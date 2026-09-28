"""
Alert Deduplication & Escalation Engine.

Eliminates operational alert fatigue by deduplicating redundant predictive alerts
targeting the same ATM kiosk within a rolling time window (default: 24h), while
deterministically escalating existing alerts upon material priority surge,
high-frequency incident velocity, or verified convergence corroboration.
"""

from datetime import datetime, timedelta
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import uuid

from backend.app.convergence_engine import detect_repeated_convergence
from backend.app.playbook_engine import generate_investigator_playbook

# Operational priority tier hierarchy
PRIORITY_TIER_ORDER: Dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Safely parses timestamp strings across common operational formats."""
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(ts_str[:19], fmt[:19])
        except (ValueError, TypeError):
            continue
    return None


def find_active_alert(
    db_conn: sqlite3.Connection,
    atm_id: str,
    reference_timestamp: Optional[str] = None,
    window_hours: int = 24,
) -> Optional[Dict[str, Any]]:
    """
    Locates an active operational alert for the specified ATM within the rolling time window.
    An alert is considered active if it targets the exact same ATM kiosk and occurred
    within window_hours of reference_timestamp.
    """
    ref_dt = parse_timestamp(reference_timestamp) if reference_timestamp else datetime.now()
    if not ref_dt:
        ref_dt = datetime.now()

    start_window = (ref_dt - timedelta(hours=window_hours)).strftime("%Y-%m-%d %H:%M:%S")
    end_window = (ref_dt + timedelta(hours=window_hours)).strftime("%Y-%m-%d %H:%M:%S")

    cur = db_conn.cursor()
    # Query active alerts for the exact target ATM within the temporal window
    cur.execute(
        """
        SELECT * FROM predictions
        WHERE predicted_atm_id = ?
          AND prediction_timestamp BETWEEN ? AND ?
          AND action_status NOT IN ('RESOLVED', 'CLOSED', 'DISMISSED')
        ORDER BY prediction_timestamp DESC
        LIMIT 1;
        """,
        (atm_id, start_window, end_window),
    )
    row = cur.fetchone()
    if row:
        return dict(row)

    return None


def evaluate_alert_escalation(
    existing_alert: Dict[str, Any],
    incoming_candidate: Dict[str, Any],
    db_conn: sqlite3.Connection,
    reference_timestamp: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """
    Evaluates whether an incoming predictive event warrants escalating an existing active alert.

    Escalation triggers:
    1. Priority Tier Increase (e.g. MEDIUM -> HIGH, or LOW -> CRITICAL).
    2. Material Priority Score Surge (+10 or more points).
    3. High-Frequency Velocity (occurrence_count >= 3 within active window).
    4. Convergence Corroboration (active HIGH or CRITICAL convergence at target ATM).

    Returns:
        (is_escalated, escalation_triggers)
    """
    triggers: List[str] = []

    existing_score = existing_alert.get("priority_score", 0) or 0
    existing_level = (existing_alert.get("priority_level", "LOW") or "LOW").upper()
    existing_count = existing_alert.get("occurrence_count", 1) or 1
    existing_state = (existing_alert.get("alert_state", "NEW") or "NEW").upper()

    incoming_score = incoming_candidate.get("priority_score", 0) or 0
    incoming_level = (incoming_candidate.get("priority_level", "LOW") or "LOW").upper()
    new_count = existing_count + 1

    # 1. Priority Tier Increase
    exist_tier = PRIORITY_TIER_ORDER.get(existing_level, 1)
    incom_tier = PRIORITY_TIER_ORDER.get(incoming_level, 1)
    if incom_tier > exist_tier:
        triggers.append(
            f"Priority tier elevated from {existing_level} to {incoming_level} ({existing_score} -> {incoming_score})"
        )

    # 2. Material Priority Score Surge (>= 10 points)
    score_diff = incoming_score - existing_score
    if score_diff >= 10:
        triggers.append(
            f"Material priority score surge (+{score_diff} pts: {existing_score} -> {incoming_score})"
        )

    # 3. High-Frequency Velocity (>= 3 repeated incidents mapped to ATM)
    if new_count >= 3:
        triggers.append(
            f"High-frequency incident velocity ({new_count} repeated complaints mapped to this ATM within 24h)"
        )

    # 4. Convergence Corroboration
    try:
        conv_result = detect_repeated_convergence(
            db_conn=db_conn,
            window_hours=48,
            min_matches=2,
            target_type="atm",
            reference_timestamp=reference_timestamp,
        )
        target_atm = incoming_candidate.get("predicted_atm_id")
        for conv in conv_result.get("convergences", []):
            if conv.get("target_id") == target_atm and conv.get("severity_level") in ("HIGH", "CRITICAL"):
                triggers.append(
                    f"Corroborated by active {conv.get('severity_level')} spatial convergence at ATM (score: {conv.get('convergence_score')})"
                )
                break
    except Exception:
        # Graceful degradation if convergence check encounters a transient error
        pass

    # If alert was already escalated, maintain escalation state
    if existing_state == "ESCALATED":
        if not triggers:
            triggers.append(f"Escalated priority maintained across repeat incident (occurrence {new_count})")
        return True, triggers

    is_escalated = len(triggers) > 0
    return is_escalated, triggers


def process_alert_lifecycle(
    db_conn: sqlite3.Connection,
    prediction_candidate: Dict[str, Any],
    window_hours: int = 24,
) -> Dict[str, Any]:
    """
    Processes an incoming prediction through the Alert Deduplication and Escalation lifecycle:
    - If no active alert exists for the predicted ATM: creates a NEW alert.
    - If an active alert exists:
        - If escalation criteria met: escalates existing alert (ESCALATED).
        - If non-escalating: refreshes existing alert (REFRESHED) with incremented occurrence count.
    Reuses existing prediction_id to prevent redundant duplicate alerts in the operational dispatch log.
    """
    predicted_atm_id = prediction_candidate["predicted_atm_id"]
    ref_ts = prediction_candidate.get("reference_timestamp")
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_ts = ref_ts if ref_ts else now_ts

    cur = db_conn.cursor()

    # 1. Search for active operational alert
    active_alert = find_active_alert(
        db_conn=db_conn,
        atm_id=predicted_atm_id,
        reference_timestamp=active_ts,
        window_hours=window_hours,
    )

    # --------------------------------------------------------------------------
    # CASE 1: Brand New Alert
    # --------------------------------------------------------------------------
    if active_alert is None:
        prediction_id = f"PRED-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        alert_state = "NEW"
        action_status = "NEW_ALERT"
        occurrence_count = 1
        escalation_reason = ""

        # Persist new alert to predictions table
        cur.execute(
            """
            INSERT INTO predictions (
                prediction_id, complaint_id, prediction_timestamp, predicted_atm_id,
                predicted_zone_id, confidence_score, top_candidates_json,
                predicted_window_start, predicted_window_end, risk_level,
                explanation_codes_json, action_status, priority_score, priority_level,
                priority_reasons_json, playbook_json, alert_state, occurrence_count,
                escalation_reason, parent_alert_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                prediction_id,
                prediction_candidate.get("complaint_id"),
                active_ts,
                predicted_atm_id,
                prediction_candidate["predicted_zone_id"],
                prediction_candidate["confidence_score"],
                json.dumps(prediction_candidate.get("top_candidates", [])),
                prediction_candidate.get("predicted_window_start", ""),
                prediction_candidate.get("predicted_window_end", ""),
                prediction_candidate.get("risk_level", "MODERATE"),
                json.dumps(prediction_candidate.get("explanation_codes", [])),
                action_status,
                prediction_candidate.get("priority_score", 0),
                prediction_candidate.get("priority_level", "LOW"),
                json.dumps(prediction_candidate.get("priority_reasons", [])),
                json.dumps(prediction_candidate.get("playbook", {})),
                alert_state,
                occurrence_count,
                escalation_reason,
                None,
            ),
        )

        res_dict = {
            "prediction_id": prediction_id,
            "complaint_id": prediction_candidate.get("complaint_id", ""),
            "prediction_timestamp": active_ts,
            "predicted_atm_id": predicted_atm_id,
            "predicted_zone_id": prediction_candidate["predicted_zone_id"],
            "confidence_score": prediction_candidate["confidence_score"],
            "top_candidates": prediction_candidate.get("top_candidates", []),
            "predicted_window_start": prediction_candidate.get("predicted_window_start", ""),
            "predicted_window_end": prediction_candidate.get("predicted_window_end", ""),
            "risk_level": prediction_candidate.get("risk_level", "MODERATE"),
            "explanation_codes": prediction_candidate.get("explanation_codes", []),
            "action_status": action_status,
            "priority_score": prediction_candidate.get("priority_score", 0),
            "priority_level": prediction_candidate.get("priority_level", "LOW"),
            "priority_reasons": prediction_candidate.get("priority_reasons", []),
            "playbook": prediction_candidate.get("playbook"),
            "alert_state": alert_state,
            "occurrence_count": occurrence_count,
            "escalation_reason": escalation_reason,
            "parent_alert_id": None,
        }
        from backend.app.case_engine import create_or_link_case
        case_id, case_status = create_or_link_case(db_conn, res_dict)
        res_dict["case_id"] = case_id
        res_dict["case_status"] = case_status
        return res_dict

    # --------------------------------------------------------------------------
    # CASE 2: Active Alert Exists -> Evaluate Escalation vs. Refresh
    # --------------------------------------------------------------------------
    existing_id = active_alert["prediction_id"]
    existing_count = active_alert.get("occurrence_count", 1) or 1
    new_count = existing_count + 1

    is_escalated, triggers = evaluate_alert_escalation(
        existing_alert=active_alert,
        incoming_candidate=prediction_candidate,
        db_conn=db_conn,
        reference_timestamp=active_ts,
    )

    if is_escalated:
        alert_state = "ESCALATED"
        action_status = "ESCALATED_ALERT"
        escalation_reason = "Escalated: " + "; ".join(triggers)

        # Update priority score and level to highest observed
        final_score = max(active_alert.get("priority_score", 0) or 0, prediction_candidate.get("priority_score", 0))
        
        # Determine highest priority level
        exist_tier = PRIORITY_TIER_ORDER.get((active_alert.get("priority_level") or "LOW").upper(), 1)
        incom_tier = PRIORITY_TIER_ORDER.get((prediction_candidate.get("priority_level") or "LOW").upper(), 1)
        if incom_tier >= exist_tier:
            final_level = prediction_candidate.get("priority_level", "HIGH")
            final_reasons = prediction_candidate.get("priority_reasons", [])
        else:
            final_level = active_alert.get("priority_level", "HIGH")
            try:
                final_reasons = json.loads(active_alert["priority_reasons_json"])
            except Exception:
                final_reasons = prediction_candidate.get("priority_reasons", [])

        # Regenerate playbook with updated escalation context
        try:
            playbook = generate_investigator_playbook({
                "predicted_atm_id": predicted_atm_id,
                "predicted_zone_id": prediction_candidate["predicted_zone_id"],
                "risk_level": "CRITICAL" if final_level == "CRITICAL" else "HIGH",
                "priority_level": final_level,
                "priority_score": final_score,
                "confidence_score": max(active_alert.get("confidence_score", 0.0), prediction_candidate.get("confidence_score", 0.0)),
                "predicted_window_start": prediction_candidate.get("predicted_window_start", ""),
                "predicted_window_end": prediction_candidate.get("predicted_window_end", ""),
                "explanation_codes": prediction_candidate.get("explanation_codes", []),
                "top_candidates": prediction_candidate.get("top_candidates", []),
            })
        except Exception:
            playbook = prediction_candidate.get("playbook")

        # Update existing record in predictions table
        cur.execute(
            """
            UPDATE predictions SET
                prediction_timestamp = ?,
                complaint_id = ?,
                action_status = ?,
                alert_state = ?,
                occurrence_count = ?,
                escalation_reason = ?,
                priority_score = ?,
                priority_level = ?,
                priority_reasons_json = ?,
                confidence_score = ?,
                risk_level = ?,
                predicted_window_start = ?,
                predicted_window_end = ?,
                playbook_json = ?
            WHERE prediction_id = ?;
            """,
            (
                active_ts,
                prediction_candidate.get("complaint_id") or active_alert.get("complaint_id"),
                action_status,
                alert_state,
                new_count,
                escalation_reason,
                final_score,
                final_level,
                json.dumps(final_reasons),
                max(active_alert.get("confidence_score", 0.0), prediction_candidate.get("confidence_score", 0.0)),
                "CRITICAL" if final_level == "CRITICAL" else "HIGH",
                prediction_candidate.get("predicted_window_start", active_alert.get("predicted_window_start")),
                prediction_candidate.get("predicted_window_end", active_alert.get("predicted_window_end")),
                json.dumps(playbook),
                existing_id,
            ),
        )

        res_dict = {
            "prediction_id": existing_id,
            "complaint_id": prediction_candidate.get("complaint_id") or active_alert.get("complaint_id", ""),
            "prediction_timestamp": active_ts,
            "predicted_atm_id": predicted_atm_id,
            "predicted_zone_id": prediction_candidate["predicted_zone_id"],
            "confidence_score": max(active_alert.get("confidence_score", 0.0), prediction_candidate.get("confidence_score", 0.0)),
            "top_candidates": prediction_candidate.get("top_candidates", []),
            "predicted_window_start": prediction_candidate.get("predicted_window_start", active_alert.get("predicted_window_start")),
            "predicted_window_end": prediction_candidate.get("predicted_window_end", active_alert.get("predicted_window_end")),
            "risk_level": "CRITICAL" if final_level == "CRITICAL" else "HIGH",
            "explanation_codes": prediction_candidate.get("explanation_codes", []),
            "action_status": action_status,
            "priority_score": final_score,
            "priority_level": final_level,
            "priority_reasons": final_reasons,
            "playbook": playbook,
            "alert_state": alert_state,
            "occurrence_count": new_count,
            "escalation_reason": escalation_reason,
            "parent_alert_id": existing_id,
        }
        from backend.app.case_engine import create_or_link_case
        case_id, case_status = create_or_link_case(db_conn, res_dict)
        res_dict["case_id"] = case_id
        res_dict["case_status"] = case_status
        return res_dict

    else:
        # ----------------------------------------------------------------------
        # CASE 3: Active Alert Exists & No Escalation Trigger -> REFRESHED
        # ----------------------------------------------------------------------
        alert_state = "REFRESHED"
        action_status = "REFRESHED_ALERT"
        escalation_reason = (
            f"Alert refreshed: Subsequent incident logged at {predicted_atm_id} "
            f"(occurrence {new_count}). Operational risk parameters stable."
        )

        # Retain original established priority score and level (no false score inflation)
        final_score = active_alert.get("priority_score", 0) or 0
        final_level = active_alert.get("priority_level", "LOW") or "LOW"
        try:
            final_reasons = json.loads(active_alert["priority_reasons_json"])
        except Exception:
            final_reasons = prediction_candidate.get("priority_reasons", [])

        try:
            playbook = json.loads(active_alert["playbook_json"])
        except Exception:
            playbook = prediction_candidate.get("playbook")

        # Update timestamp, occurrence count, state, and status
        cur.execute(
            """
            UPDATE predictions SET
                prediction_timestamp = ?,
                complaint_id = ?,
                action_status = ?,
                alert_state = ?,
                occurrence_count = ?,
                escalation_reason = ?
            WHERE prediction_id = ?;
            """,
            (
                active_ts,
                prediction_candidate.get("complaint_id") or active_alert.get("complaint_id"),
                action_status,
                alert_state,
                new_count,
                escalation_reason,
                existing_id,
            ),
        )

        res_dict = {
            "prediction_id": existing_id,
            "complaint_id": prediction_candidate.get("complaint_id") or active_alert.get("complaint_id", ""),
            "prediction_timestamp": active_ts,
            "predicted_atm_id": predicted_atm_id,
            "predicted_zone_id": active_alert.get("predicted_zone_id", prediction_candidate["predicted_zone_id"]),
            "confidence_score": active_alert.get("confidence_score", prediction_candidate["confidence_score"]),
            "top_candidates": prediction_candidate.get("top_candidates", []),
            "predicted_window_start": active_alert.get("predicted_window_start", prediction_candidate.get("predicted_window_start")),
            "predicted_window_end": active_alert.get("predicted_window_end", prediction_candidate.get("predicted_window_end")),
            "risk_level": active_alert.get("risk_level", prediction_candidate.get("risk_level")),
            "explanation_codes": prediction_candidate.get("explanation_codes", []),
            "action_status": action_status,
            "priority_score": final_score,
            "priority_level": final_level,
            "priority_reasons": final_reasons,
            "playbook": playbook,
            "alert_state": alert_state,
            "occurrence_count": new_count,
            "escalation_reason": escalation_reason,
            "parent_alert_id": existing_id,
        }
        from backend.app.case_engine import create_or_link_case
        case_id, case_status = create_or_link_case(db_conn, res_dict)
        res_dict["case_id"] = case_id
        res_dict["case_status"] = case_status
        return res_dict
