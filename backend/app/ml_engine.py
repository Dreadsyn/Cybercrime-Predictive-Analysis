"""
Machine Learning Inference & Explainability Service.

Loads Phase 2 artifacts in read-only mode.
Executes calibrated spatial probability forecasting, temporal window estimation,
point-in-time historical explainability audits, and objective risk policy assignments.
"""

import json
import math
import sys
import uuid
from datetime import datetime
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "ml"))
MODELS_DIR = BASE_DIR / "ml" / "models"
DATA_DIR = BASE_DIR / "data"

# Zone centroids for proximity calculation
ZONE_CENTROIDS = {
    "ZONE_CENTRAL": {"lat": 28.6300, "lon": 77.2200},
    "ZONE_NORTH":   {"lat": 28.7000, "lon": 77.1500},
    "ZONE_SOUTH":   {"lat": 28.5300, "lon": 77.2000},
    "ZONE_EAST":    {"lat": 28.6200, "lon": 77.2900},
    "ZONE_WEST":    {"lat": 28.6500, "lon": 77.1000},
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates geodesic distance between two points in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def compute_intervention_priority(
    confidence_score: float,
    reporting_delay_mins: float,
    reported_amount: float,
    payment_channel: str,
    explanation_codes: list,
) -> dict:
    """
    Computes a transparent, deterministic 0–100 operational intervention priority score
    and 2–4 concise explanatory reasons using existing prediction signals.

    Factor Breakdown (Max 100):
    1. Calibrated Spatial Confidence (Max 35 pts)
    2. Temporal & Channel Urgency (Max 30 pts)
    3. Spatial & Target Vulnerability (Max 20 pts)
    4. Financial Exposure (Max 15 pts)
    """
    reasons = []

    # 1. Calibrated Spatial Confidence (Max 35 pts)
    if confidence_score >= 0.25:
        conf_pts = 35
        reasons.append(f"High top-1 spatial concentration ({round(confidence_score * 100, 1)}% probability vs 2% uniform baseline)")
    elif confidence_score >= 0.18:
        conf_pts = 28
        reasons.append(f"Elevated top-1 spatial confidence ({round(confidence_score * 100, 1)}% probability)")
    elif confidence_score >= 0.12:
        conf_pts = 20
        reasons.append(f"Moderate spatial confidence ({round(confidence_score * 100, 1)}% probability)")
    elif confidence_score >= 0.07:
        conf_pts = 12
    else:
        conf_pts = 5

    # 2. Temporal & Channel Urgency (Max 30 pts)
    if reporting_delay_mins <= 30.0:
        delay_pts = 20
        delay_text = f"Rapid reporting ({int(reporting_delay_mins)}m delay) offers immediate interception lead-time"
    elif reporting_delay_mins <= 60.0:
        delay_pts = 15
        delay_text = f"Actionable reporting window ({int(reporting_delay_mins)}m delay)"
    elif reporting_delay_mins <= 120.0:
        delay_pts = 10
        delay_text = f"Standard reporting delay ({int(reporting_delay_mins)}m delay)"
    else:
        delay_pts = 3
        delay_text = f"Extended reporting delay ({int(reporting_delay_mins)}m delay) reduces immediate interception window"

    if payment_channel in ["UPI", "IMPS"] or "HIGH_VELOCITY_CHANNEL" in explanation_codes:
        chan_pts = 10
        chan_text = f"Instant settlement rail ({payment_channel}) implies fast cash-out urgency"
    else:
        chan_pts = 3
        chan_text = f"Batch clearing rail ({payment_channel}) offers extended window"

    urgency_pts = min(30, delay_pts + chan_pts)
    if delay_pts >= 15:
        reasons.append(delay_text)
    elif chan_pts >= 10:
        reasons.append(chan_text)
    else:
        reasons.append(delay_text)

    # 3. Spatial & Target Vulnerability (Max 20 pts)
    spatial_pts = 0
    spatial_reason = None
    if "HOTSPOT_CORRIDOR" in explanation_codes:
        spatial_pts += 8
        spatial_reason = "Target ATM is in an active historical cash-out hotspot corridor"
    if "ON_US_BANK_MATCH" in explanation_codes:
        spatial_pts += 6
        if not spatial_reason:
            spatial_reason = "Mule beneficiary bank matches target ATM network (on-us cash-out pattern)"
    if "GEOGRAPHIC_PROXIMITY" in explanation_codes:
        spatial_pts += 3
        if not spatial_reason:
            spatial_reason = "Target ATM located within 4km proximity of mule branch zone"
    if "LOW_SURVEILLANCE_RISK" in explanation_codes or "HIGH_CAPACITY_TARGET" in explanation_codes:
        spatial_pts += 3
        if not spatial_reason:
            spatial_reason = "Target ATM is a high-capacity or standalone kiosk location"

    spatial_pts = min(20, spatial_pts)
    if spatial_reason:
        reasons.append(spatial_reason)
    else:
        reasons.append("Standard geographic zone routing without specific corridor clustering")

    # 4. Financial Exposure (Max 15 pts)
    if reported_amount >= 100000.0:
        amt_pts = 15
        reasons.append(f"Substantial financial exposure (INR {int(reported_amount):,}) warrants priority response")
    elif reported_amount >= 50000.0:
        amt_pts = 11
        reasons.append(f"Significant reported amount (INR {int(reported_amount):,})")
    elif reported_amount >= 25000.0:
        amt_pts = 7
    else:
        amt_pts = 3

    total_score = min(100, max(0, conf_pts + urgency_pts + spatial_pts + amt_pts))

    if total_score >= 80:
        priority_level = "CRITICAL"
    elif total_score >= 60:
        priority_level = "HIGH"
    elif total_score >= 40:
        priority_level = "MEDIUM"
    else:
        priority_level = "LOW"

    selected_reasons = reasons[:4]
    if len(selected_reasons) < 2:
        selected_reasons.append(f"Overall operational priority rated {priority_level} based on multi-factor triage")

    return {
        "priority_score": int(total_score),
        "priority_level": priority_level,
        "priority_reasons": selected_reasons,
    }


class MLEngine:
    """Singleton service to load models and run inference."""

    def __init__(self):
        self.calibrated_clf = None
        self.preprocessor = None
        self.temporal_model = None
        self.metadata = None
        self.atm_cache = {}
        self.load_artifacts()
        try:
            from backend.app.database import ensure_db_schema
            ensure_db_schema()
        except Exception:
            pass

    def load_artifacts(self):
        print(f"Loading Phase 2 ML artifacts from {MODELS_DIR} (Read-Only)...")
        classifier_path = MODELS_DIR / "spatial_atm_classifier.joblib"
        preprocessor_path = MODELS_DIR / "feature_preprocessor.joblib"
        temporal_path = MODELS_DIR / "temporal_window_estimator.joblib"
        meta_path = MODELS_DIR / "model_metadata.json"

        assert classifier_path.exists(), f"Missing {classifier_path}"
        assert preprocessor_path.exists(), f"Missing {preprocessor_path}"
        assert temporal_path.exists(), f"Missing {temporal_path}"
        assert meta_path.exists(), f"Missing {meta_path}"

        self.calibrated_clf = joblib.load(classifier_path)
        self.preprocessor = joblib.load(preprocessor_path)
        self.temporal_model = joblib.load(temporal_path)

        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        print("  [OK] ML artifacts loaded successfully.")

    def get_atm_info(self, atm_id: str, db_conn) -> dict:
        """Retrieves static metadata for an ATM with memory caching."""
        if atm_id in self.atm_cache:
            return self.atm_cache[atm_id]

        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM atm_locations WHERE atm_id = ?;", (atm_id,))
        row = cursor.fetchone()
        if row:
            info = dict(row)
            self.atm_cache[atm_id] = info
            return info
        return {
            "atm_id": atm_id,
            "bank_code": "UNKNOWN",
            "zone_id": "UNKNOWN",
            "location_type": "UNKNOWN",
            "cash_capacity_level": "UNKNOWN",
            "latitude": 28.6300,
            "longitude": 77.2200,
        }

    def predict(self, payload: dict, db_conn) -> dict:
        """
        Executes full inference workflow for an incoming complaint:
        1. Preprocessing
        2. Calibrated Spatial Inference
        3. Temporal Window Forecasting
        4. Point-in-Time Explainability Audit
        5. Objective Risk Policy Assignment
        6. Persistence to predictions table
        """
        # Form complaint timestamp
        complaint_ts = payload.get("complaint_timestamp")
        if not complaint_ts:
            complaint_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        complaint_id = payload.get("complaint_id") or f"CMP-LIVE-{uuid.uuid4().hex[:6].upper()}"

        # 1. Prepare Feature Input DataFrame
        feature_dict = {
            "crime_category": payload["crime_category"],
            "payment_channel": payload["payment_channel"],
            "mule_account_tier": payload["mule_account_tier"],
            "mule_branch_zone": payload["mule_branch_zone"],
            "reported_amount": float(payload["reported_amount"]),
            "reporting_delay_mins": float(payload["reporting_delay_mins"]),
            "incident_hour": int(payload["incident_hour"]),
            "incident_day_of_week": int(payload["incident_day_of_week"]),
        }
        df_input = pd.DataFrame([feature_dict])

        # 2. Transform Features & Run Calibrated Probability Prediction
        X_trans = self.preprocessor.transform(df_input)
        probs = self.calibrated_clf.predict_proba(X_trans)[0]
        classes = self.calibrated_clf.classes_

        # 3. Sort Candidates Descending
        sorted_indices = np.argsort(probs)[::-1]
        top1_idx = sorted_indices[0]
        top1_atm_id = classes[top1_idx]
        confidence_score = float(probs[top1_idx])

        # Top-5 Candidate Ranking
        top_candidates = []
        for rank, idx in enumerate(sorted_indices[:5], start=1):
            atm_cand_id = classes[idx]
            atm_meta = self.get_atm_info(atm_cand_id, db_conn)

            # Query point-in-time cash-out count strictly prior to complaint_ts
            cur = db_conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM cash_out_events WHERE atm_id = ? AND withdrawal_timestamp < ?;",
                (atm_cand_id, complaint_ts),
            )
            pit_count = cur.fetchone()[0]

            top_candidates.append({
                "rank": rank,
                "atm_id": atm_cand_id,
                "bank_code": atm_meta.get("bank_code", "UNKNOWN"),
                "zone_id": atm_meta.get("zone_id", "UNKNOWN"),
                "location_type": atm_meta.get("location_type", "UNKNOWN"),
                "latitude": float(atm_meta.get("latitude", 0.0)),
                "longitude": float(atm_meta.get("longitude", 0.0)),
                "probability": round(float(probs[idx]), 4),
                "historical_cashout_count": int(pit_count),
            })

        top1_meta = self.get_atm_info(top1_atm_id, db_conn)
        predicted_zone_id = top1_meta.get("zone_id", "ZONE_CENTRAL")

        # 4. Temporal Window Forecasting
        from ml.train_model import predict_temporal_window
        w_start, w_end = predict_temporal_window(
            complaint_ts,
            payload["crime_category"],
            payload["payment_channel"],
            self.temporal_model,
        )
        predicted_window_start = w_start.strftime("%Y-%m-%d %H:%M:%S")
        predicted_window_end = w_end.strftime("%Y-%m-%d %H:%M:%S")

        # 5. Point-in-Time Explainability Audit (Top-1 ATM)
        explanation_codes = []
        # A. On-Us Bank Match
        if payload.get("mule_bank_code") == top1_meta.get("bank_code"):
            explanation_codes.append("ON_US_BANK_MATCH")

        # B. High Velocity Channel
        if payload.get("payment_channel") in ["UPI", "IMPS"] and float(payload.get("reporting_delay_mins", 0)) <= 60.0:
            explanation_codes.append("HIGH_VELOCITY_CHANNEL")

        # C. Hotspot Corridor (Point-in-Time)
        top1_pit_count = top_candidates[0]["historical_cashout_count"]
        if top1_pit_count >= 10:
            explanation_codes.append("HOTSPOT_CORRIDOR")

        # D. High Capacity Target
        if float(payload.get("reported_amount", 0)) >= 50000.0 and top1_meta.get("cash_capacity_level") == "HIGH":
            explanation_codes.append("HIGH_CAPACITY_TARGET")

        # E. Low Surveillance Risk
        if top1_meta.get("location_type") == "STANDALONE_KIOSK":
            explanation_codes.append("LOW_SURVEILLANCE_RISK")

        # F. Geographic Proximity to Mule Branch Zone Centroid
        mule_zone = payload.get("mule_branch_zone", "ZONE_CENTRAL")
        centroid = ZONE_CENTROIDS.get(mule_zone, {"lat": 28.6300, "lon": 77.2200})
        dist_to_cand = haversine_km(centroid["lat"], centroid["lon"], top1_meta["latitude"], top1_meta["longitude"])
        if dist_to_cand <= 4.0:
            explanation_codes.append("GEOGRAPHIC_PROXIMITY")

        if not explanation_codes:
            explanation_codes.append("ZONE_AFFINITY_MATCH")

        # 6. Objective Risk Policy Assignment
        rep_amt = float(payload.get("reported_amount", 0))
        delay = float(payload.get("reporting_delay_mins", 0))

        if rep_amt >= 50000.0 and delay <= 60.0 and confidence_score >= 0.15:
            risk_level = "CRITICAL"
        elif delay <= 120.0 and confidence_score >= 0.12:
            risk_level = "HIGH"
        elif delay <= 240.0 or confidence_score >= 0.08:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"

        # 7. Intervention Priority Scoring (Deterministic 0-100 Operational Triage)
        priority_info = compute_intervention_priority(
            confidence_score=confidence_score,
            reporting_delay_mins=delay,
            reported_amount=rep_amt,
            payment_channel=payload.get("payment_channel", ""),
            explanation_codes=explanation_codes,
        )

        # 8. Investigator Action Playbook Generation (Milestone 1, Feature 7)
        from backend.app.playbook_engine import generate_investigator_playbook
        playbook = generate_investigator_playbook({
            "predicted_atm_id": top1_atm_id,
            "predicted_zone_id": predicted_zone_id,
            "priority_score": priority_info["priority_score"],
            "priority_level": priority_info["priority_level"],
            "confidence_score": confidence_score,
            "predicted_window_start": predicted_window_start,
            "predicted_window_end": predicted_window_end,
            "explanation_codes": explanation_codes,
            "top_candidates": top_candidates,
            "reported_amount": rep_amt,
            "payment_channel": payload.get("payment_channel", "UPI"),
            "mule_bank_code": payload.get("mule_bank_code", ""),
        })

        # 9. Persistence to predictions table
        prediction_id = f"PRED-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        cur = db_conn.cursor()
        cur.execute(
            """
            INSERT INTO predictions (
                prediction_id, complaint_id, prediction_timestamp, predicted_atm_id,
                predicted_zone_id, confidence_score, top_candidates_json,
                predicted_window_start, predicted_window_end, risk_level,
                explanation_codes_json, action_status, priority_score, priority_level,
                priority_reasons_json, playbook_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                prediction_id,
                complaint_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                top1_atm_id,
                predicted_zone_id,
                round(confidence_score, 4),
                json.dumps(top_candidates),
                predicted_window_start,
                predicted_window_end,
                risk_level,
                json.dumps(explanation_codes),
                "NEW_ALERT",
                priority_info["priority_score"],
                priority_info["priority_level"],
                json.dumps(priority_info["priority_reasons"]),
                json.dumps(playbook),
            ),
        )

        return {
            "prediction_id": prediction_id,
            "complaint_id": complaint_id,
            "prediction_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "predicted_atm_id": top1_atm_id,
            "predicted_zone_id": predicted_zone_id,
            "confidence_score": round(confidence_score, 4),
            "top_candidates": top_candidates,
            "predicted_window_start": predicted_window_start,
            "predicted_window_end": predicted_window_end,
            "risk_level": risk_level,
            "explanation_codes": explanation_codes,
            "action_status": "NEW_ALERT",
            "priority_score": priority_info["priority_score"],
            "priority_level": priority_info["priority_level"],
            "priority_reasons": priority_info["priority_reasons"],
            "playbook": playbook,
        }


# Global engine instance
ml_engine = MLEngine()
