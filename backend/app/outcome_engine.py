"""
Incident Outcome Logging & Interception Feedback Loop Engine.

Lightweight outcome-tracking layer connected to the existing Case Lifecycle:
- Allows investigators to record actual operational outcomes for dispatched cases
- Tracks predicted-vs-actual ATM match, spatial hit verification, and interception success
- Computes aggregate feedback metrics (prediction hit rate, match count, interception rate)
- Operates strictly outside frozen ML models, never auto-retraining or altering ML artifacts
"""

from datetime import datetime
import sqlite3
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status

from backend.app.case_engine import get_case_by_id, transition_case_status
from backend.app.dispatch_engine import get_dispatch_by_case_id


VALID_OUTCOME_STATUSES = {
    "INTERCEPTED_AT_PREDICTED_ATM",
    "INTERCEPTED_AT_OTHER_ATM",
    "NO_CASHOUT",
    "FALSE_ALERT",
    "UNRESOLVED",
}


def generate_outcome_id() -> str:
    """Generates a standardized unique Outcome ID, e.g. OUT-20260929-A1B2C3."""
    date_str = datetime.now().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"OUT-{date_str}-{unique_suffix}"


def _format_outcome_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to format a SQLite outcome row for API responses."""
    d = dict(row_dict)
    d["is_spatial_hit"] = bool(d.get("is_spatial_hit", 0))
    return d


def get_outcome_by_id(db_conn: sqlite3.Connection, outcome_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves an outcome record by its outcome_id."""
    cur = db_conn.cursor()
    cur.execute("SELECT * FROM case_outcomes WHERE outcome_id = ?;", (outcome_id,))
    row = cur.fetchone()
    return _format_outcome_row(dict(row)) if row else None


def get_outcome_by_case_id(db_conn: sqlite3.Connection, case_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the recorded outcome for a specific operational case."""
    cur = db_conn.cursor()
    cur.execute("SELECT * FROM case_outcomes WHERE case_id = ?;", (case_id,))
    row = cur.fetchone()
    return _format_outcome_row(dict(row)) if row else None


def list_case_outcomes(db_conn: sqlite3.Connection, limit: int = 25) -> List[Dict[str, Any]]:
    """Lists recent operational case outcomes."""
    cur = db_conn.cursor()
    lim = limit if isinstance(limit, int) else 25
    cur.execute("SELECT * FROM case_outcomes ORDER BY recorded_timestamp DESC LIMIT ?;", (lim,))
    rows = cur.fetchall()
    return [_format_outcome_row(dict(r)) for r in rows]


def record_or_update_case_outcome(
    db_conn: sqlite3.Connection,
    case_id: str,
    outcome_status_val: str,
    actual_atm_id: Optional[str] = None,
    notes: Optional[str] = "",
    investigator_id: Optional[str] = "INV-DESK-01",
    auto_resolve_case: bool = True,
) -> Dict[str, Any]:
    """
    Records or updates the ground truth outcome for an operational case.
    Calculates spatial match against predicted ATM and optionally marks
    the case lifecycle as RESOLVED.
    """
    clean_status = outcome_status_val.strip().upper() if outcome_status_val else ""
    if clean_status not in VALID_OUTCOME_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid outcome_status '{outcome_status_val}'. Allowed: {', '.join(sorted(VALID_OUTCOME_STATUSES))}",
        )

    # 1. Fetch case record
    case = get_case_by_id(db_conn, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operational case '{case_id}' not found.",
        )

    predicted_atm = case["predicted_atm_id"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 2. Resolve actual ATM and spatial hit flag
    resolved_actual_atm = (actual_atm_id or "").strip() or None
    if clean_status == "INTERCEPTED_AT_PREDICTED_ATM":
        if not resolved_actual_atm:
            resolved_actual_atm = predicted_atm
        is_spatial_hit = 1
    elif clean_status == "INTERCEPTED_AT_OTHER_ATM":
        is_spatial_hit = 1 if (resolved_actual_atm and resolved_actual_atm == predicted_atm) else 0
    else:
        # FALSE_ALERT, NO_CASHOUT, UNRESOLVED can NEVER be a spatial hit
        is_spatial_hit = 0
        resolved_actual_atm = None

    # 3. Guard: Cannot record outcome before patrol dispatch
    dispatch_rec = get_dispatch_by_case_id(db_conn, case_id)
    if not dispatch_rec or dispatch_rec.get("dispatch_status") != "DISPATCHED" or case.get("case_status") == "NEW_ALERT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot record outcome for case '{case_id}' before patrol is dispatched.",
        )
    dispatch_id = dispatch_rec["dispatch_id"]

    # 4. Guard: Final outcome cannot be modified after recording
    existing = get_outcome_by_case_id(db_conn, case_id)
    if existing or case.get("case_status") in ("RESOLVED", "CLOSED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Outcome for case '{case_id}' is finalized and cannot be modified.",
        )

    # 5. Pull linked prediction ID
    prediction_id = case.get("parent_alert_id") or ""
    cur = db_conn.cursor()

    outcome_id = generate_outcome_id()
    cur.execute(
        """
        INSERT INTO case_outcomes (
            outcome_id, case_id, prediction_id, dispatch_id,
            outcome_status, predicted_atm_id, actual_atm_id,
            is_spatial_hit, recorded_timestamp, notes, investigator_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            outcome_id,
            case_id,
            prediction_id,
            dispatch_id,
            clean_status,
            predicted_atm,
            resolved_actual_atm,
            is_spatial_hit,
            now_str,
            notes or f"Outcome logged by {investigator_id or 'investigator'}.",
            investigator_id or "INV-DESK-01",
        ),
    )

    # 6. Advance case lifecycle: resolve to RESOLVED if requested, otherwise advance to OUTCOME_PENDING
    if auto_resolve_case:
        if case.get("case_status") not in ("RESOLVED", "CLOSED"):
            transition_case_status(
                db_conn=db_conn,
                case_id=case_id,
                target_status="RESOLVED",
                notes=f"Outcome recorded: {clean_status} (Spatial hit: {bool(is_spatial_hit)}).",
            )
    elif case.get("case_status") == "PATROL_DISPATCHED":
        transition_case_status(
            db_conn=db_conn,
            case_id=case_id,
            target_status="OUTCOME_PENDING",
            notes=f"Outcome recording in progress: {clean_status}.",
        )

    return get_outcome_by_id(db_conn, outcome_id)


