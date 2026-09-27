"""
Automated Test Suite for FastAPI REST Endpoints & Service Layer.

Tests:
1. Health check (/api/health)
2. Dashboard KPIs and distributions (/api/stats)
3. ATM coordinates and metadata (/api/atms)
4. Zone risk hotspots (/api/hotspots)
5. Paginated complaints querying (/api/complaints)
6. Real-time predictive analytics inference (/api/predict)
7. Input schema validation error handling (Pydantic ValidationError)
8. Prediction history retrieval (/api/predictions)
9. Model provenance and verified Phase 2 metrics (/api/model-info)
"""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.exceptions import HTTPException, RequestValidationError
from pydantic import ValidationError

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.main import (
    app,
    generate_playbook_endpoint,
    generic_exception_handler,
    get_dashboard_stats,
    get_emerging_clusters,
    get_model_information,
    get_zone_hotspots,
    health_check,
    list_atms,
    list_complaints,
    list_predictions,
    ml_engine,
    predict_cashout_location,
    serve_dashboard,
    validation_exception_handler,
)
from backend.app.cluster_engine import detect_emerging_clusters
from backend.app.database import get_db_connection, verify_database_readiness
from backend.app.ml_engine import compute_intervention_priority
from backend.app.playbook_engine import generate_investigator_playbook
from backend.app.schemas import ComplaintCreate, PlaybookRequest, PredictionRequest


def test_health_endpoint():
    """Verifies that the API service is online and healthy."""
    data = health_check()
    assert data["status"] == "HEALTHY"
    assert data["version"] == "1.0.0"


def test_stats_endpoint():
    """Verifies executive KPI metrics from SQLite database."""
    data = get_dashboard_stats()
    assert data["total_complaints"] == 4000
    assert data["total_cashouts"] == 3295
    assert data["active_atms"] == 50
    assert "INVESTMENT_FRAUD" in data["crime_category_breakdown"]
    assert "UPI" in data["payment_channel_breakdown"]
    assert "ZONE_CENTRAL" in data["zone_distribution"]


def test_atms_endpoint():
    """Verifies ATM network listing for map rendering."""
    atms = list_atms()
    assert len(atms) == 50
    first_atm = atms[0]
    assert "atm_id" in first_atm
    assert "latitude" in first_atm
    assert "longitude" in first_atm
    assert "bank_code" in first_atm
    assert "zone_id" in first_atm
    assert first_atm["latitude"] > 20.0
    assert first_atm["longitude"] > 70.0


def test_hotspots_endpoint():
    """Verifies aggregated area-level risk zones across 5 sectors."""
    hotspots = get_zone_hotspots()
    assert len(hotspots) == 5
    zone_ids = {h["zone_id"] for h in hotspots}
    assert zone_ids == {"ZONE_CENTRAL", "ZONE_NORTH", "ZONE_SOUTH", "ZONE_EAST", "ZONE_WEST"}


def test_complaints_pagination():
    """Verifies paginated retrieval of complaints with query filters."""
    complaints = list_complaints(limit=15, offset=0, category="INVESTMENT_FRAUD", zone=None)
    assert len(complaints) <= 15
    for c in complaints:
        assert c["crime_category"] == "INVESTMENT_FRAUD"
        assert "complaint_id" in c
        assert "reported_amount" in c


