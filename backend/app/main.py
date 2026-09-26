"""
FastAPI REST Application Entry Point.

Problem Statement:
"Development of a Predictive Analytics Framework for Cybercrime Complaints to Forecast
Likely Cash Withdrawal Locations in Advance, Enabling Generation of Actionable Intelligence
for Timely and Proactive Cybercrime Intervention."

Provides:
- GET  /api/health
- GET  /api/stats
- GET  /api/complaints
- GET  /api/atms
- GET  /api/hotspots
- POST /api/predict
- GET  /api/predictions
- GET  /api/model-info
"""

import json
import sys
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
sys.path.insert(0, str(BASE_DIR))

# Database and Schemas
from backend.app.database import get_db_connection
from backend.app.ml_engine import ml_engine
from backend.app.schemas import (
    ATMLocationResponse,
    ComplaintResponse,
    HotspotZone,
    ModelInfoResponse,
    PredictionRequest,
    PredictionResponse,
    StatsResponse,
)

# App instance
app = FastAPI(
    title="Cybercrime Cash Withdrawal Predictive Analytics Framework",
    description="Forecast likely cybercrime cash withdrawal ATM locations in advance for proactive intervention.",
    version="1.0.0",
)

# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ==============================================================================
# CORS CONFIGURATION (STRICTLY ISOLATED FOR LOCAL DEVELOPMENT/TESTING)
# ==============================================================================
ALLOW_DEV_CORS = True

if ALLOW_DEV_CORS:
    # WARNING: This wildcard configuration is strictly for local prototyping and development.
    # In a production environment, this must be restricted to explicit, trusted domain origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


# ==============================================================================
# API & DASHBOARD ENDPOINTS
# ==============================================================================
@app.get("/", tags=["Dashboard"])
def serve_dashboard():
    """Serves the main interactive dashboard interface."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "status": "ONLINE",
        "framework": "Cybercrime Predictive Analytics Framework",
        "documentation": "/docs",
        "api_prefix": "/api",
    }


@app.get("/api/health", tags=["Health"])
def health_check():
    return {"status": "HEALTHY", "version": "1.0.0"}


@app.get("/api/stats", response_model=StatsResponse, tags=["Analytics"])
def get_dashboard_stats():
    """Returns high-level KPI metrics for the executive dashboard."""
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM complaints;")
        total_cmps = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM cash_out_events;")
        total_cashouts = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM atm_locations;")
        active_atms = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM predictions;")
        total_preds = cur.fetchone()[0]

        # Breakdowns
        cur.execute("SELECT crime_category, COUNT(*) FROM complaints GROUP BY crime_category;")
        cat_counts = dict(cur.fetchall())

        cur.execute("SELECT payment_channel, COUNT(*) FROM complaints GROUP BY payment_channel;")
        chan_counts = dict(cur.fetchall())

        cur.execute("SELECT mule_branch_zone, COUNT(*) FROM complaints GROUP BY mule_branch_zone;")
        zone_counts = dict(cur.fetchall())

        cur.execute("SELECT risk_level, COUNT(*) FROM predictions GROUP BY risk_level;")
        risk_counts = dict(cur.fetchall())

    return {
        "total_complaints": total_cmps,
        "total_cashouts": total_cashouts,
        "active_atms": active_atms,
        "total_predictions": total_preds,
        "crime_category_breakdown": cat_counts,
        "payment_channel_breakdown": chan_counts,
        "zone_distribution": zone_counts,
        "recent_risk_breakdown": risk_counts,
    }


@app.get("/api/complaints", response_model=List[ComplaintResponse], tags=["Complaints"])
def list_complaints(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    zone: Optional[str] = None,
):
    """Retrieves paginated complaints with optional category and zone filters."""
    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    if category:
        query += " AND crime_category = ?"
        params.append(category)
    if zone:
        query += " AND mule_branch_zone = ?"
        params.append(zone)

    query += " ORDER BY complaint_timestamp DESC LIMIT ? OFFSET ?;"
    params.extend([limit, offset])

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

    return [dict(r) for r in rows]


@app.get("/api/atms", response_model=List[ATMLocationResponse], tags=["Infrastructure"])
def list_atms():
    """Returns all monitored ATM locations and attributes for interactive map visualization."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM atm_locations ORDER BY historical_cashout_count DESC;")
        rows = cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/api/hotspots", response_model=List[HotspotZone], tags=["Analytics"])
