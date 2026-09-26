"""
Emerging Cash-Out Cluster Detection Engine (Milestone 1, Feature 1).

Detects spatiotemporal concentration where multiple independent cybercrime complaints
and cash-out events converge on specific ATMs or localized zone corridors within a rolling time window.
"""

import math
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates geodesic distance between two latitude/longitude points in kilometers."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def detect_emerging_clusters(
    db_conn: sqlite3.Connection,
    window_hours: int = 24,
    min_events: int = 2,
    zone: Optional[str] = None,
    source: str = "all",
    reference_timestamp: Optional[str] = None,
) -> dict:
    """
    Scans the cybercrime analytics database to detect emerging cash-out clusters
    across a configurable rolling temporal window.

    Parameters:
        db_conn: sqlite3.Connection to cybercrime_analytics.db
        window_hours: Length of rolling window in hours (default: 24)
        min_events: Minimum incidents required to constitute an emerging cluster (default: 2)
        zone: Optional zone filter (e.g. 'ZONE_WEST')
        source: 'all', 'predictions', or 'cashouts' (default: 'all')
        reference_timestamp: Optional end timestamp of the window (YYYY-MM-DD HH:MM:SS)

    Returns:
        dict: Structured ClusterResponse containing detected clusters and metadata.
    """
    cur = db_conn.cursor()

    # Query operational dataset boundaries
    cur.execute("SELECT MAX(withdrawal_timestamp) FROM cash_out_events;")
    max_co = cur.fetchone()[0]
    cur.execute("SELECT MAX(prediction_timestamp) FROM predictions;")
    max_pred = cur.fetchone()[0]

    all_clusters: List[Dict[str, Any]] = []
    win_start_overall = ""
    win_end_overall = ""

    def process_records(records: List[Dict[str, Any]], cluster_type: str, win_start: str, win_end: str):
        # Group records by (zone_id, atm_id)
        grouped: Dict[tuple, List[Dict[str, Any]]] = {}
        for r in records:
            key = (r["zone_id"], r["atm_id"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r)

        detected = []
        for (zid, aid), items in grouped.items():
            if zone and zid != zone:
                continue
            if len(items) < min_events:
                continue

            timestamps = [it["timestamp"] for it in items]
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            total_amt = sum(it.get("amount", 0.0) or 0.0 for it in items)
            complaint_ids = list({it["complaint_id"] for it in items if it.get("complaint_id")})
            prediction_ids = list({it["prediction_id"] for it in items if it.get("prediction_id")})
            co_count = sum(1 for it in items if it.get("is_cashout"))
            pred_count = sum(1 for it in items if it.get("is_prediction"))

            lat = float(items[0]["lat"])
            lon = float(items[0]["lon"])

            # Proximity check: identify secondary ATMs in same zone within 2.5 km with concurrent activity
            involved_atms = [aid]
            for (other_zid, other_aid), other_items in grouped.items():
                if other_zid == zid and other_aid != aid:
                    dist = haversine_km(lat, lon, float(other_items[0]["lat"]), float(other_items[0]["lon"]))
                    if dist <= 2.5:
                        involved_atms.append(other_aid)

            # Emergence Score calculation (0-100)
            vol_pts = min(45, len(items) * 9)

            dt_first = datetime.fromisoformat(min_ts.replace(" ", "T"))
            dt_last = datetime.fromisoformat(max_ts.replace(" ", "T"))
            span_hrs = max(0.1, (dt_last - dt_first).total_seconds() / 3600.0)

            if span_hrs <= 4.0:
                time_pts = 25
            elif span_hrs <= 12.0:
                time_pts = 18
            else:
                time_pts = 10

            amt_pts = 20 if total_amt >= 100000 else (12 if total_amt >= 50000 else 5)
            max_prio = max([it.get("priority_score", 0) for it in items] or [0])
            prio_pts = 10 if max_prio >= 75 else (5 if max_prio >= 50 else 0)

            score = min(100, vol_pts + time_pts + amt_pts + prio_pts)
            if score >= 75:
                sev = "CRITICAL"
            elif score >= 50:
                sev = "HIGH"
            else:
                sev = "ELEVATED"

            zone_pretty = zid.replace("ZONE_", "Zone ").title()
            date_tag = dt_last.strftime("%Y%m%d")
            clean_atm_code = aid.replace("ATM-", "")
            cid = f"CLUSTER-{date_tag}-{zid.replace('ZONE_', '')[:2]}-{clean_atm_code}"

            recom = (
                f"Establish active patrol perimeter around {aid} in {zone_pretty}. "
                f"Cluster demonstrates convergence of {len(items)} incidents within {round(span_hrs, 1)}h."
            )

            detected.append({
                "cluster_id": cid,
                "cluster_type": cluster_type,
                "zone": zid,
                "primary_atm_id": aid,
                "involved_atm_ids": sorted(list(set(involved_atms))),
                "time_window_start": win_start,
                "time_window_end": win_end,
                "complaint_count": len(complaint_ids) or len(items),
                "complaint_case_count": len(complaint_ids) or len(items),
                "cash_out_event_count": co_count,
                "event_count": len(items),
                "prediction_count": pred_count,
                "total_amount_involved": round(total_amt, 2),
                "severity_level": sev,
                "emergence_score": int(score),
                "supporting_complaint_ids": complaint_ids[:10],
                "supporting_prediction_ids": prediction_ids[:10],
                "center_latitude": round(lat, 6),
                "center_longitude": round(lon, 6),
                "recommendation": recom,
                "recommended_action": recom,
            })

        return detected

    valid_ref_ts = reference_timestamp if (reference_timestamp and isinstance(reference_timestamp, str)) else None

    # 1. Evaluate Prediction Stream
    if source in ["all", "predictions"] and max_pred:
        ref_pred_dt = (
            datetime.fromisoformat(valid_ref_ts.replace(" ", "T"))
            if valid_ref_ts
            else datetime.fromisoformat(max_pred.replace(" ", "T"))
        )
        pred_start_dt = ref_pred_dt - timedelta(hours=window_hours)
        p_win_start = pred_start_dt.strftime("%Y-%m-%d %H:%M:%S")
        p_win_end = ref_pred_dt.strftime("%Y-%m-%d %H:%M:%S")
        win_start_overall = p_win_start
        win_end_overall = p_win_end

        cur.execute(
            """
            SELECT p.prediction_id, p.complaint_id, p.predicted_atm_id, p.prediction_timestamp,
                   p.predicted_zone_id, p.priority_score, a.latitude, a.longitude
            FROM predictions p
            JOIN atm_locations a ON p.predicted_atm_id = a.atm_id
            WHERE p.prediction_timestamp >= ? AND p.prediction_timestamp <= ?
            ORDER BY p.prediction_timestamp DESC;
            """,
            (p_win_start, p_win_end),
        )
        p_records = [
            {
                "prediction_id": r[0],
                "complaint_id": r[1],
                "atm_id": r[2],
                "timestamp": r[3],
                "zone_id": r[4],
                "priority_score": r[5] or 0,
                "lat": r[6],
                "lon": r[7],
                "amount": 0.0,
                "is_prediction": True,
                "is_cashout": False,
            }
            for r in cur.fetchall()
        ]
        all_clusters.extend(process_records(p_records, "PREDICTED_CONVERGENCE", p_win_start, p_win_end))

    # 2. Evaluate Confirmed Cash-Out Events Stream
    if source in ["all", "cashouts"] and max_co:
        if valid_ref_ts:
            ref_co_dt = datetime.fromisoformat(valid_ref_ts.replace(" ", "T"))
        else:
            ref_co_dt = datetime.fromisoformat(max_co.replace(" ", "T"))

        co_start_dt = ref_co_dt - timedelta(hours=window_hours)
        co_win_start = co_start_dt.strftime("%Y-%m-%d %H:%M:%S")
        co_win_end = ref_co_dt.strftime("%Y-%m-%d %H:%M:%S")

        if not win_start_overall:
            win_start_overall = co_win_start
            win_end_overall = co_win_end

        cur.execute(
            """
            SELECT e.event_id, e.complaint_id, e.atm_id, e.withdrawal_timestamp, e.withdrawal_amount,
                   a.zone_id, a.latitude, a.longitude
            FROM cash_out_events e
            JOIN atm_locations a ON e.atm_id = a.atm_id
            WHERE e.withdrawal_timestamp >= ? AND e.withdrawal_timestamp <= ?
            ORDER BY e.withdrawal_timestamp DESC;
            """,
            (co_win_start, co_win_end),
        )
        co_records = [
            {
                "event_id": r[0],
                "complaint_id": r[1],
                "atm_id": r[2],
                "timestamp": r[3],
                "amount": r[4] or 0.0,
                "zone_id": r[5],
                "lat": r[6],
                "lon": r[7],
                "is_prediction": False,
                "is_cashout": True,
                "priority_score": 0,
            }
            for r in cur.fetchall()
        ]
        all_clusters.extend(process_records(co_records, "CONFIRMED_CASHOUT_SURGE", co_win_start, co_win_end))

    # Sort clusters descending by emergence score, then event volume
    all_clusters.sort(key=lambda x: (x["emergence_score"], x["complaint_count"]), reverse=True)

    return {
        "total_clusters": len(all_clusters),
        "total_clusters_detected": len(all_clusters),
        "window_hours": window_hours,
        "rolling_window_hours": window_hours,
        "window_start": win_start_overall or "",
        "window_end": win_end_overall or "",
        "reference_timestamp": win_end_overall or "",
        "active_zone_filter": zone,
        "source_evaluated": source,
        "clusters": all_clusters,
    }
