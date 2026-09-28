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
    get_repeated_convergences,
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
from backend.app.alert_engine import (
    evaluate_alert_escalation,
    find_active_alert,
    process_alert_lifecycle,
)
from backend.app.cluster_engine import detect_emerging_clusters
from backend.app.convergence_engine import (
    compute_atm_convergence_score,
    compute_zone_convergence_score,
    detect_repeated_convergence,
)
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


# ==============================================================================
# FEATURE 2: REPEATED ATM & ZONE CONVERGENCE TESTS
# ==============================================================================

def test_get_repeated_convergences_endpoint():
    """Verifies that /api/analytics/convergences returns valid convergence intelligence."""
    response = get_repeated_convergences(window_hours=48, min_matches=2, target_type="all")
    assert "total_convergences" in response
    assert response["total_convergences"] >= 1
    assert "atm_convergences_count" in response
    assert "zone_convergences_count" in response
    assert response["atm_convergences_count"] >= 1
    assert response["zone_convergences_count"] >= 1
    assert response["total_convergences"] == response["atm_convergences_count"] + response["zone_convergences_count"]
    assert "convergences" in response
    assert isinstance(response["convergences"], list)
    assert len(response["convergences"]) == response["total_convergences"]

    first = response["convergences"][0]
    assert first["convergence_id"].startswith("CONV-")
    assert first["convergence_type"] in {"ATM_CONVERGENCE", "ZONE_CONVERGENCE"}
    assert "target_id" in first
    assert "target_name" in first
    assert first["zone_id"] in {"ZONE_CENTRAL", "ZONE_NORTH", "ZONE_SOUTH", "ZONE_EAST", "ZONE_WEST"}
    assert first["total_matches"] >= 2
    assert first["prediction_count"] >= 0
    assert first["case_count"] >= 0
    assert len(first["involved_atm_ids"]) >= 1
    assert 0 <= first["convergence_score"] <= 100
    assert first["severity_level"] in {"CRITICAL", "HIGH", "ELEVATED", "MODERATE"}
    assert len(first["reason"]) > 10
    assert len(first["recommended_action"]) > 10
    assert "time_window_start" in first
    assert "time_window_end" in first
    assert first["time_span_hours"] >= 0.0
    assert isinstance(first["supporting_prediction_ids"], list)
    assert isinstance(first["supporting_case_ids"], list)


def test_repeated_convergences_target_type_filters():
    """Verifies target_type filters: 'atm', 'zone', and 'all'."""
    # ATM-only filter
    atm_res = get_repeated_convergences(window_hours=48, min_matches=2, target_type="atm")
    assert atm_res["target_type"] == "atm"
    assert atm_res["zone_convergences_count"] == 0
    assert atm_res["total_convergences"] == atm_res["atm_convergences_count"]
    for c in atm_res["convergences"]:
        assert c["convergence_type"] == "ATM_CONVERGENCE"
        assert c["target_id"].startswith("ATM-")

    # Zone-only filter
    zone_res = get_repeated_convergences(window_hours=48, min_matches=2, target_type="zone")
    assert zone_res["target_type"] == "zone"
    assert zone_res["atm_convergences_count"] == 0
    assert zone_res["total_convergences"] == zone_res["zone_convergences_count"]
    for c in zone_res["convergences"]:
        assert c["convergence_type"] == "ZONE_CONVERGENCE"
        assert c["target_id"].startswith("ZONE_")


def test_repeated_convergences_zone_filter():
    """Verifies filtering by specific geographic zone."""
    west_res = get_repeated_convergences(window_hours=48, min_matches=2, zone="ZONE_WEST")
    assert west_res["zone_filter"] == "ZONE_WEST"
    for c in west_res["convergences"]:
        assert c["zone_id"] == "ZONE_WEST"


