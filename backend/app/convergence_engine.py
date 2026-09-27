"""
Repeated ATM and Zone Convergence Detection Engine.

Detects spatial convergence where multiple independent cybercrime complaints,
predictive inferences, or cash-out events repeatedly point toward the same ATM kiosk
or concentrate within the same administrative zone across a rolling time window.
"""

from datetime import datetime, timedelta
import sqlite3
from typing import Any, Dict, List, Optional


ZONE_CENTROIDS = {
    "ZONE_CENTRAL": (28.6300, 77.2200),
    "ZONE_NORTH":   (28.7000, 77.1500),
    "ZONE_SOUTH":   (28.5300, 77.2000),
    "ZONE_EAST":    (28.6200, 77.2900),
    "ZONE_WEST":    (28.6500, 77.1000),
}

ZONE_NAMES = {
    "ZONE_CENTRAL": "Zone Central (Commercial Core)",
    "ZONE_NORTH":   "Zone North (Transport Nexus)",
    "ZONE_SOUTH":   "Zone South (Institutional Hub)",
    "ZONE_EAST":    "Zone East (Industrial Fringe)",
    "ZONE_WEST":    "Zone West (Market Corridor)",
}


def compute_atm_convergence_score(
    total_matches: int,
    time_span_hours: float,
    avg_priority: float,
    has_ground_truth_cashout: bool,
) -> tuple[int, str]:
    """
    Computes a deterministic 0-100 convergence score and severity level
    for repeated convergence on the exact same ATM.
    """
    # 1. Volume score (up to 40 pts)
    if total_matches >= 4:
        vol_score = 40
    elif total_matches == 3:
        vol_score = 30
    elif total_matches == 2:
        vol_score = 20
    else:
        vol_score = 10

    # 2. Temporal velocity score (up to 30 pts)
    if time_span_hours <= 6.0:
        vel_score = 30
    elif time_span_hours <= 18.0:
        vel_score = 20
    elif time_span_hours <= 36.0:
        vel_score = 12
    else:
        vel_score = 5

    # 3. Priority / Confidence score (up to 20 pts)
    if avg_priority >= 75.0:
        prio_score = 20
    elif avg_priority >= 50.0:
        prio_score = 12
    else:
        prio_score = 5

    # 4. Ground-truth cross-corroboration (up to 10 pts)
    corr_score = 10 if has_ground_truth_cashout else 0

    total_score = min(100, vol_score + vel_score + prio_score + corr_score)

    if total_score >= 75:
        severity = "CRITICAL"
    elif total_score >= 55:
        severity = "HIGH"
    elif total_score >= 35:
        severity = "ELEVATED"
    else:
        severity = "MODERATE"

    return total_score, severity


def compute_zone_convergence_score(
    total_matches: int,
    distinct_atms_count: int,
    time_span_hours: float,
    avg_priority: float,
) -> tuple[int, str]:
    """
    Computes a deterministic 0-100 convergence score and severity level
    for repeated convergence across multiple ATMs in the same zone.
    """
    # 1. Volume score (up to 35 pts)
    if total_matches >= 5:
        vol_score = 35
    elif total_matches in (3, 4):
        vol_score = 25
    else:
        vol_score = 15

    # 2. Multi-ATM dispersion score (up to 25 pts)
    if distinct_atms_count >= 3:
        disp_score = 25
    elif distinct_atms_count == 2:
        disp_score = 18
    else:
        disp_score = 10

    # 3. Temporal velocity score (up to 20 pts)
    if time_span_hours <= 12.0:
        vel_score = 20
    elif time_span_hours <= 24.0:
        vel_score = 14
    elif time_span_hours <= 48.0:
        vel_score = 8
    else:
        vel_score = 4

    # 4. Priority score (up to 20 pts)
    if avg_priority >= 75.0:
        prio_score = 20
    elif avg_priority >= 50.0:
        prio_score = 12
    else:
        prio_score = 5

    total_score = min(100, vol_score + disp_score + vel_score + prio_score)

    if total_score >= 75:
        severity = "CRITICAL"
    elif total_score >= 55:
        severity = "HIGH"
    elif total_score >= 35:
        severity = "ELEVATED"
    else:
        severity = "MODERATE"

    return total_score, severity


