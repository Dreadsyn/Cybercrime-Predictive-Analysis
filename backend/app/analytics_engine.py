"""
Intervention Performance & Operational Analytics Engine.

Computes aggregate performance metrics from recorded application data:
- Operational case lifecycle progression (actionable, dispatched, resolved, intercepted)
- Prediction hit rate & predicted-vs-actual ATM spatial matches
- Intervention outcome distributions (intercepted, other ATM, no cashout, false alert, unresolved)
- Operational response latency (Alert -> Dispatch -> Outcome)
- Spatial breakdown by zone and predicted ATM

Operates strictly on recorded operational tables (operational_cases, patrol_dispatches,
case_outcomes, predictions), never inventing synthetic live data or modifying ML models.
"""

from datetime import datetime
import sqlite3
from typing import Any, Dict, List, Optional


def _parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
    """Helper to parse varied SQLite datetime string formats safely."""
    if not ts_str:
        return None
    cleaned = ts_str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(cleaned[:19], fmt)
        except Exception:
            continue
    return None


def get_intervention_performance_analytics(db_conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Computes comprehensive intervention performance and operational analytics
    strictly from recorded SQLite application tables.
    """
    cur = db_conn.cursor()

    # 1. Pipeline Case Counts
    cur.execute("SELECT COUNT(*) FROM operational_cases;")
    total_cases = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM operational_cases WHERE case_status = 'NEW_ALERT';")
    new_alert_cases = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM operational_cases WHERE case_status = 'PATROL_DISPATCHED';")
    patrol_dispatched_cases = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM operational_cases WHERE case_status = 'RESOLVED';")
    resolved_cases = cur.fetchone()[0] or 0

    # Total dispatched includes cases currently dispatched or resolved after dispatch
    dispatched_cases = patrol_dispatched_cases + resolved_cases

    # 2. Outcome Totals & Breakdown
    cur.execute("SELECT COUNT(*) FROM case_outcomes;")
    total_outcomes = cur.fetchone()[0] or 0

    valid_statuses = [
        "INTERCEPTED_AT_PREDICTED_ATM",
        "INTERCEPTED_AT_OTHER_ATM",
        "NO_CASHOUT",
        "FALSE_ALERT",
        "UNRESOLVED",
    ]
    outcome_breakdown = {st: 0 for st in valid_statuses}

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

    cur.execute("SELECT COUNT(*) FROM case_outcomes WHERE is_spatial_hit = 1;")
    predicted_vs_actual_matches = cur.fetchone()[0] or 0

    intercepted_cases = (
        outcome_breakdown.get("INTERCEPTED_AT_PREDICTED_ATM", 0)
        + outcome_breakdown.get("INTERCEPTED_AT_OTHER_ATM", 0)
    )
    unresolved_count = outcome_breakdown.get("UNRESOLVED", 0)
    false_alert_count = outcome_breakdown.get("FALSE_ALERT", 0)
    no_cashout_count = outcome_breakdown.get("NO_CASHOUT", 0)

    spatial_hit_rate_pct = (
        round((predicted_vs_actual_matches / total_outcomes) * 100, 2)
        if total_outcomes > 0
        else 0.0
    )
    interception_success_rate_pct = (
        round((intercepted_cases / total_outcomes) * 100, 2)
        if total_outcomes > 0
        else 0.0
    )

    # 3. Timing Metrics (Alert -> Dispatch -> Outcome)
    cur.execute(
        """
        SELECT 
            c.created_timestamp AS alert_time,
            d.dispatched_timestamp AS dispatch_time,
            o.recorded_timestamp AS outcome_time
        FROM operational_cases c
        LEFT JOIN patrol_dispatches d ON c.case_id = d.case_id
        LEFT JOIN case_outcomes o ON c.case_id = o.case_id;
        """
    )
    rows = cur.fetchall()

    alert_to_dispatch_deltas = []
    dispatch_to_outcome_deltas = []
    alert_to_outcome_deltas = []

    for r in rows:
        dt_alert = _parse_ts(r["alert_time"])
        dt_disp = _parse_ts(r["dispatch_time"])
        dt_out = _parse_ts(r["outcome_time"])

        if dt_alert and dt_disp:
            diff1 = (dt_disp - dt_alert).total_seconds() / 60.0
            if diff1 >= 0:
                alert_to_dispatch_deltas.append(diff1)

        if dt_disp and dt_out:
            diff2 = (dt_out - dt_disp).total_seconds() / 60.0
            if diff2 >= 0:
                dispatch_to_outcome_deltas.append(diff2)

        if dt_alert and dt_out:
            diff3 = (dt_out - dt_alert).total_seconds() / 60.0
            if diff3 >= 0:
                alert_to_outcome_deltas.append(diff3)

    avg_alert_to_dispatch_mins = (
        round(sum(alert_to_dispatch_deltas) / len(alert_to_dispatch_deltas), 1)
        if alert_to_dispatch_deltas
        else 0.0
    )
    avg_dispatch_to_outcome_mins = (
        round(sum(dispatch_to_outcome_deltas) / len(dispatch_to_outcome_deltas), 1)
        if dispatch_to_outcome_deltas
        else 0.0
    )
    avg_alert_to_outcome_mins = (
        round(sum(alert_to_outcome_deltas) / len(alert_to_outcome_deltas), 1)
        if alert_to_outcome_deltas
        else 0.0
    )

    timing_metrics = {
        "avg_alert_to_dispatch_mins": avg_alert_to_dispatch_mins,
        "avg_dispatch_to_outcome_mins": avg_dispatch_to_outcome_mins,
        "avg_alert_to_outcome_mins": avg_alert_to_outcome_mins,
        "sampled_timed_cases": len(alert_to_outcome_deltas) or len(alert_to_dispatch_deltas),
    }

    # 4. Performance by Zone
    cur.execute(
        """
        SELECT 
            c.predicted_zone_id AS zone_id,
            COUNT(DISTINCT c.case_id) AS total_cases,
            SUM(CASE WHEN c.case_status IN ('PATROL_DISPATCHED', 'RESOLVED') THEN 1 ELSE 0 END) AS dispatched_cases,
            SUM(CASE WHEN c.case_status = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved_cases,
            COUNT(DISTINCT o.outcome_id) AS outcomes_logged,
            SUM(CASE WHEN o.is_spatial_hit = 1 THEN 1 ELSE 0 END) AS spatial_hits
        FROM operational_cases c
        LEFT JOIN case_outcomes o ON c.case_id = o.case_id
        GROUP BY c.predicted_zone_id
        ORDER BY total_cases DESC, zone_id ASC;
        """
    )
    zone_rows = cur.fetchall()
    performance_by_zone = []
    for z in zone_rows:
        tot_z = z["total_cases"] or 0
        out_z = z["outcomes_logged"] or 0
        hits_z = z["spatial_hits"] or 0
        hit_rate_z = round((hits_z / out_z) * 100, 1) if out_z > 0 else 0.0
        performance_by_zone.append({
            "zone_id": z["zone_id"],
            "total_cases": tot_z,
            "dispatched_cases": z["dispatched_cases"] or 0,
            "resolved_cases": z["resolved_cases"] or 0,
            "outcomes_logged": out_z,
            "spatial_hits": hits_z,
            "spatial_hit_rate_pct": hit_rate_z,
        })

    # 5. Performance by ATM (where operational cases exist)
    cur.execute(
        """
        SELECT 
            c.predicted_atm_id AS atm_id,
            c.predicted_zone_id AS zone_id,
            COUNT(DISTINCT c.case_id) AS total_cases,
            SUM(CASE WHEN c.case_status IN ('PATROL_DISPATCHED', 'RESOLVED') THEN 1 ELSE 0 END) AS dispatched_cases,
            SUM(CASE WHEN c.case_status = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved_cases,
            COUNT(DISTINCT o.outcome_id) AS outcomes_logged,
            SUM(CASE WHEN o.is_spatial_hit = 1 THEN 1 ELSE 0 END) AS spatial_hits
        FROM operational_cases c
        LEFT JOIN case_outcomes o ON c.case_id = o.case_id
        GROUP BY c.predicted_atm_id, c.predicted_zone_id
        ORDER BY total_cases DESC, outcomes_logged DESC, c.predicted_atm_id ASC
        LIMIT 20;
        """
    )
    atm_rows = cur.fetchall()
    performance_by_atm = []
    for a in atm_rows:
        tot_a = a["total_cases"] or 0
        out_a = a["outcomes_logged"] or 0
        hits_a = a["spatial_hits"] or 0
        hit_rate_a = round((hits_a / out_a) * 100, 1) if out_a > 0 else 0.0
        performance_by_atm.append({
            "atm_id": a["atm_id"],
            "zone_id": a["zone_id"],
            "total_cases": tot_a,
            "dispatched_cases": a["dispatched_cases"] or 0,
            "resolved_cases": a["resolved_cases"] or 0,
            "outcomes_logged": out_a,
            "spatial_hits": hits_a,
            "spatial_hit_rate_pct": hit_rate_a,
        })

    return {
        "generated_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_actionable_cases": total_cases,
        "dispatched_cases": dispatched_cases,
        "resolved_cases": resolved_cases,
        "new_alert_cases": new_alert_cases,
        "intercepted_cases": intercepted_cases,
        "unresolved_count": unresolved_count,
        "false_alert_count": false_alert_count,
        "no_cashout_count": no_cashout_count,
        "total_outcomes_logged": total_outcomes,
        "predicted_vs_actual_matches": predicted_vs_actual_matches,
        "spatial_hit_rate_pct": spatial_hit_rate_pct,
        "interception_success_rate_pct": interception_success_rate_pct,
        "outcome_breakdown": outcome_breakdown,
        "timing": timing_metrics,
        "performance_by_zone": performance_by_zone,
        "performance_by_atm": performance_by_atm,
    }