def test_repeated_convergences_threshold_and_empty_handling():
    """Verifies graceful handling of restrictive thresholds and empty result sets."""
    # Impossibly high match count
    empty_res = get_repeated_convergences(window_hours=48, min_matches=500)
    assert empty_res["total_convergences"] == 0
    assert empty_res["atm_convergences_count"] == 0
    assert empty_res["zone_convergences_count"] == 0
    assert empty_res["convergences"] == []

    # Non-existent zone
    empty_zone = get_repeated_convergences(window_hours=48, min_matches=2, zone="ZONE_NON_EXISTENT")
    assert empty_zone["total_convergences"] == 0
    assert empty_zone["convergences"] == []


def test_convergence_detection_deterministic_logic():
    """Verifies that detect_repeated_convergence is 100% deterministic and reproducible."""
    with get_db_connection() as conn:
        run1 = detect_repeated_convergence(conn, window_hours=48, min_matches=2, target_type="all")
        run2 = detect_repeated_convergence(conn, window_hours=48, min_matches=2, target_type="all")

    assert run1["total_convergences"] == run2["total_convergences"]
    assert run1["atm_convergences_count"] == run2["atm_convergences_count"]
    assert run1["zone_convergences_count"] == run2["zone_convergences_count"]
    assert len(run1["convergences"]) == len(run2["convergences"])
    for c1, c2 in zip(run1["convergences"], run2["convergences"]):
        assert c1["convergence_id"] == c2["convergence_id"]
        assert c1["target_id"] == c2["target_id"]
        assert c1["convergence_type"] == c2["convergence_type"]
        assert c1["convergence_score"] == c2["convergence_score"]
        assert c1["severity_level"] == c2["severity_level"]
        assert c1["reason"] == c2["reason"]
        assert c1["recommended_action"] == c2["recommended_action"]


def test_convergence_score_helpers_bounds():
    """Verifies that convergence scoring helpers stay strictly within [0, 100] across extremes."""
    # Extreme high ATM case
    score_hi, sev_hi = compute_atm_convergence_score(
        total_matches=20,
        time_span_hours=1.0,
        avg_priority=95.0,
        has_ground_truth_cashout=True,
    )
    assert 0 <= score_hi <= 100
    assert score_hi >= 80
    assert sev_hi == "CRITICAL"

    # Extreme low ATM case
    score_lo, sev_lo = compute_atm_convergence_score(
        total_matches=1,
        time_span_hours=100.0,
        avg_priority=15.0,
        has_ground_truth_cashout=False,
    )
    assert 0 <= score_lo <= 100
    assert score_lo < 35
    assert sev_lo == "MODERATE"

    # Extreme high Zone case
    z_score_hi, z_sev_hi = compute_zone_convergence_score(
        total_matches=30,
        distinct_atms_count=5,
        time_span_hours=2.0,
        avg_priority=90.0,
    )
    assert 0 <= z_score_hi <= 100
    assert z_score_hi >= 80
    assert z_sev_hi == "CRITICAL"

    # Extreme low Zone case
    z_score_lo, z_sev_lo = compute_zone_convergence_score(
        total_matches=1,
        distinct_atms_count=1,
        time_span_hours=200.0,
        avg_priority=10.0,
    )
    assert 0 <= z_score_lo <= 100
    assert z_score_lo < 35
    assert z_sev_lo == "MODERATE"


# ==============================================================================
# 9. ALERT DEDUPLICATION & ESCALATION TESTS
# ==============================================================================

@pytest.fixture(autouse=True)
def clean_alert_test_predictions():
    """Cleans up isolated test prediction records before and after each test."""
    clean_sql = """
        DELETE FROM predictions 
        WHERE complaint_id LIKE 'CMP-TEST-%' 
           OR complaint_id LIKE 'CMP-DEDUP-%' 
           OR complaint_id LIKE 'CMP-SEPARATE-%' 
           OR complaint_id LIKE 'CMP-SURGE-%' 
           OR complaint_id LIKE 'CMP-VEL-%' 
           OR complaint_id LIKE 'CMP-EXP-%';
    """
    with get_db_connection() as conn:
        conn.execute(clean_sql)
    yield
    with get_db_connection() as conn:
        conn.execute(clean_sql)