def test_predict_endpoint_valid():
    """Verifies real-time prediction pipeline and actionable intelligence generation."""
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=85000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=35.0,
        incident_hour=15,
        incident_day_of_week=4,
        complaint_timestamp="2026-09-26 15:30:00",
        complaint_id="CMP-TEST-UNIT-001",
    )
    pred = predict_cashout_location(req)

    assert pred["complaint_id"] == "CMP-TEST-UNIT-001"
    assert pred["predicted_atm_id"].startswith("ATM-")
    assert pred["predicted_zone_id"].startswith("ZONE_")
    assert 0.0 <= pred["confidence_score"] <= 1.0
    assert len(pred["top_candidates"]) == 5
    assert pred["risk_level"] in ["CRITICAL", "HIGH", "MODERATE", "LOW"]
    assert len(pred["explanation_codes"]) >= 1
    assert pred["predicted_window_start"] <= pred["predicted_window_end"]

    # Verify candidate probabilities are sorted descending
    cand_probs = [c["probability"] for c in pred["top_candidates"]]
    assert cand_probs == sorted(cand_probs, reverse=True)

    # Milestone 1 Feature 6: Intervention Priority Scoring
    assert isinstance(pred["priority_score"], int)
    assert 0 <= pred["priority_score"] <= 100
    assert pred["priority_level"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    assert isinstance(pred["priority_reasons"], list)
    assert 2 <= len(pred["priority_reasons"]) <= 4

    # Milestone 1 Feature 7: Investigator Action Playbook
    assert "playbook" in pred
    assert pred["playbook"] is not None
    playbook = pred["playbook"]
    assert "disposition" in playbook
    assert "summary" in playbook
    assert playbook["total_actions"] >= 4
    assert len(playbook["actions"]) >= 4
    assert "dispatch_brief" in playbook
    assert pred["predicted_atm_id"] in playbook["dispatch_brief"]

    # Verify structured action contract
    first_action = playbook["actions"][0]
    assert "step" in first_action
    assert "title" in first_action
    assert "action_type" in first_action
    assert "urgency" in first_action
    assert "target" in first_action
    assert "description" in first_action
    assert "rationale" in first_action


def test_playbook_generation_scenarios():
    """Verifies that generate_investigator_playbook produces contextual, prioritized SOP steps."""
    # Critical scenario
    crit_playbook = generate_investigator_playbook({
        "predicted_atm_id": "ATM-WE-047",
        "predicted_zone_id": "ZONE_WEST",
        "priority_score": 88,
        "priority_level": "CRITICAL",
        "confidence_score": 0.25,
        "predicted_window_start": "2026-09-26 15:30:00",
        "predicted_window_end": "2026-09-26 16:15:00",
        "explanation_codes": ["HIGH_VELOCITY_CHANNEL", "HOTSPOT_CORRIDOR", "ON_US_BANK_MATCH"],
        "top_candidates": [
            {"rank": 1, "atm_id": "ATM-WE-047", "zone_id": "ZONE_WEST", "probability": 0.25},
            {"rank": 2, "atm_id": "ATM-WE-048", "zone_id": "ZONE_WEST", "probability": 0.12},
        ],
        "reported_amount": 125000.0,
        "payment_channel": "UPI",
        "mule_bank_code": "BANK_SBI_SYNTH",
    })

    assert crit_playbook["disposition"] == "RAPID_TACTICAL_INTERCEPTION"
    assert crit_playbook["total_actions"] >= 5
    assert crit_playbook["actions"][0]["urgency"] == "IMMEDIATE"
    assert crit_playbook["actions"][0]["action_type"] == "PATROL_DISPATCH"
    assert "ATM-WE-047" in crit_playbook["actions"][0]["target"]

    # Low routine scenario
    low_playbook = generate_investigator_playbook({
        "predicted_atm_id": "ATM-EA-038",
        "predicted_zone_id": "ZONE_EAST",
        "priority_score": 25,
        "priority_level": "LOW",
        "confidence_score": 0.04,
        "predicted_window_start": "2026-09-26 10:00:00",
        "predicted_window_end": "2026-09-26 14:00:00",
        "explanation_codes": ["ZONE_AFFINITY_MATCH"],
        "top_candidates": [
            {"rank": 1, "atm_id": "ATM-EA-038", "zone_id": "ZONE_EAST", "probability": 0.04},
        ],
        "reported_amount": 9000.0,
        "payment_channel": "NEFT",
        "mule_bank_code": "BANK_PNB_SYNTH",
    })

    assert low_playbook["disposition"] == "ROUTINE_AUDIT_LOGGING"
    assert low_playbook["actions"][0]["urgency"] == "STANDARD"
    assert low_playbook["actions"][0]["action_type"] == "ROUTINE_LOG"


def test_playbook_endpoint():
    """Verifies that POST /api/playbook endpoint serves structured playbook schema."""
    req = PlaybookRequest(
        predicted_atm_id="ATM-NO-013",
        predicted_zone_id="ZONE_NORTH",
        risk_level="HIGH",
        priority_level="HIGH",
        priority_score=75,
        confidence_score=0.20,
        predicted_window_start="2026-09-26 12:00:00",
        predicted_window_end="2026-09-26 12:45:00",
        explanation_codes=["HIGH_VELOCITY_CHANNEL", "LOW_SURVEILLANCE_RISK"],
        top_candidates=[
            {"rank": 1, "atm_id": "ATM-NO-013", "zone_id": "ZONE_NORTH", "probability": 0.20},
            {"rank": 2, "atm_id": "ATM-NO-014", "zone_id": "ZONE_NORTH", "probability": 0.10},
        ],
        reported_amount=60000.0,
        payment_channel="IMPS",
        mule_bank_code="BANK_HDFC_SYNTH",
    )
    playbook = generate_playbook_endpoint(req)
    assert playbook["disposition"] == "PRIORITY_PATROL_MONITORING"
    assert playbook["total_actions"] >= 4
    assert len(playbook["actions"]) == playbook["total_actions"]
    assert "ATM-NO-013" in playbook["dispatch_brief"]


def test_intervention_priority_scoring_deterministic_logic():
    """Verifies that compute_intervention_priority is deterministic, explainable, and multi-factor."""
    # Critical intervention case: high amount, immediate reporting, instant rail, high confidence
    crit = compute_intervention_priority(
        confidence_score=0.26,
        reporting_delay_mins=20.0,
        reported_amount=120000.0,
        payment_channel="UPI",
        explanation_codes=["HIGH_VELOCITY_CHANNEL", "HOTSPOT_CORRIDOR", "ON_US_BANK_MATCH"],
    )
    assert crit["priority_score"] >= 80
    assert crit["priority_level"] == "CRITICAL"
    assert 2 <= len(crit["priority_reasons"]) <= 4

    # Low intervention case: small amount, long delay, slow rail, low confidence
    low = compute_intervention_priority(
        confidence_score=0.04,
        reporting_delay_mins=300.0,
        reported_amount=8000.0,
        payment_channel="NEFT",
        explanation_codes=["ZONE_AFFINITY_MATCH"],
    )
    assert low["priority_score"] < 40
    assert low["priority_level"] == "LOW"
    assert 2 <= len(low["priority_reasons"]) <= 4

    # Determinism: exact same inputs produce exact same score and reasons
    crit_repeat = compute_intervention_priority(
        confidence_score=0.26,
        reporting_delay_mins=20.0,
        reported_amount=120000.0,
        payment_channel="UPI",
        explanation_codes=["HIGH_VELOCITY_CHANNEL", "HOTSPOT_CORRIDOR", "ON_US_BANK_MATCH"],
    )
    assert crit == crit_repeat


def test_intervention_priority_boundaries():
    """Verifies that the score stays strictly bounded in [0, 100] across extreme values."""
    # Max bound test
    max_case = compute_intervention_priority(
        confidence_score=1.0,
        reporting_delay_mins=0.0,
        reported_amount=1000000.0,
        payment_channel="UPI",
        explanation_codes=["HOTSPOT_CORRIDOR", "ON_US_BANK_MATCH", "GEOGRAPHIC_PROXIMITY", "LOW_SURVEILLANCE_RISK"],
    )
    assert 0 <= max_case["priority_score"] <= 100

    # Min bound test
    min_case = compute_intervention_priority(
        confidence_score=0.0,
        reporting_delay_mins=9999.0,
        reported_amount=1.0,
        payment_channel="OTHER",
        explanation_codes=[],
    )
    assert 0 <= min_case["priority_score"] <= 100
    assert min_case["priority_level"] == "LOW"
    assert len(min_case["priority_reasons"]) >= 2


def test_predict_endpoint_validation_error():
    """Verifies Pydantic rejects invalid or negative inputs."""
    with pytest.raises(ValidationError):
        PredictionRequest(
            crime_category="INVESTMENT_FRAUD",
            reported_amount=-500.0,  # Negative amount rejected
            payment_channel="UPI",
            mule_bank_code="BANK_SBI_SYNTH",
            mule_account_tier="NEW_DIGITAL",
            mule_branch_zone="ZONE_WEST",
            reporting_delay_mins=35.0,
            incident_hour=15,
            incident_day_of_week=4,
        )


def test_predictions_audit_log():
    """Verifies that generated predictions are persisted and queryable."""
    preds = list_predictions(limit=10)
    assert len(preds) >= 1
    assert "prediction_id" in preds[0]
    assert "top_candidates" in preds[0]
    assert isinstance(preds[0]["top_candidates"], list)
    assert "priority_score" in preds[0]
    assert "priority_level" in preds[0]


def test_model_info_matches_phase2():
    """Verifies that /api/model-info serves immutable Phase 2 Partition 3 metrics."""
    info = get_model_information()
    assert info["evaluation_partition"] == "P3_FUTURE_TEST_ONLY"
    metrics = info["p3_eval_metrics"]
    assert metrics["top1_spatial_accuracy_pct"] == 10.17
    assert metrics["top3_spatial_accuracy_pct"] == 31.71
    assert metrics["top5_spatial_accuracy_pct"] == 41.88
    assert metrics["zone_level_accuracy_pct"] == 68.89
    assert metrics["calibrated_brier_score"] == 0.9726
    assert metrics["calibrated_log_loss"] == 3.5199
    assert metrics["temporal_window_coverage_pct"] == 50.38


def test_dashboard_serve_endpoint():
    """Verifies that root endpoint serves the index.html dashboard file."""
    res = serve_dashboard()
    assert res.status_code == 200
    assert "index.html" in str(res.path)


def test_get_emerging_clusters_endpoint():
    """Verifies that /api/analytics/clusters returns valid cluster intelligence."""
    response = get_emerging_clusters(window_hours=24, min_events=2, source="all")
    assert "total_clusters" in response
    assert "window_hours" in response
    assert response["window_hours"] == 24
    assert "clusters" in response
    assert isinstance(response["clusters"], list)
    assert response["total_clusters"] >= 1
    assert len(response["clusters"]) == response["total_clusters"]

    first = response["clusters"][0]
    assert first["cluster_id"].startswith("CLUSTER-")
    assert first["zone"] in {"ZONE_CENTRAL", "ZONE_NORTH", "ZONE_SOUTH", "ZONE_EAST", "ZONE_WEST"}
    assert first["complaint_case_count"] >= 2
    assert first["event_count"] >= 2
    assert len(first["involved_atm_ids"]) >= 1
    assert 0 <= first["emergence_score"] <= 100
    assert first["severity_level"] in {"CRITICAL", "HIGH", "ELEVATED"}
    assert len(first["recommended_action"]) > 10
    assert "time_window_start" in first
    assert "time_window_end" in first


def test_get_emerging_clusters_filters():
    """Verifies cluster query filters: zone filter, time window, and data source."""
    # Zone filter test
    zone_res = get_emerging_clusters(window_hours=48, min_events=2, zone="ZONE_WEST", source="all")
    assert isinstance(zone_res["clusters"], list)
    for c in zone_res["clusters"]:
        assert c["zone"] == "ZONE_WEST"

    # Source filter tests
    cashout_res = get_emerging_clusters(window_hours=24, min_events=2, source="cashouts")
    assert isinstance(cashout_res["clusters"], list)
    for c in cashout_res["clusters"]:
        assert c["cluster_type"] == "CONFIRMED_CASHOUT_SURGE"

    pred_res = get_emerging_clusters(window_hours=24, min_events=2, source="predictions")
    assert isinstance(pred_res["clusters"], list)
    for c in pred_res["clusters"]:
        assert c["cluster_type"] == "PREDICTED_CONVERGENCE"


def test_cluster_detection_deterministic_logic():
    """Verifies that detect_emerging_clusters is 100% deterministic and reproducible."""
    with get_db_connection() as conn:
        run1 = detect_emerging_clusters(conn, window_hours=24, min_events=2, source="all")
        run2 = detect_emerging_clusters(conn, window_hours=24, min_events=2, source="all")

    assert run1["total_clusters"] == run2["total_clusters"]
    assert len(run1["clusters"]) == len(run2["clusters"])
    for c1, c2 in zip(run1["clusters"], run2["clusters"]):
        assert c1["cluster_id"] == c2["cluster_id"]
        assert c1["zone"] == c2["zone"]
        assert c1["emergence_score"] == c2["emergence_score"]
        assert c1["severity_level"] == c2["severity_level"]
        assert c1["involved_atm_ids"] == c2["involved_atm_ids"]


def test_cluster_detection_threshold_and_empty_handling():
    """Verifies graceful handling of restrictive thresholds and empty result sets."""
    # Impossibly high threshold
    high_thresh = get_emerging_clusters(window_hours=1, min_events=50)
    assert high_thresh["total_clusters"] == 0
    assert high_thresh["clusters"] == []

    # Non-existent zone
    empty_zone = get_emerging_clusters(window_hours=24, min_events=2, zone="ZONE_NON_EXISTENT")
    assert empty_zone["total_clusters"] == 0
    assert empty_zone["clusters"] == []


# ==============================================================================
# FEATURE 3: VALIDATION & ERROR HANDLING TESTS
# ==============================================================================

def test_validation_categorical_domain_rejections():
    """Verifies that invalid categorical values across all fields are strictly rejected."""
    base_kwargs = {
        "crime_category": "INVESTMENT_FRAUD",
        "reported_amount": 50000.0,
        "payment_channel": "UPI",
        "mule_bank_code": "BANK_SBI_SYNTH",
        "mule_account_tier": "NEW_DIGITAL",
        "mule_branch_zone": "ZONE_WEST",
        "reporting_delay_mins": 30.0,
        "incident_hour": 14,
        "incident_day_of_week": 2,
    }

    # Invalid crime category
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "crime_category": "CRYPTO_RANSOM"})
    assert "Invalid crime_category" in str(exc.value)

    # Invalid payment channel
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "payment_channel": "BITCOIN"})
    assert "Invalid payment_channel" in str(exc.value)

    # Invalid mule bank code
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "mule_bank_code": "BANK_UNKNOWN_XYZ"})
    assert "Invalid mule_bank_code" in str(exc.value)

    # Invalid mule branch zone
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "mule_branch_zone": "ZONE_NORTH_EAST"})
    assert "Invalid mule_branch_zone" in str(exc.value)

    # Invalid mule account tier
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "mule_account_tier": "VIP_INVESTOR"})
    assert "Invalid mule_account_tier" in str(exc.value)


