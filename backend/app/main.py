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
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
sys.path.insert(0, str(BASE_DIR))

# Database and Schemas
from backend.app.cluster_engine import detect_emerging_clusters
from backend.app.convergence_engine import detect_repeated_convergence
from backend.app.database import ensure_db_schema, get_db_connection, verify_database_readiness
from backend.app.ml_engine import ml_engine
from backend.app.playbook_engine import generate_investigator_playbook
from backend.app.case_engine import (
    get_case_by_id,
    list_operational_cases,
    transition_case_status,
)
from backend.app.schemas import (
    ATMLocationResponse,
    CaseResponse,
    CaseStatusUpdateRequest,
    ClusterResponse,
    ComplaintResponse,
    ConvergenceResponse,
    HotspotZone,
    InvestigatorPlaybook,
    ModelInfoResponse,
    PlaybookRequest,
    PredictionRequest,
    PredictionResponse,
    RepeatedConvergence,
    StatsResponse,
)

# App instance
app = FastAPI(
    title="Cybercrime Cash Withdrawal Predictive Analytics Framework",
    description="Forecast likely cybercrime cash withdrawal ATM locations in advance for proactive intervention.",
    version="1.0.0",
)

# Ensure database schema is backwards-compatible on startup
ensure_db_schema()


# ==============================================================================
# EXCEPTION HANDLERS (SANITIZED, SECURE ERROR RESPONSES)
# ==============================================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Sanitizes Pydantic input validation errors into structured, human-readable messages
    without exposing internal Python tracebacks or implementation details.
    """
    field_errors = {}
    error_messages = []

    for err in exc.errors():
        loc = err.get("loc", [])
        field = str(loc[-1]) if loc else "field"
        raw_msg = err.get("msg", "Invalid input value.")
        if raw_msg.startswith("Value error, "):
            raw_msg = raw_msg[len("Value error, "):]
        field_errors[field] = raw_msg
        error_messages.append(f"{field}: {raw_msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": "; ".join(error_messages) if error_messages else "Invalid input data provided.",
            "field_errors": field_errors,
        },
    )


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """
    Standardizes HTTP error responses with clean, actionable messages.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Request Failed" if exc.status_code < 500 else "Service Unavailable",
            "detail": str(exc.detail),
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Catches unhandled internal exceptions, strictly preventing tracebacks, SQLite errors,
    or internal server details from leaking to the client.
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An internal operational error occurred while processing the request. Please contact system administration.",
        },
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