def test_new_alert_lifecycle_initial():
    """Verifies that an initial predictive inference creates a NEW alert with occurrence count 1."""
    # Ensure fresh ATM target by creating a mock payload
    payload = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=80000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=25.0,
        incident_hour=15,
        incident_day_of_week=4,
        complaint_timestamp="2026-09-20 10:00:00",
        complaint_id="CMP-TEST-NEW-01",
    )
    res = predict_cashout_location(payload)
    assert res["alert_state"] in ("NEW", "REFRESHED", "ESCALATED")
    assert res["occurrence_count"] >= 1
    assert "prediction_id" in res
    assert res["prediction_id"].startswith("PRED-")


def test_alert_deduplication_refreshed_on_subsequent_incident():
    """
    Verifies that a subsequent prediction on the same ATM within the active window
    is deduplicated, refreshing the existing alert and incrementing occurrence_count
    without artificial score inflation.
    """
    ts_base = "2026-09-18 09:00:00"
    ts_later = "2026-09-18 10:30:00"

    with get_db_connection() as conn:
        # 1. First event
        res1 = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-DEDUP-01",
                "predicted_atm_id": "ATM-WE-048",
                "predicted_zone_id": "ZONE_WEST",
                "confidence_score": 0.42,
                "top_candidates": [],
                "predicted_window_start": "2026-09-18 09:30:00",
                "predicted_window_end": "2026-09-18 10:30:00",
                "risk_level": "MODERATE",
                "explanation_codes": ["EXP_CHANNEL_UPI"],
                "priority_score": 45,
                "priority_level": "MEDIUM",
                "priority_reasons": ["Moderate loss amount"],
                "playbook": None,
                "reference_timestamp": ts_base,
            },
            window_hours=24,
        )
        assert res1["alert_state"] == "NEW"
        assert res1["action_status"] == "NEW_ALERT"
        assert res1["occurrence_count"] == 1
        initial_id = res1["prediction_id"]

        # 2. Second event targeting same ATM with similar/lower priority
        res2 = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-DEDUP-02",
                "predicted_atm_id": "ATM-WE-048",
                "predicted_zone_id": "ZONE_WEST",
                "confidence_score": 0.40,
                "top_candidates": [],
                "predicted_window_start": "2026-09-18 11:00:00",
                "predicted_window_end": "2026-09-18 12:00:00",
                "risk_level": "MODERATE",
                "explanation_codes": ["EXP_CHANNEL_UPI"],
                "priority_score": 44,
                "priority_level": "MEDIUM",
                "priority_reasons": ["Moderate loss amount"],
                "playbook": None,
                "reference_timestamp": ts_later,
            },
            window_hours=24,
        )
        assert res2["prediction_id"] == initial_id  # Reused primary alert ID
        assert res2["alert_state"] == "REFRESHED"
        assert res2["action_status"] == "REFRESHED_ALERT"
        assert res2["occurrence_count"] == 2
        assert res2["priority_score"] == 45  # Retained stable score without artificial inflation
        assert "Alert refreshed" in res2["escalation_reason"]


def test_different_atm_same_zone_creates_separate_alert():
    """
    Verifies operational boundary: two complaints pointing to DIFFERENT ATMs
    in the same zone are NOT falsely deduplicated into each other.
    """
    ts = "2026-09-17 12:00:00"

    with get_db_connection() as conn:
        res_atm_a = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-SEPARATE-A",
                "predicted_atm_id": "ATM-NO-011",
                "predicted_zone_id": "ZONE_NORTH",
                "confidence_score": 0.35,
                "top_candidates": [],
                "predicted_window_start": ts,
                "predicted_window_end": ts,
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 50,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts,
            },
            window_hours=24,
        )
        res_atm_b = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-SEPARATE-B",
                "predicted_atm_id": "ATM-NO-012",
                "predicted_zone_id": "ZONE_NORTH",
                "confidence_score": 0.35,
                "top_candidates": [],
                "predicted_window_start": ts,
                "predicted_window_end": ts,
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 50,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts,
            },
            window_hours=24,
        )

        assert res_atm_a["prediction_id"] != res_atm_b["prediction_id"]
        assert res_atm_a["predicted_atm_id"] == "ATM-NO-011"
        assert res_atm_b["predicted_atm_id"] == "ATM-NO-012"
        assert res_atm_a["alert_state"] == "NEW"
        assert res_atm_b["alert_state"] == "NEW"


