"""
Field Patrol Dispatch Routing & Evidence Export Engine.

Lightweight operational service connected directly to the Case Lifecycle:
- Generates structured patrol dispatch records (READY -> DISPATCHED)
- Routes tactical briefs, lead time windows, and playbook checklists to field patrols
- Compiles comprehensive multi-source evidence packets (predictions, candidates, 
  spatiotemporal convergences, and verified ML provenance) for investigators
- Exports evidence packets cleanly in standardized JSON and CSV formats.
"""

import csv
from datetime import datetime
import io
import json
import sqlite3
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status

from backend.app.case_engine import get_case_by_id, transition_case_status


def generate_dispatch_id() -> str:
    """Generates a standardized unique Dispatch ID, e.g. DISP-20260929-A1B2C3."""
    date_str = datetime.now().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"DISP-{date_str}-{unique_suffix}"


def get_dispatch_by_id(db_conn: sqlite3.Connection, dispatch_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a patrol dispatch record by dispatch_id."""
    cur = db_conn.cursor()
    cur.execute("SELECT * FROM patrol_dispatches WHERE dispatch_id = ?;", (dispatch_id,))
    row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["playbook_actions"] = json.loads(d.get("playbook_actions_json") or "[]")
    except Exception:
        d["playbook_actions"] = []
    return d


def get_dispatch_by_case_id(db_conn: sqlite3.Connection, case_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the active patrol dispatch record linked to a specific case."""
    cur = db_conn.cursor()
    cur.execute(
        "SELECT * FROM patrol_dispatches WHERE case_id = ? ORDER BY created_timestamp DESC LIMIT 1;",
        (case_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["playbook_actions"] = json.loads(d.get("playbook_actions_json") or "[]")
    except Exception:
        d["playbook_actions"] = []
    return d


def list_patrol_dispatches(db_conn: sqlite3.Connection, limit: int = 25) -> List[Dict[str, Any]]:
    """Lists recent patrol dispatches."""
    cur = db_conn.cursor()
    lim = limit if isinstance(limit, int) else 25
    cur.execute("SELECT * FROM patrol_dispatches ORDER BY created_timestamp DESC LIMIT ?;", (lim,))
    rows = cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["playbook_actions"] = json.loads(d.get("playbook_actions_json") or "[]")
        except Exception:
            d["playbook_actions"] = []
        results.append(d)
    return results


def create_or_get_patrol_dispatch(
    db_conn: sqlite3.Connection,
    case_id: str,
    patrol_unit: Optional[str] = None,
    notes: Optional[str] = "",
    auto_advance_case: bool = True,
    mark_dispatched: bool = True,
) -> Dict[str, Any]:
    """
    Creates or updates a patrol dispatch record for an operational case.
    Transitions dispatch status to 'DISPATCHED' and optionally advances
    the underlying case state from 'NEW_ALERT' to 'PATROL_DISPATCHED'.
    """
    cur = db_conn.cursor()

    # 1. Fetch case record
    case = get_case_by_id(db_conn, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operational case '{case_id}' not found.",
        )

    # 2. Check if dispatch already exists
    existing = get_dispatch_by_case_id(db_conn, case_id)
    if mark_dispatched:
        if existing and existing.get("dispatch_status") == "DISPATCHED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Case '{case_id}' has already been dispatched. Cannot dispatch twice.",
            )
        if case.get("case_status") == "RESOLVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Case '{case_id}' has already been dispatched and resolved. Cannot dispatch twice.",
            )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 3. Pull tactical playbook and lead window from linked prediction
    cur.execute(
        """
        SELECT playbook_json, top_candidates_json, predicted_window_start, predicted_window_end
        FROM predictions
        WHERE case_id = ? OR prediction_id = ? OR parent_alert_id = ?
        ORDER BY prediction_timestamp DESC LIMIT 1;
        """,
        (case_id, case["parent_alert_id"], case["parent_alert_id"]),
    )
    pred_row = cur.fetchone()

    playbook_dict = {}
    playbook_actions_list = []
    tactical_brief = ""
    lead_window = ""

    if pred_row:
        try:
            playbook_dict = json.loads(pred_row["playbook_json"] or "{}")
            playbook_actions_list = playbook_dict.get("actions", [])
            tactical_brief = playbook_dict.get("dispatch_brief") or playbook_dict.get("summary") or ""
        except Exception:
            pass

        w_start = pred_row["predicted_window_start"]
        w_end = pred_row["predicted_window_end"]
        if w_start and w_end and len(w_start) >= 16 and len(w_end) >= 16:
            lead_window = f"{w_start[11:16]} - {w_end[11:16]} hrs"

    if not lead_window:
        c_start = case.get("intervention_window_start", "")
        c_end = case.get("intervention_window_end", "")
        if c_start and c_end and len(c_start) >= 16 and len(c_end) >= 16:
            lead_window = f"{c_start[11:16]} - {c_end[11:16]} hrs"
        else:
            lead_window = "Immediate Intercept Window"

    if not tactical_brief:
        zone_name = case["predicted_zone_id"].replace("ZONE_", "Zone ")
        tactical_brief = (
            f"[SECTOR DISPATCH BRIEF] Priority: {case['priority_level']} (Score: {case['priority_score']}/100) | "
            f"Target ATM: {case['predicted_atm_id']} ({zone_name}) | Tactical Lead Window: {lead_window}."
        )

    # 4. Resolve patrol unit callsign
    assigned_unit = patrol_unit.strip() if patrol_unit and patrol_unit.strip() else ""
    if not assigned_unit:
        zone_abbr = case["predicted_zone_id"].replace("ZONE_", "")
        assigned_unit = f"PCR-{zone_abbr}-01"

    new_dispatch_status = "DISPATCHED" if mark_dispatched else "READY"

    if existing:
        dispatch_id = existing["dispatch_id"]
        existing_notes = existing.get("notes") or ""
        updated_notes = f"{existing_notes}\n[{now_str}] Updated dispatch: unit {assigned_unit} ({new_dispatch_status}). {notes}".strip()

        cur.execute(
            """
            UPDATE patrol_dispatches SET
                patrol_unit_assigned = ?,
                dispatch_status = ?,
                dispatched_timestamp = ?,
                notes = ?
            WHERE dispatch_id = ?;
            """,
            (assigned_unit, new_dispatch_status, now_str, updated_notes, dispatch_id),
        )
    else:
        dispatch_id = generate_dispatch_id()
        cur.execute(
            """
            INSERT INTO patrol_dispatches (
                dispatch_id, case_id, target_atm_id, zone_id,
                priority_score, priority_level, lead_time_window,
                patrol_unit_assigned, dispatch_status, playbook_actions_json,
                tactical_brief, dispatched_timestamp, created_timestamp, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                dispatch_id,
                case_id,
                case["predicted_atm_id"],
                case["predicted_zone_id"],
                case["priority_score"],
                case["priority_level"],
                lead_window,
                assigned_unit,
                new_dispatch_status,
                json.dumps(playbook_actions_list),
                tactical_brief,
                now_str if mark_dispatched else None,
                now_str,
                notes or f"Patrol dispatch initiated for case {case_id}.",
            ),
        )

    # 5. Automatically advance case state to PATROL_DISPATCHED if currently NEW_ALERT
    if auto_advance_case and case["case_status"] == "NEW_ALERT":
        transition_case_status(
            db_conn=db_conn,
            case_id=case_id,
            target_status="PATROL_DISPATCHED",
            notes=f"Field patrol dispatched ({assigned_unit}, Dispatch ID: {dispatch_id}).",
        )

    return get_dispatch_by_id(db_conn, dispatch_id)


def compile_case_evidence_packet(
    db_conn: sqlite3.Connection,
    case_id: str,
) -> Dict[str, Any]:
    """
    Compiles a comprehensive, structured evidence packet for an operational case.
    Aggregates:
    - Case lifecycle metadata
    - Linked prediction and priority triage breakdown
    - Physical ATM location attributes
    - Top ranked candidate ATMs
    - Active repeated convergences and emerging clusters affecting target/zone
    - Dispatch status and tactical patrol brief
    - Verified Phase 2 ML model provenance
    """
    cur = db_conn.cursor()

    # 1. Operational Case
    case = get_case_by_id(db_conn, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operational case '{case_id}' not found.",
        )

    # 2. Linked Prediction Record
    cur.execute(
        """
        SELECT * FROM predictions
        WHERE case_id = ? OR prediction_id = ? OR parent_alert_id = ?
        ORDER BY prediction_timestamp DESC LIMIT 1;
        """,
        (case_id, case["parent_alert_id"], case["parent_alert_id"]),
    )
    pred_row = cur.fetchone()
    pred_dict = None
    top_candidates = []
    explanation_codes = []
    priority_reasons = []

    if pred_row:
        pred_dict = dict(pred_row)
        try:
            top_candidates = json.loads(pred_dict.get("top_candidates_json") or "[]")
        except Exception:
            top_candidates = []
        try:
            explanation_codes = json.loads(pred_dict.get("explanation_codes_json") or "[]")
        except Exception:
            explanation_codes = []
        try:
            priority_reasons = json.loads(pred_dict.get("priority_reasons_json") or "[]")
        except Exception:
            priority_reasons = []

        pred_dict["top_candidates"] = top_candidates
        pred_dict["explanation_codes"] = explanation_codes
        pred_dict["priority_reasons"] = priority_reasons

    # 3. Target ATM Physical Facility Metadata
    target_atm_id = case["predicted_atm_id"]
    cur.execute("SELECT * FROM atm_locations WHERE atm_id = ?;", (target_atm_id,))
    atm_row = cur.fetchone()
    atm_dict = dict(atm_row) if atm_row else None

    # 4. Patrol Dispatch Record
    dispatch_dict = get_dispatch_by_case_id(db_conn, case_id)

    # 4b. Recorded Case Outcome
    outcome_dict = None
    try:
        from backend.app.outcome_engine import get_outcome_by_case_id
        outcome_dict = get_outcome_by_case_id(db_conn, case_id)
    except Exception:
        outcome_dict = None

    # 5. Convergence Intelligence
    convergences = []
    try:
        from backend.app.convergence_engine import detect_repeated_convergence
        conv_res = detect_repeated_convergence(
            db_conn=db_conn,
            window_hours=168,
            min_matches=2,
            target_type="all",
            zone=case["predicted_zone_id"],
        )
        if conv_res and "convergences" in conv_res:
            convergences = [
                c for c in conv_res["convergences"]
                if c.get("target_id") == target_atm_id or c.get("zone_id") == case["predicted_zone_id"]
            ]
    except Exception:
        convergences = []

    # 6. Cluster Intelligence
    clusters = []
    try:
        from backend.app.cluster_engine import detect_emerging_clusters
        clust_res = detect_emerging_clusters(
            db_conn=db_conn,
            window_hours=72,
            min_events=2,
            zone=case["predicted_zone_id"],
        )
        if clust_res and "clusters" in clust_res:
            clusters = [
                cl for cl in clust_res["clusters"]
                if cl.get("primary_atm_id") == target_atm_id or cl.get("zone") == case["predicted_zone_id"]
            ]
    except Exception:
        clusters = []

    # 7. Model Provenance & Evaluation Integrity
    model_provenance = {
        "model_name": "Cybercrime_Cashout_Spatial_Predictor",
        "evaluation_partition": "P3_FUTURE_TEST_ONLY",
        "verified_metrics": {
            "top1_spatial_accuracy_pct": 10.17,
            "top3_spatial_accuracy_pct": 31.71,
            "top5_spatial_accuracy_pct": 41.88,
            "zone_level_accuracy_pct": 68.89,
            "calibrated_brier_score": 0.9726,
            "calibrated_log_loss": 3.5199,
            "temporal_window_coverage_pct": 50.38,
        },
    }

    return {
        "export_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "case": case,
        "dispatch": dispatch_dict,
        "outcome": outcome_dict,
        "prediction": pred_dict,
        "target_atm": atm_dict,
        "top_candidates": top_candidates,
        "convergences": convergences,
        "clusters": clusters,
        "model_provenance": model_provenance,
    }


def export_case_evidence_csv(evidence: Dict[str, Any]) -> str:
    """
    Serializes a case evidence packet into a clean, human-readable CSV table.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["SECTION", "FIELD", "VALUE"])

    # Case section
    c = evidence.get("case", {})
    writer.writerow(["CASE_METADATA", "Case ID", c.get("case_id", "")])
    writer.writerow(["CASE_METADATA", "Parent Alert ID", c.get("parent_alert_id", "")])
    writer.writerow(["CASE_METADATA", "Complaint ID", c.get("complaint_id", "")])
    writer.writerow(["CASE_METADATA", "Current Status", c.get("case_status", "")])
    writer.writerow(["CASE_METADATA", "Priority Score", c.get("priority_score", "")])
    writer.writerow(["CASE_METADATA", "Priority Level", c.get("priority_level", "")])
    writer.writerow(["CASE_METADATA", "Intervention Window", f"{c.get('intervention_window_start', '')} to {c.get('intervention_window_end', '')}"])
    writer.writerow(["CASE_METADATA", "Created Timestamp", c.get("created_timestamp", "")])
    writer.writerow(["CASE_METADATA", "Updated Timestamp", c.get("updated_timestamp", "")])

    # Target ATM
    a = evidence.get("target_atm") or {}
    writer.writerow(["TARGET_ATM", "ATM ID", a.get("atm_id", c.get("predicted_atm_id", ""))])
    writer.writerow(["TARGET_ATM", "Bank Network", a.get("bank_code", "")])
    writer.writerow(["TARGET_ATM", "Zone ID", a.get("zone_id", c.get("predicted_zone_id", ""))])
    writer.writerow(["TARGET_ATM", "Location Type", a.get("location_type", "")])
    writer.writerow(["TARGET_ATM", "Latitude", a.get("latitude", "")])
    writer.writerow(["TARGET_ATM", "Longitude", a.get("longitude", "")])
    writer.writerow(["TARGET_ATM", "Historical Cashouts", a.get("historical_cashout_count", "")])

    # Dispatch
    d = evidence.get("dispatch") or {}
    writer.writerow(["PATROL_DISPATCH", "Dispatch ID", d.get("dispatch_id", "NOT_DISPATCHED")])
    writer.writerow(["PATROL_DISPATCH", "Assigned Unit", d.get("patrol_unit_assigned", "UNASSIGNED")])
    writer.writerow(["PATROL_DISPATCH", "Dispatch Status", d.get("dispatch_status", "READY")])
    writer.writerow(["PATROL_DISPATCH", "Dispatched Timestamp", d.get("dispatched_timestamp", "")])
    writer.writerow(["PATROL_DISPATCH", "Tactical Brief", d.get("tactical_brief", "")])

    # Outcome
    o = evidence.get("outcome") or {}
    if o:
        writer.writerow(["RECORDED_OUTCOME", "Outcome ID", o.get("outcome_id", "")])
        writer.writerow(["RECORDED_OUTCOME", "Status", o.get("outcome_status", "")])
        writer.writerow(["RECORDED_OUTCOME", "Actual ATM", o.get("actual_atm_id", "N/A")])
        writer.writerow(["RECORDED_OUTCOME", "Spatial Hit", "YES" if o.get("is_spatial_hit") else "NO"])
        writer.writerow(["RECORDED_OUTCOME", "Recorded Timestamp", o.get("recorded_timestamp", "")])
        writer.writerow(["RECORDED_OUTCOME", "Investigator Notes", o.get("notes", "")])

    # Top Candidates
    for idx, cand in enumerate(evidence.get("top_candidates", []), 1):
        writer.writerow([
            "CANDIDATE_ATMS",
            f"Rank {cand.get('rank', idx)}",
            f"{cand.get('atm_id')} ({cand.get('bank_code', '')}) - Prob: {round(cand.get('probability', 0)*100, 1)}% | Zone: {cand.get('zone_id')}",
        ])

    # Provenance
    m = evidence.get("model_provenance", {})
    metrics = m.get("verified_metrics", {})
    writer.writerow(["ML_PROVENANCE", "Model Name", m.get("model_name", "")])
    writer.writerow(["ML_PROVENANCE", "Evaluation Partition", m.get("evaluation_partition", "")])
    writer.writerow(["ML_PROVENANCE", "Top-1 Accuracy", f"{metrics.get('top1_spatial_accuracy_pct')}%"])
    writer.writerow(["ML_PROVENANCE", "Top-5 Accuracy", f"{metrics.get('top5_spatial_accuracy_pct')}%"])
    writer.writerow(["ML_PROVENANCE", "Zone Accuracy", f"{metrics.get('zone_level_accuracy_pct')}%"])

    return output.getvalue()