@app.get("/api/analytics/clusters", response_model=ClusterResponse, tags=["Analytics"])
def get_emerging_clusters(
    window_hours: int = Query(24, ge=1, le=168, description="Rolling time window length in hours"),
    min_events: int = Query(2, ge=2, le=50, description="Minimum events to form an emerging cluster"),
    zone: Optional[str] = Query(None, description="Optional zone filter, e.g. ZONE_WEST"),
    source: str = Query("all", description="Source data: 'all', 'predictions', or 'cashouts'"),
    reference_timestamp: Optional[str] = Query(None, description="Optional custom reference end timestamp (YYYY-MM-DD HH:MM:SS)"),
):
    """
    Detects emerging cash-out clusters across a configurable rolling temporal window.
    Identifies localized concentration around ATM/ATM-zone locations.
    """
    try:
        actual_window = window_hours if isinstance(window_hours, int) else getattr(window_hours, "default", 24)
        actual_min = min_events if isinstance(min_events, int) else getattr(min_events, "default", 2)
        actual_zone = zone if isinstance(zone, str) else getattr(zone, "default", None)
        if not isinstance(actual_zone, str):
            actual_zone = None
        actual_source = source if isinstance(source, str) else getattr(source, "default", "all")
        if not isinstance(actual_source, str):
            actual_source = "all"
        actual_ref = reference_timestamp if isinstance(reference_timestamp, str) else getattr(reference_timestamp, "default", None)
        if not isinstance(actual_ref, str):
            actual_ref = None

        with get_db_connection() as conn:
            result = detect_emerging_clusters(
                db_conn=conn,
                window_hours=actual_window,
                min_events=actual_min,
                zone=actual_zone,
                source=actual_source,
                reference_timestamp=actual_ref,
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cluster detection failed: {str(e)}")


@app.get("/api/analytics/convergences", response_model=ConvergenceResponse, tags=["Analytics"])
def get_repeated_convergences(
    window_hours: int = Query(48, ge=1, le=168, description="Rolling time window length in hours"),
    min_matches: int = Query(2, ge=2, le=50, description="Minimum events or predictions required to trigger convergence"),
    target_type: str = Query("all", description="Target type filter: 'all', 'atm', or 'zone'"),
    zone: Optional[str] = Query(None, description="Optional zone filter, e.g. ZONE_WEST"),
    reference_timestamp: Optional[str] = Query(None, description="Optional custom reference end timestamp (YYYY-MM-DD HH:MM:SS)"),
):
    """
    Detects repeated spatial convergence where multiple recent cases or predictions
    point toward the same ATM kiosk or concentrate within the same administrative zone.
    """
    try:
        actual_window = window_hours if isinstance(window_hours, int) else getattr(window_hours, "default", 48)
        actual_min = min_matches if isinstance(min_matches, int) else getattr(min_matches, "default", 2)
        actual_type = target_type if isinstance(target_type, str) else getattr(target_type, "default", "all")
        if not isinstance(actual_type, str):
            actual_type = "all"
        actual_zone = zone if isinstance(zone, str) else getattr(zone, "default", None)
        if not isinstance(actual_zone, str):
            actual_zone = None
        actual_ref = reference_timestamp if isinstance(reference_timestamp, str) else getattr(reference_timestamp, "default", None)
        if not isinstance(actual_ref, str):
            actual_ref = None

        with get_db_connection() as conn:
            result = detect_repeated_convergence(
                db_conn=conn,
                window_hours=actual_window,
                min_matches=actual_min,
                target_type=actual_type,
                zone=actual_zone,
                reference_timestamp=actual_ref,
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Convergence detection failed: {str(e)}")



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
    # 1. Model service readiness check
    if ml_engine is None or not ml_engine.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictive analytics model engine is not ready or required model artifacts are missing.",
        )

    # 2. Database dependency readiness check
    try:
        with get_db_connection() as conn:
            is_ready, db_err = verify_database_readiness(conn)
            if not is_ready:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=db_err,
                )
            result = ml_engine.predict(request.model_dump(), conn)
            return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Predictive inference execution failed due to an internal system error. Please retry or verify system logs.",
        )


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
        if "playbook_json" in d and d["playbook_json"]:
            try:
                d["playbook"] = json.loads(d["playbook_json"])
            except Exception:
                d["playbook"] = None
        else:
            d["playbook"] = None

        # Alert deduplication and escalation lifecycle fields
        d["alert_state"] = d.get("alert_state", "NEW") or "NEW"
        d["occurrence_count"] = d.get("occurrence_count", 1) or 1
        d["escalation_reason"] = d.get("escalation_reason", "") or ""
        d["parent_alert_id"] = d.get("parent_alert_id", None)
        d["case_id"] = d.get("case_id", None)
        d["case_status"] = d.get("case_status", "NEW_ALERT") or "NEW_ALERT"
        results.append(d)
    return results


# ==============================================================================
# 5. OPERATIONAL CASE LIFECYCLE MANAGEMENT ENDPOINTS
# ==============================================================================
@app.get("/api/cases", response_model=List[CaseResponse], tags=["Case Management"])
def list_cases(
    status: Optional[str] = Query(None, description="Optional status filter: NEW_ALERT, PATROL_DISPATCHED, RESOLVED"),
    limit: int = Query(25, ge=1, le=100),
):
    """Retrieves operational cases generated from predictive alerts."""
    actual_status = status if isinstance(status, str) else getattr(status, "default", None)
    if not isinstance(actual_status, str):
        actual_status = None
    actual_limit = limit if isinstance(limit, int) else getattr(limit, "default", 25)
    with get_db_connection() as conn:
        cases = list_operational_cases(conn, case_status=actual_status, limit=actual_limit)
    return cases


@app.get("/api/cases/{case_id}", response_model=CaseResponse, tags=["Case Management"])
def get_case_details(case_id: str):
    """Retrieves details of a specific operational case."""
    with get_db_connection() as conn:
        case = get_case_by_id(conn, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Operational case '{case_id}' not found.")
    return case


@app.patch("/api/cases/{case_id}/status", response_model=CaseResponse, tags=["Case Management"])
def update_case_status(case_id: str, request: CaseStatusUpdateRequest):
    """Executes valid lifecycle transition: NEW_ALERT -> PATROL_DISPATCHED -> RESOLVED."""
    with get_db_connection() as conn:
        updated = transition_case_status(conn, case_id, request.status, request.notes)
    return updated


@app.post("/api/cases/{case_id}/transition", response_model=CaseResponse, tags=["Case Management"])
def transition_case_endpoint(case_id: str, request: CaseStatusUpdateRequest):
    """Convenience alias for case lifecycle transition."""
    with get_db_connection() as conn:
        updated = transition_case_status(conn, case_id, request.status, request.notes)
    return updated


@app.post("/api/playbook", response_model=InvestigatorPlaybook, status_code=status.HTTP_200_OK, tags=["Predictive Analytics"])
def generate_playbook_endpoint(request: PlaybookRequest):
    """
    Generates a structured, prioritized investigator action playbook
    tailored to the specific prediction, priority triage score, ATM, and risk codes.
    """
    try:
        playbook = generate_investigator_playbook(request.model_dump())
        return playbook
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Playbook generation failed: {str(e)}")


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
