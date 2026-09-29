"""
Operational Case Management & Lifecycle Engine.

Connects the predictive alert workflow to an operational case lifecycle:
NEW_ALERT -> PATROL_DISPATCHED -> RESOLVED

Ensures strict linking to originating complaints, predictions, target ATMs,
zones, priority triage scores, and intervention windows, while preventing
duplicate case generation upon alert deduplication.
"""

from datetime import datetime
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import uuid
from fastapi import HTTPException, status


VALID_CASE_STATUSES = {"NEW_ALERT", "PATROL_DISPATCHED", "OUTCOME_PENDING", "RESOLVED", "CLOSED"}

VALID_STATUS_TRANSITIONS = {
    "NEW_ALERT": {"PATROL_DISPATCHED"},
    "PATROL_DISPATCHED": {"OUTCOME_PENDING", "RESOLVED", "CLOSED"},
    "OUTCOME_PENDING": {"RESOLVED", "CLOSED"},
    "RESOLVED": set(),
    "CLOSED": set(),
}


def generate_case_id() -> str:
    """Generates a standardized unique Case ID, e.g. CASE-20260928-89F12A."""
    date_str = datetime.now().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"CASE-{date_str}-{unique_suffix}"


def get_case_by_id(db_conn: sqlite3.Connection, case_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves an operational case record by case_id enriched with state machine telemetry."""
    cur = db_conn.cursor()
    cur.execute("SELECT * FROM operational_cases WHERE case_id = ?;", (case_id,))
    row = cur.fetchone()
    if not row:
        return None

    d = dict(row)
    # Check dispatch record
    cur.execute("SELECT dispatch_id, dispatch_status FROM patrol_dispatches WHERE case_id = ?;", (case_id,))
    disp_row = cur.fetchone()
    d["is_dispatched"] = bool(disp_row and disp_row[1] == "DISPATCHED")
    d["dispatch_id"] = disp_row[0] if disp_row else None

    # Check outcome record
    cur.execute("SELECT outcome_id, outcome_status FROM case_outcomes WHERE case_id = ?;", (case_id,))
    out_row = cur.fetchone()
    d["has_outcome"] = bool(out_row)
    d["outcome_status"] = out_row[1] if out_row else None

    # Check linked prediction record for candidates and explainability
    pred_id = d.get("parent_alert_id")
    cur.execute(
        """
        SELECT confidence_score, top_candidates_json, explanation_codes_json, priority_reasons_json
        FROM predictions
        WHERE prediction_id = ? OR case_id = ?
        ORDER BY prediction_timestamp DESC LIMIT 1;
        """,
        (pred_id, case_id),
    )
    pred_row = cur.fetchone()
    if pred_row:
        d["confidence_score"] = float(pred_row[0]) if pred_row[0] is not None else 0.15
        try:
            d["top_candidates"] = json.loads(pred_row[1] or "[]")
        except Exception:
            d["top_candidates"] = []
        try:
            d["explanation_codes"] = json.loads(pred_row[2] or "[]")
        except Exception:
            d["explanation_codes"] = []
        try:
            d["priority_reasons"] = json.loads(pred_row[3] or "[]")
        except Exception:
            d["priority_reasons"] = []
    else:
        d["confidence_score"] = 0.15
        d["top_candidates"] = []
        d["explanation_codes"] = []
        d["priority_reasons"] = []

    # Determine next valid primary action
    st = d.get("case_status", "NEW_ALERT")
    if st == "NEW_ALERT":
        d["next_valid_action"] = "DISPATCH_PATROL"
    elif st == "PATROL_DISPATCHED":
        d["next_valid_action"] = "LOG_OUTCOME"
    elif st == "OUTCOME_PENDING":
        d["next_valid_action"] = "RECORD_OUTCOME"
    else:
        d["next_valid_action"] = "NONE"

    return d


def get_case_by_parent_alert_id(db_conn: sqlite3.Connection, parent_alert_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves an active operational case linked to a parent alert ID."""
    cur = db_conn.cursor()
    cur.execute(
        "SELECT * FROM operational_cases WHERE parent_alert_id = ? ORDER BY created_timestamp DESC LIMIT 1;",
        (parent_alert_id,),
    )
    row = cur.fetchone()
    if row:
        return dict(row)
    return None


def create_or_link_case(
    db_conn: sqlite3.Connection,
    alert_result: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Creates an operational case for a NEW alert, or retrieves and links the
    existing case when alert deduplication identifies a REFRESHED or ESCALATED alert.
    
    Returns:
        (case_id, case_status)
    """
    cur = db_conn.cursor()
    prediction_id = alert_result.get("prediction_id")
    parent_alert_id = alert_result.get("parent_alert_id") or prediction_id
    alert_state = (alert_result.get("alert_state") or "NEW").upper()

    # 1. Deduplication check: if alert is REFRESHED or ESCALATED, look for existing case
    if alert_state in ("REFRESHED", "ESCALATED") or (parent_alert_id and parent_alert_id != prediction_id):
        existing_case = get_case_by_parent_alert_id(db_conn, parent_alert_id)
        if not existing_case and prediction_id:
            existing_case = get_case_by_parent_alert_id(db_conn, prediction_id)

        if existing_case:
            case_id = existing_case["case_id"]
            current_status = existing_case["case_status"]

            # If escalated, update case priority score and level
            if alert_state == "ESCALATED":
                new_score = alert_result.get("priority_score", existing_case["priority_score"])
                new_level = alert_result.get("priority_level", existing_case["priority_level"])
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                reason = alert_result.get("escalation_reason", "")
                existing_notes = existing_case.get("notes") or ""
                updated_notes = f"{existing_notes}\n[{now_str}] Alert Escalation: {reason}".strip()

                cur.execute(
                    """
                    UPDATE operational_cases SET
                        priority_score = ?,
                        priority_level = ?,
                        updated_timestamp = ?,
                        notes = ?
                    WHERE case_id = ?;
                    """,
                    (new_score, new_level, now_str, updated_notes, case_id),
                )

            # Link prediction record to case
            if prediction_id:
                cur.execute(
                    "UPDATE predictions SET case_id = ?, case_status = ? WHERE prediction_id = ?;",
                    (case_id, current_status, prediction_id),
                )
            return case_id, current_status

    # 2. Check if a case already exists for this exact prediction_id (idempotency)
    if prediction_id:
        existing_case = get_case_by_parent_alert_id(db_conn, prediction_id)
        if existing_case:
            return existing_case["case_id"], existing_case["case_status"]

    # 3. Create brand new operational case
    case_id = generate_case_id()
    case_status = "NEW_ALERT"
    created_ts = alert_result.get("prediction_timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updated_ts = created_ts

    cur.execute(
        """
        INSERT INTO operational_cases (
            case_id, parent_alert_id, complaint_id, predicted_atm_id,
            predicted_zone_id, priority_score, priority_level,
            intervention_window_start, intervention_window_end,
            case_status, created_timestamp, updated_timestamp, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            case_id,
            prediction_id or f"ALERT-{case_id}",
            alert_result.get("complaint_id"),
            alert_result.get("predicted_atm_id") or "UNKNOWN",
            alert_result.get("predicted_zone_id") or "ZONE_CENTRAL",
            alert_result.get("priority_score", 0),
            alert_result.get("priority_level", "LOW"),
            alert_result.get("predicted_window_start", ""),
            alert_result.get("predicted_window_end", ""),
            case_status,
            created_ts,
            updated_ts,
            f"Case opened from initial predictive intercept alert {prediction_id}.",
        ),
    )

    # Link prediction record to case
    if prediction_id:
        cur.execute(
            "UPDATE predictions SET case_id = ?, case_status = ? WHERE prediction_id = ?;",
            (case_id, case_status, prediction_id),
        )

    return case_id, case_status


def transition_case_status(
    db_conn: sqlite3.Connection,
    case_id: str,
    target_status: str,
    notes: Optional[str] = "",
) -> Dict[str, Any]:
    """
    Validates and executes a lifecycle state transition on an operational case:
    NEW_ALERT -> PATROL_DISPATCHED -> RESOLVED

    Raises HTTPException(400) if transition is invalid or case not found.
    """
    cur = db_conn.cursor()
    case = get_case_by_id(db_conn, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operational case '{case_id}' not found.",
        )

    current_status = case["case_status"]
    target_status = target_status.strip().upper() if target_status else ""

    if target_status not in VALID_CASE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid case status '{target_status}'. Valid states: {', '.join(sorted(VALID_CASE_STATUSES))}.",
        )

    allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid lifecycle transition from '{current_status}' to '{target_status}'. "
                f"Allowed transitions from '{current_status}': {list(allowed) if allowed else 'None (Terminal state)'}."
            ),
        )

    if target_status in ("RESOLVED", "CLOSED"):
        cur.execute("SELECT outcome_id FROM case_outcomes WHERE case_id = ?;", (case_id,))
        if not cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot close case '{case_id}' before an operational outcome is recorded.",
            )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing_notes = case.get("notes") or ""
    log_entry = f"[{now_str}] Status transitioned from {current_status} to {target_status}."
    if notes:
        log_entry += f" Notes: {notes.strip()}"
    new_notes = f"{existing_notes}\n{log_entry}".strip()

    cur.execute(
        """
        UPDATE operational_cases SET
            case_status = ?,
            updated_timestamp = ?,
            notes = ?
        WHERE case_id = ?;
        """,
        (target_status, now_str, new_notes, case_id),
    )

    # Propagate case status to linked predictions
    cur.execute(
        "UPDATE predictions SET case_status = ? WHERE case_id = ? OR parent_alert_id = ?;",
        (target_status, case_id, case["parent_alert_id"]),
    )

    return get_case_by_id(db_conn, case_id)


def list_operational_cases(
    db_conn: sqlite3.Connection,
    case_status: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """Retrieves recent operational cases with optional status filtering."""
    cur = db_conn.cursor()
    lim = limit if isinstance(limit, int) else 25
    if case_status and isinstance(case_status, str) and case_status.strip().upper() in VALID_CASE_STATUSES:
        cur.execute(
            "SELECT * FROM operational_cases WHERE case_status = ? ORDER BY updated_timestamp DESC LIMIT ?;",
            (case_status.strip().upper(), lim),
        )
    else:
        cur.execute(
            "SELECT * FROM operational_cases ORDER BY updated_timestamp DESC LIMIT ?;",
            (lim,),
        )
    rows = cur.fetchall()
    return [dict(r) for r in rows]