def test_material_priority_surge_escalation():
    """
    Verifies that an incoming incident with a materially higher priority score (+10 pts)
    and higher priority tier triggers an immediate ESCALATED alert state.
    """
    ts_start = "2026-09-16 08:00:00"
    ts_surge = "2026-09-16 11:00:00"

    with get_db_connection() as conn:
        # Initial lower-priority event
        res_init = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-SURGE-01",
                "predicted_atm_id": "ATM-CE-009",
                "predicted_zone_id": "ZONE_CENTRAL",
                "confidence_score": 0.20,
                "top_candidates": [],
                "predicted_window_start": ts_start,
                "predicted_window_end": ts_start,
                "risk_level": "LOW",
                "explanation_codes": [],
                "priority_score": 30,
                "priority_level": "LOW",
                "priority_reasons": ["Low loss amount"],
                "playbook": None,
                "reference_timestamp": ts_start,
            },
            window_hours=24,
        )
        assert res_init["alert_state"] == "NEW"
        initial_id = res_init["prediction_id"]

        # Surge event: high loss, short delay -> priority score 85, CRITICAL
        res_escalated = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-SURGE-02",
                "predicted_atm_id": "ATM-CE-009",
                "predicted_zone_id": "ZONE_CENTRAL",
                "confidence_score": 0.65,
                "top_candidates": [],
                "predicted_window_start": ts_surge,
                "predicted_window_end": ts_surge,
                "risk_level": "CRITICAL",
                "explanation_codes": ["EXP_FAST_REPORT"],
                "priority_score": 85,
                "priority_level": "CRITICAL",
                "priority_reasons": ["Urgent short delay", "Large financial loss"],
                "playbook": None,
                "reference_timestamp": ts_surge,
            },
            window_hours=24,
        )

        assert res_escalated["prediction_id"] == initial_id
        assert res_escalated["alert_state"] == "ESCALATED"
        assert res_escalated["action_status"] == "ESCALATED_ALERT"
        assert res_escalated["occurrence_count"] == 2
        assert res_escalated["priority_score"] == 85
        assert res_escalated["priority_level"] == "CRITICAL"
        assert "Escalated:" in res_escalated["escalation_reason"]
        assert "Priority tier elevated" in res_escalated["escalation_reason"]
        assert "+55 pts" in res_escalated["escalation_reason"]


def test_high_velocity_repetition_escalation():
    """
    Verifies that 3 repeated incidents mapped to the same ATM within the window
    escalate due to high velocity even if scores are otherwise stable.
    """
    ts1 = "2026-09-15 10:00:00"
    ts2 = "2026-09-15 11:00:00"
    ts3 = "2026-09-15 12:00:00"

    with get_db_connection() as conn:
        res1 = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-VEL-01",
                "predicted_atm_id": "ATM-SO-028",
                "predicted_zone_id": "ZONE_SOUTH",
                "confidence_score": 0.30,
                "top_candidates": [],
                "predicted_window_start": ts1,
                "predicted_window_end": ts1,
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 40,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts1,
            },
            window_hours=24,
        )
        assert res1["occurrence_count"] == 1
        assert res1["alert_state"] == "NEW"

        res2 = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-VEL-02",
                "predicted_atm_id": "ATM-SO-028",
                "predicted_zone_id": "ZONE_SOUTH",
                "confidence_score": 0.30,
                "top_candidates": [],
                "predicted_window_start": ts2,
                "predicted_window_end": ts2,
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 40,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts2,
            },
            window_hours=24,
        )
        assert res2["occurrence_count"] == 2
        assert res2["alert_state"] == "REFRESHED"

        # Third occurrence triggers velocity escalation
        res3 = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-VEL-03",
                "predicted_atm_id": "ATM-SO-028",
                "predicted_zone_id": "ZONE_SOUTH",
                "confidence_score": 0.30,
                "top_candidates": [],
                "predicted_window_start": ts3,
                "predicted_window_end": ts3,
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 40,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts3,
            },
            window_hours=24,
        )
        assert res3["occurrence_count"] == 3
        assert res3["alert_state"] == "ESCALATED"
        assert res3["action_status"] == "ESCALATED_ALERT"
        assert "High-frequency" in res3["escalation_reason"] or "velocity" in res3["escalation_reason"]