def test_validation_numeric_range_rejections():
    """Verifies numeric bounds: positive amount, non-negative delay, hour 0-23, day 0-6."""
    base_kwargs = {
        "crime_category": "INVESTMENT_FRAUD",
        "reported_amount": 50000.0,
        "payment_channel": "UPI",
        "mule_bank_code": "BANK_SBI_SYNTH",
        "mule_account_tier": "NEW_DIGITAL",
        "mule_branch_zone": "ZONE_WEST",
        "reporting_delay_mins": 30.0,
        "incident_hour": 14,
        "incident_day_of_week": 2,
    }

    # Zero amount
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "reported_amount": 0.0})
    assert "greater than 0" in str(exc.value)

    # Negative amount
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "reported_amount": -1500.0})
    assert "greater than 0" in str(exc.value)

    # Negative delay
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "reporting_delay_mins": -10.0})
    assert "greater than or equal to 0" in str(exc.value) or "non-negative" in str(exc.value)

    # Incident hour < 0
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "incident_hour": -1})
    assert "greater than or equal to 0" in str(exc.value) or "between 0 and 23" in str(exc.value)

    # Incident hour > 23
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "incident_hour": 24})
    assert "less than or equal to 23" in str(exc.value) or "between 0 and 23" in str(exc.value)

    # Incident day < 0
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "incident_day_of_week": -1})
    assert "greater than or equal to 0" in str(exc.value) or "between 0 and 6" in str(exc.value)

    # Incident day > 6
    with pytest.raises(ValidationError) as exc:
        PredictionRequest(**{**base_kwargs, "incident_day_of_week": 7})
    assert "less than or equal to 6" in str(exc.value) or "between 0 and 6" in str(exc.value)