def detect_repeated_convergence(
    db_conn: sqlite3.Connection,
    window_hours: int = 48,
    min_matches: int = 2,
    target_type: str = "all",
    zone: Optional[str] = None,
    reference_timestamp: Optional[str] = None,
) -> dict:
    """
    Analyzes historical complaints, active predictive inferences, and confirmed cash-outs
    to detect repeated spatial convergence on specific ATMs or geographic zones.

    Parameters:
        db_conn: sqlite3.Connection to database
        window_hours: Rolling time window in hours (default: 48)
        min_matches: Minimum events or predictions required to trigger convergence (default: 2)
        target_type: 'all', 'atm', or 'zone' (default: 'all')
        zone: Optional zone filter, e.g. 'ZONE_WEST'
        reference_timestamp: Optional reference end timestamp (YYYY-MM-DD HH:MM:SS)

    Returns:
        dict: Structured ConvergenceResponse containing detected repeated convergences.
    """
    cur = db_conn.cursor()

    # 1. Establish window boundaries
    if reference_timestamp and isinstance(reference_timestamp, str):
        ref_dt = datetime.fromisoformat(reference_timestamp.replace(" ", "T"))
    else:
        cur.execute("SELECT MAX(prediction_timestamp) FROM predictions;")
        max_pred = cur.fetchone()[0]
        if max_pred:
            ref_dt = datetime.fromisoformat(max_pred.replace(" ", "T"))
        else:
            cur.execute("SELECT MAX(withdrawal_timestamp) FROM cash_out_events;")
            max_co = cur.fetchone()[0]
            if max_co:
                ref_dt = datetime.fromisoformat(max_co.replace(" ", "T"))
            else:
                ref_dt = datetime.now()

    start_dt = ref_dt - timedelta(hours=window_hours)
    w_start = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    w_end = ref_dt.strftime("%Y-%m-%d %H:%M:%S")

    # 2. Query predictions in rolling window
    cur.execute(
        """
        SELECT p.prediction_id, p.complaint_id, p.predicted_atm_id, p.predicted_zone_id,
               p.prediction_timestamp, p.priority_score, a.bank_code, a.latitude, a.longitude,
               a.location_type
        FROM predictions p
        JOIN atm_locations a ON p.predicted_atm_id = a.atm_id
        WHERE p.prediction_timestamp >= ? AND p.prediction_timestamp <= ?
        ORDER BY p.prediction_timestamp DESC;
        """,
        (w_start, w_end),
    )
    pred_rows = cur.fetchall()

    predictions = [
        {
            "prediction_id": r[0],
            "complaint_id": r[1],
            "atm_id": r[2],
            "zone_id": r[3],
            "timestamp": r[4],
            "priority_score": r[5] or 0,
            "bank_code": r[6],
            "latitude": r[7],
            "longitude": r[8],
            "location_type": r[9],
            "is_prediction": True,
            "is_cashout": False,
        }
        for r in pred_rows
    ]

    # 3. Query cash-out events in window (if any)
    cur.execute(
        """
        SELECT e.event_id, e.complaint_id, e.atm_id, e.withdrawal_timestamp, e.withdrawal_amount,
               a.zone_id, a.bank_code, a.latitude, a.longitude
        FROM cash_out_events e
        JOIN atm_locations a ON e.atm_id = a.atm_id
        WHERE e.withdrawal_timestamp >= ? AND e.withdrawal_timestamp <= ?
        ORDER BY e.withdrawal_timestamp DESC;
        """,
        (w_start, w_end),
    )
    cashout_rows = cur.fetchall()

    cashouts = [
        {
            "event_id": r[0],
            "complaint_id": r[1],
            "atm_id": r[2],
            "timestamp": r[3],
            "amount": r[4] or 0.0,
            "zone_id": r[5],
            "bank_code": r[6],
            "latitude": r[7],
            "longitude": r[8],
            "priority_score": 0,
            "is_prediction": False,
            "is_cashout": True,
        }
        for r in cashout_rows
    ]

    all_incidents = predictions + cashouts

    detected_convergences: List[Dict[str, Any]] = []

    # ==========================================================================
    # A. REPEATED ATM CONVERGENCE DETECTION
    # ==========================================================================
    if target_type in ("all", "atm"):
        by_atm: Dict[str, List[Dict[str, Any]]] = {}
        for inc in all_incidents:
            aid = inc["atm_id"]
            if aid not in by_atm:
                by_atm[aid] = []
            by_atm[aid].append(inc)

        for aid, items in by_atm.items():
            zid = items[0]["zone_id"]
            if zone and zid != zone:
                continue
            if len(items) < min_matches:
                continue

            timestamps = [it["timestamp"] for it in items]
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            dt_min = datetime.fromisoformat(min_ts.replace(" ", "T"))
            dt_max = datetime.fromisoformat(max_ts.replace(" ", "T"))
            span_hrs = max(0.1, (dt_max - dt_min).total_seconds() / 3600.0)

            pred_items = [it for it in items if it["is_prediction"]]
            co_items = [it for it in items if it["is_cashout"]]
            pred_count = len(pred_items)
            co_count = len(co_items)

            pred_ids = [it["prediction_id"] for it in pred_items if it.get("prediction_id")]
            case_ids = list(set([it["complaint_id"] for it in items if it.get("complaint_id")]))

            prio_scores = [it["priority_score"] for it in pred_items if it.get("priority_score")]
            avg_prio = sum(prio_scores) / len(prio_scores) if prio_scores else 50.0

            score, severity = compute_atm_convergence_score(
                total_matches=len(items),
                time_span_hours=span_hrs,
                avg_priority=avg_prio,
                has_ground_truth_cashout=bool(co_count > 0),
            )

            bank_label = items[0].get("bank_code", "").replace("BANK_", "").replace("_SYNTH", "")
            target_name = f"{aid} ({bank_label} Kiosk)"
            zone_pretty = ZONE_NAMES.get(zid, zid.replace("ZONE_", "Zone ").title())

            cid = f"CONV-ATM-{aid.replace('ATM-', '')}-{dt_max.strftime('%Y%m%d%H%M')}"

            reason = (
                f"Target ATM convergence: {pred_count} prediction alert(s) and {co_count} cash-out event(s) "
                f"converged on {aid} in {zone_pretty} within a {round(span_hrs, 1)}h span "
                f"(average priority: {round(avg_prio)}/100)."
            )

            if severity == "CRITICAL":
                rec = f"Deploy rapid interception team to {aid} immediately. Verify live CCTV feed and secure physical perimeter."
            elif severity == "HIGH":
                rec = f"Dispatch priority patrol to inspect {aid} kiosk perimeter and cross-reference nearby ATM network."
            else:
                rec = f"Maintain elevated surveillance on {aid} and monitor upcoming cybercrime intake queue."

            detected_convergences.append({
                "convergence_id": cid,
                "convergence_type": "ATM_CONVERGENCE",
                "target_id": aid,
                "target_name": target_name,
                "zone_id": zid,
                "total_matches": len(items),
                "prediction_count": pred_count,
                "case_count": len(case_ids) or len(items),
                "involved_atm_ids": [aid],
                "time_window_start": w_start,
                "time_window_end": w_end,
                "time_span_hours": round(span_hrs, 1),
                "convergence_score": int(score),
                "severity_level": severity,
                "supporting_prediction_ids": pred_ids[:10],
                "supporting_case_ids": case_ids[:10],
                "reason": reason,
                "recommended_action": rec,
                "latitude": round(float(items[0]["latitude"]), 6),
                "longitude": round(float(items[0]["longitude"]), 6),
            })

    # ==========================================================================
    # B. REPEATED ZONE CONVERGENCE DETECTION
    # ==========================================================================
    if target_type in ("all", "zone"):
        by_zone: Dict[str, List[Dict[str, Any]]] = {}
        for inc in all_incidents:
            zid = inc["zone_id"]
            if zid not in by_zone:
                by_zone[zid] = []
            by_zone[zid].append(inc)

        for zid, items in by_zone.items():
            if zone and zid != zone:
                continue
            if len(items) < min_matches:
                continue

            distinct_atms = sorted(list(set(it["atm_id"] for it in items)))
            timestamps = [it["timestamp"] for it in items]
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            dt_min = datetime.fromisoformat(min_ts.replace(" ", "T"))
            dt_max = datetime.fromisoformat(max_ts.replace(" ", "T"))
            span_hrs = max(0.1, (dt_max - dt_min).total_seconds() / 3600.0)

            pred_items = [it for it in items if it["is_prediction"]]
            co_items = [it for it in items if it["is_cashout"]]
            pred_count = len(pred_items)
            co_count = len(co_items)

            pred_ids = [it["prediction_id"] for it in pred_items if it.get("prediction_id")]
            case_ids = list(set([it["complaint_id"] for it in items if it.get("complaint_id")]))

            prio_scores = [it["priority_score"] for it in pred_items if it.get("priority_score")]
            avg_prio = sum(prio_scores) / len(prio_scores) if prio_scores else 50.0

            score, severity = compute_zone_convergence_score(
                total_matches=len(items),
                distinct_atms_count=len(distinct_atms),
                time_span_hours=span_hrs,
                avg_priority=avg_prio,
            )

            zone_pretty = ZONE_NAMES.get(zid, zid.replace("ZONE_", "Zone ").title())
            cid = f"CONV-ZONE-{zid.replace('ZONE_', '')[:2]}-{dt_max.strftime('%Y%m%d%H%M')}"

            reason = (
                f"Regional corridor convergence: {len(items)} incidents ({pred_count} alerts, {co_count} cashouts) "
                f"concentrated across {len(distinct_atms)} ATM(s) in {zone_pretty} within {round(span_hrs, 1)}h, "
                f"indicating multi-kiosk cash extraction pressure."
            )

            atm_preview = ", ".join(distinct_atms[:3])
            if len(distinct_atms) > 3:
                atm_preview += f" (+{len(distinct_atms) - 3} more)"

            if severity == "CRITICAL":
                rec = f"Issue regional tactical corridor alert across {zone_pretty}. Coordinate mobile interception patrolling ({atm_preview})."
            elif severity == "HIGH":
                rec = f"Deploy mobile patrol unit to monitor high-risk ATMs in {zone_pretty} ({atm_preview}) and alert local bank branches."
            else:
                rec = f"Maintain enhanced situational awareness across {zone_pretty} ATMs during upcoming operational shift."

            lat, lon = ZONE_CENTROIDS.get(zid, (float(items[0]["latitude"]), float(items[0]["longitude"])))

            detected_convergences.append({
                "convergence_id": cid,
                "convergence_type": "ZONE_CONVERGENCE",
                "target_id": zid,
                "target_name": zone_pretty,
                "zone_id": zid,
                "total_matches": len(items),
                "prediction_count": pred_count,
                "case_count": len(case_ids) or len(items),
                "involved_atm_ids": distinct_atms,
                "time_window_start": w_start,
                "time_window_end": w_end,
                "time_span_hours": round(span_hrs, 1),
                "convergence_score": int(score),
                "severity_level": severity,
                "supporting_prediction_ids": pred_ids[:10],
                "supporting_case_ids": case_ids[:10],
                "reason": reason,
                "recommended_action": rec,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
            })

    # Sort convergences descending by convergence_score, then total_matches
    detected_convergences.sort(key=lambda x: (x["convergence_score"], x["total_matches"]), reverse=True)

    atm_count = sum(1 for c in detected_convergences if c["convergence_type"] == "ATM_CONVERGENCE")
    zone_count = sum(1 for c in detected_convergences if c["convergence_type"] == "ZONE_CONVERGENCE")

    return {
        "total_convergences": len(detected_convergences),
        "atm_convergences_count": atm_count,
        "zone_convergences_count": zone_count,
        "window_hours": window_hours,
        "window_start": w_start,
        "window_end": w_end,
        "target_type": target_type,
        "zone_filter": zone,
        "convergences": detected_convergences,
    }