def test_expired_window_creates_new_alert():
    """
    Verifies that if an existing alert is outside the rolling window (> 24 hours),
    a new complaint at the same ATM creates a fresh NEW alert rather than deduplicating.
    """
    ts_old = "2026-09-10 08:00:00"
    ts_new = "2026-09-12 12:00:00"  # 52 hours later (> 24h)

    with get_db_connection() as conn:
        res_old = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-EXP-01",
                "predicted_atm_id": "ATM-EA-038",
                "predicted_zone_id": "ZONE_EAST",
                "confidence_score": 0.30,
                "top_candidates": [],
                "predicted_window_start": ts_old,
                "predicted_window_end": ts_old,
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 40,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts_old,
            },
            window_hours=24,
        )
        assert res_old["alert_state"] == "NEW"

        res_new = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-EXP-02",
                "predicted_atm_id": "ATM-EA-038",
                "predicted_zone_id": "ZONE_EAST",
                "confidence_score": 0.30,
                "top_candidates": [],
                "predicted_window_start": ts_new,
                "predicted_window_end": ts_new,
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 40,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts_new,
            },
            window_hours=24,
        )
        assert res_new["prediction_id"] != res_old["prediction_id"]
        assert res_new["alert_state"] == "NEW"
        assert res_new["occurrence_count"] == 1


def test_list_predictions_includes_alert_lifecycle():
    """Verifies that GET /api/predictions history endpoint supplies alert lifecycle metadata."""
    preds = list_predictions(limit=10)
    assert isinstance(preds, list)
    assert len(preds) > 0
    for p in preds:
        assert "alert_state" in p
        assert p["alert_state"] in ("NEW", "REFRESHED", "ESCALATED")
        assert "occurrence_count" in p
        assert p["occurrence_count"] >= 1
        assert "escalation_reason" in p


# ==============================================================================
# 10. MAP CONVERGENCE & VISUALIZATION TESTS
# ==============================================================================

def test_convergence_map_data_completeness():
    """
    Verifies that all convergences returned by GET /api/analytics/convergences
    include complete geospatial coordinates and visual telemetry required for Leaflet map overlays.
    """
    res = get_repeated_convergences(
        window_hours=168,
        min_matches=2,
        target_type="all",
        zone=None,
    )
    assert isinstance(res, dict)
    assert "convergences" in res
    assert len(res["convergences"]) > 0

    valid_severities = {"CRITICAL", "HIGH", "ELEVATED", "MODERATE"}
    valid_types = {"ATM_CONVERGENCE", "ZONE_CONVERGENCE"}

    for c in res["convergences"]:
        # 1. Geospatial coordinates within Metropolitan Delhi operational bounds
        assert "latitude" in c and isinstance(c["latitude"], (int, float))
        assert "longitude" in c and isinstance(c["longitude"], (int, float))
        assert 28.0 <= c["latitude"] <= 29.5
        assert 76.5 <= c["longitude"] <= 78.0

        # 2. Map styling attributes
        assert c["convergence_type"] in valid_types
        assert c["severity_level"] in valid_severities
        assert 0 <= c["convergence_score"] <= 100
        assert isinstance(c["target_id"], str) and len(c["target_id"]) > 0
        assert isinstance(c["target_name"], str) and len(c["target_name"]) > 0
        assert isinstance(c["reason"], str) and len(c["reason"]) > 0
        assert isinstance(c["recommended_action"], str) and len(c["recommended_action"]) > 0
        assert c["total_matches"] >= 2