def compute_outcome_metrics(db_conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Computes aggregated operational outcome metrics:
    - Prediction hit rate (predicted vs actual ATM matches)
    - Interception success rate
    - False alert rate
    - Breakdown across all outcome statuses
    """
    cur = db_conn.cursor()

    cur.execute("SELECT COUNT(*) FROM case_outcomes;")
    total_outcomes = cur.fetchone()[0] or 0

    outcome_breakdown = {status_key: 0 for status_key in sorted(VALID_OUTCOME_STATUSES)}

    if total_outcomes == 0:
        return {
            "total_outcomes_recorded": 0,
            "predicted_atm_match_count": 0,
            "prediction_hit_rate_pct": 0.0,
            "interception_success_count": 0,
            "interception_rate_pct": 0.0,
            "false_alert_count": 0,
            "false_alert_rate_pct": 0.0,
            "outcome_breakdown": outcome_breakdown,
        }

    cur.execute(
        """
        SELECT outcome_status, COUNT(*) as cnt
        FROM case_outcomes
        GROUP BY outcome_status;
        """
    )
    for r in cur.fetchall():
        st = r["outcome_status"]
        if st in outcome_breakdown:
            outcome_breakdown[st] = r["cnt"]

    # Spatial hit count (where predicted ATM was the actual cash-out / interception location)
    cur.execute("SELECT COUNT(*) FROM case_outcomes WHERE is_spatial_hit = 1;")
    predicted_atm_matches = cur.fetchone()[0] or 0

    prediction_hit_rate = round((predicted_atm_matches / total_outcomes) * 100, 2)

    interception_success_count = (
        outcome_breakdown.get("INTERCEPTED_AT_PREDICTED_ATM", 0)
        + outcome_breakdown.get("INTERCEPTED_AT_OTHER_ATM", 0)
    )
    interception_rate = round((interception_success_count / total_outcomes) * 100, 2)

    false_alert_count = outcome_breakdown.get("FALSE_ALERT", 0)
    false_alert_rate = round((false_alert_count / total_outcomes) * 100, 2)

    return {
        "total_outcomes_recorded": total_outcomes,
        "predicted_atm_match_count": predicted_atm_matches,
        "prediction_hit_rate_pct": prediction_hit_rate,
        "interception_success_count": interception_success_count,
        "interception_rate_pct": interception_rate,
        "false_alert_count": false_alert_count,
        "false_alert_rate_pct": false_alert_rate,
        "outcome_breakdown": outcome_breakdown,
    }