def get_zone_hotspots():
    """Aggregates area-level risk zones across the 5 administrative sectors."""
    centroids = {
        "ZONE_CENTRAL": (28.6300, 77.2200),
        "ZONE_NORTH":   (28.7000, 77.1500),
        "ZONE_SOUTH":   (28.5300, 77.2000),
        "ZONE_EAST":    (28.6200, 77.2900),
        "ZONE_WEST":    (28.6500, 77.1000),
    }

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT zone_id, COUNT(atm_id) as atm_count, SUM(historical_cashout_count) as total_cashouts
            FROM atm_locations
            GROUP BY zone_id;
            """
        )
        rows = cur.fetchall()

    results = []
    for r in rows:
        zid = r["zone_id"]
        total_co = r["total_cashouts"] or 0
        risk = "HIGH" if total_co > 700 else ("ELEVATED" if total_co > 500 else "MODERATE")
        lat, lon = centroids.get(zid, (28.6300, 77.2200))

        results.append({
            "zone_id": zid,
            "atm_count": r["atm_count"],
            "historical_cashouts": total_co,
            "active_risk_level": risk,
            "center_latitude": lat,
            "center_longitude": lon,
        })
    return results


@app.post("/api/predict", response_model=PredictionResponse, status_code=status.HTTP_200_OK, tags=["Predictive Analytics"])
def predict_cashout_location(request: PredictionRequest):
    """
    Executes real-time inference on a new cybercrime complaint:
    1. Preprocessing (Frozen P1 transformer)
    2. Calibrated Spatial Inference (P(ATM = k))
    3. Temporal Window Forecasting (IQR bounds)
    4. Point-in-Time Explainability Audit
    5. Actionable risk assignment & database logging
    """
    try:
        with get_db_connection() as conn:
            result = ml_engine.predict(request.model_dump(), conn)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference execution failed: {str(e)}")


@app.get("/api/predictions", tags=["Predictive Analytics"])
def list_predictions(limit: int = Query(25, ge=1, le=100)):
    """Retrieves the history of generated actionable intelligence alerts."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM predictions ORDER BY prediction_timestamp DESC LIMIT ?;", (limit,))
        rows = cur.fetchall()

    results = []
    for r in rows:
        d = dict(r)
        d["top_candidates"] = json.loads(d["top_candidates_json"])
        d["explanation_codes"] = json.loads(d["explanation_codes_json"])
        if "priority_reasons_json" in d and d["priority_reasons_json"]:
            try:
                d["priority_reasons"] = json.loads(d["priority_reasons_json"])
            except Exception:
                d["priority_reasons"] = []
        else:
            d["priority_reasons"] = []
        d["priority_score"] = d.get("priority_score", 0) or 0
        d["priority_level"] = d.get("priority_level", "LOW") or "LOW"
        results.append(d)
    return results


@app.get("/api/model-info", response_model=ModelInfoResponse, tags=["Predictive Analytics"])
def get_model_information():
    """Serves model provenance, partition boundaries, and verified Phase 2 Partition 3 evaluation metrics."""
    meta = ml_engine.metadata
    if not meta:
        raise HTTPException(status_code=404, detail="Model metadata not found")

    return {
        "model_name": meta.get("model_name", "Cybercrime_Cashout_Spatial_Predictor"),
        "trained_at": meta.get("trained_at", "N/A"),
        "evaluation_partition": meta.get("evaluation_partition", "P3_FUTURE_TEST_ONLY"),
        "p3_eval_metrics": meta.get("p3_eval_metrics", {}),
        "partition_sizes": meta.get("partition_sizes", {}),
        "chronological_boundaries": meta.get("chronological_boundaries", {}),
    }