def test_atm_convergence_map_attributes():
    """
    Verifies that for every ATM_CONVERGENCE item, the latitude and longitude
    match the exact physical database coordinates in atm_locations.
    """
    res = get_repeated_convergences(
        window_hours=168,
        min_matches=2,
        target_type="atm",
        zone=None,
    )
    atm_convs = [c for c in res["convergences"] if c["convergence_type"] == "ATM_CONVERGENCE"]
    assert len(atm_convs) > 0

    with get_db_connection() as conn:
        for c in atm_convs:
            atm_id = c["target_id"]
            row = conn.execute(
                "SELECT latitude, longitude FROM atm_locations WHERE atm_id = ?;",
                (atm_id,),
            ).fetchone()
            assert row is not None
            expected_lat = round(float(row["latitude"]), 6)
            expected_lon = round(float(row["longitude"]), 6)
            assert round(c["latitude"], 4) == round(expected_lat, 4)
            assert round(c["longitude"], 4) == round(expected_lon, 4)
            assert c["involved_atm_ids"] == [atm_id]


def test_zone_convergence_map_attributes():
    """
    Verifies that for every ZONE_CONVERGENCE item, the latitude and longitude
    match the administrative zone centroid coordinates, and multi-ATM IDs are listed.
    """
    from backend.app.convergence_engine import ZONE_CENTROIDS

    res = get_repeated_convergences(
        window_hours=168,
        min_matches=2,
        target_type="zone",
        zone=None,
    )
    zone_convs = [c for c in res["convergences"] if c["convergence_type"] == "ZONE_CONVERGENCE"]
    assert len(zone_convs) > 0

    for c in zone_convs:
        zid = c["zone_id"]
        assert zid in ZONE_CENTROIDS
        expected_lat, expected_lon = ZONE_CENTROIDS[zid]
        assert round(c["latitude"], 4) == round(expected_lat, 4)
        assert round(c["longitude"], 4) == round(expected_lon, 4)
        assert isinstance(c["involved_atm_ids"], list)
        assert len(c["involved_atm_ids"]) >= 1


def test_convergence_filtering_for_map_sync():
    """
    Verifies that map sync filter queries return strictly the requested target_type
    and zone, enabling reactive map layer re-rendering.
    """
    # 1. Target type ATM only
    atm_res = get_repeated_convergences(target_type="atm", window_hours=168, min_matches=2)
    for c in atm_res["convergences"]:
        assert c["convergence_type"] == "ATM_CONVERGENCE"
    assert atm_res["zone_convergences_count"] == 0

    # 2. Target type Zone only
    zone_res = get_repeated_convergences(target_type="zone", window_hours=168, min_matches=2)
    for c in zone_res["convergences"]:
        assert c["convergence_type"] == "ZONE_CONVERGENCE"
    assert zone_res["atm_convergences_count"] == 0

    # 3. Zone specific filter
    west_res = get_repeated_convergences(target_type="all", zone="ZONE_WEST", window_hours=168, min_matches=2)
    for c in west_res["convergences"]:
        assert c["zone_id"] == "ZONE_WEST"


def test_empty_convergence_map_response_structure():
    """
    Verifies that an empty convergence result (e.g. min_matches=9999)
    preserves a valid, complete schema so the map controller clears tactical layers without crashing.
    """
    res = get_repeated_convergences(
        window_hours=24,
        min_matches=9999,
        target_type="all",
        zone=None,
    )
    assert res["total_convergences"] == 0
    assert res["atm_convergences_count"] == 0
    assert res["zone_convergences_count"] == 0
    assert res["convergences"] == []
    assert "window_start" in res
    assert "window_end" in res