def test_validation_missing_required_fields():
    """Verifies that missing required fields trigger Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        PredictionRequest(
            reported_amount=50000.0,
            payment_channel="UPI",
        )


def test_validation_exception_handler_sanitization():
    """Verifies that FastAPI RequestValidationError handler produces clean human-readable JSON."""
    raw_errors = [
        {
            "type": "value_error",
            "loc": ("body", "reported_amount"),
            "msg": "Value error, Reported loss amount must be greater than 0.",
            "input": -500,
        },
        {
            "type": "value_error",
            "loc": ("body", "crime_category"),
            "msg": "Value error, Invalid crime category 'UNKNOWN'. Must be one of ('INVESTMENT_FRAUD', ...)",
            "input": "UNKNOWN",
        },
    ]
    exc = RequestValidationError(raw_errors)
    res = asyncio.run(validation_exception_handler(None, exc))

    assert res.status_code == 422
    body = json.loads(res.body.decode())
    assert body["error"] == "Validation Error"
    assert "reported_amount" in body["field_errors"]
    assert "crime_category" in body["field_errors"]
    assert not body["field_errors"]["reported_amount"].startswith("Value error, ")
    assert "Reported loss amount must be greater than 0." in body["field_errors"]["reported_amount"]
    assert "traceback" not in body
    assert "sqlite" not in body["detail"].lower()


def test_database_readiness_verification_behavior():
    """Verifies that verify_database_readiness validates table presence."""
    with get_db_connection() as conn:
        ready, msg = verify_database_readiness(conn)
        assert ready is True
        assert msg == ""

    # In-memory empty database
    empty_conn = sqlite3.connect(":memory:")
    try:
        ready_empty, msg_empty = verify_database_readiness(empty_conn)
        assert ready_empty is False
        assert "missing required operational tables" in msg_empty.lower()
        assert "atm_locations" in msg_empty
    finally:
        empty_conn.close()


def test_predict_database_unready_raises_503():
    """Verifies that predict_cashout_location raises HTTP 503 if database dependencies are missing."""
    valid_req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=85000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=25.0,
        incident_hour=15,
        incident_day_of_week=4,
    )

    with patch("backend.app.main.verify_database_readiness", return_value=(False, "Missing required operational tables: atm_locations")):
        with pytest.raises(HTTPException) as exc_info:
            predict_cashout_location(valid_req)
        assert exc_info.value.status_code == 503
        assert "Missing required operational tables" in exc_info.value.detail


def test_predict_model_unready_raises_503():
    """Verifies that predict_cashout_location raises HTTP 503 if ML engine is not ready."""
    valid_req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=85000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=25.0,
        incident_hour=15,
        incident_day_of_week=4,
    )

    with patch.object(ml_engine, "is_ready", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            predict_cashout_location(valid_req)
        assert exc_info.value.status_code == 503
        assert "Predictive analytics model engine is not ready" in exc_info.value.detail


def test_generic_exception_handler_sanitizes_internal_errors():
    """Verifies that internal exceptions do not leak SQLite errors or stack traces to clients."""
    sqlite_err = sqlite3.OperationalError("near 'WHERE': syntax error in SELECT * FROM complaints")
    res = asyncio.run(generic_exception_handler(None, sqlite_err))

    assert res.status_code == 500
    body = json.loads(res.body.decode())
    assert body["error"] == "Internal Server Error"
    assert "sqlite" not in body["detail"].lower()
    assert "syntax error" not in body["detail"].lower()
    assert "complaints" not in body["detail"].lower()
    assert "traceback" not in body



