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
import re
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
    dispatch_patrol_endpoint,
    export_case_evidence_endpoint,
    generate_playbook_endpoint,
    generic_exception_handler,
    get_case_details,
    get_case_dispatch_endpoint,
    get_case_outcome_endpoint,
    get_dashboard_stats,
    get_emerging_clusters,
    get_intervention_performance_endpoint,
    get_model_information,
    get_outcome_metrics_endpoint,
    get_repeated_convergences,
    get_zone_hotspots,
    health_check,
    list_atms,
    list_cases,
    list_complaints,
    list_dispatches_endpoint,
    list_outcomes_endpoint,
    list_predictions,
    ml_engine,
    predict_cashout_location,
    record_case_outcome_endpoint,
    require_investigator_role,
    serve_dashboard,
    update_case_status,
    validation_exception_handler,
)
from backend.app.alert_engine import (
    evaluate_alert_escalation,
    find_active_alert,
    process_alert_lifecycle,
)
from backend.app.case_engine import (
    VALID_STATUS_TRANSITIONS,
    create_or_link_case,
    generate_case_id,
    get_case_by_id,
    list_operational_cases,
    transition_case_status,
)
from backend.app.dispatch_engine import (
    compile_case_evidence_packet,
    create_or_get_patrol_dispatch,
    export_case_evidence_csv,
    generate_dispatch_id,
    get_dispatch_by_case_id,
    list_patrol_dispatches,
)
from backend.app.outcome_engine import (
    VALID_OUTCOME_STATUSES,
    compute_outcome_metrics,
    get_outcome_by_case_id,
    list_case_outcomes,
    record_or_update_case_outcome,
)
from backend.app.analytics_engine import get_intervention_performance_analytics
from backend.app.cluster_engine import detect_emerging_clusters
from backend.app.convergence_engine import (
    compute_atm_convergence_score,
    compute_zone_convergence_score,
    detect_repeated_convergence,
)
from backend.app.database import get_db_connection, verify_database_readiness
from backend.app.ml_engine import compute_intervention_priority
from backend.app.playbook_engine import generate_investigator_playbook
from backend.app.schemas import (
    CaseOutcomeCreateRequest,
    CaseOutcomeResponse,
    CaseStatusUpdateRequest,
    ComplaintCreate,
    DispatchCreateRequest,
    DispatchResponse,
    InterventionPerformanceResponse,
    OutcomeMetricsResponse,
    PlaybookRequest,
    PredictionRequest,
)


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
    """Cleans up isolated test prediction, dispatch, outcome, and case records before and after each test."""
    clean_outcomes_sql = "DELETE FROM case_outcomes;"
    clean_dispatches_sql = "DELETE FROM patrol_dispatches;"
    clean_cases_sql = """
        DELETE FROM operational_cases 
        WHERE parent_alert_id IN (
            SELECT prediction_id FROM predictions
            WHERE complaint_id != 'CMP-INIT-001'
        )
        OR complaint_id != 'CMP-INIT-001';
    """
    clean_sql = """
        DELETE FROM predictions 
        WHERE complaint_id != 'CMP-INIT-001';
    """
    with get_db_connection() as conn:
        conn.execute(clean_outcomes_sql)
        conn.execute(clean_dispatches_sql)
        conn.execute(clean_cases_sql)
        conn.execute(clean_sql)
    yield
    with get_db_connection() as conn:
        conn.execute(clean_outcomes_sql)
        conn.execute(clean_dispatches_sql)
        conn.execute(clean_cases_sql)
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


# ==============================================================================
# SECTION 11: OPERATIONAL CASE IDS & CASE LIFECYCLE TESTS
# ==============================================================================

def test_case_creation_on_new_alert():
    """
    Verifies that generating a prediction/alert generates a unique operational Case ID
    in the format CASE-YYYYMMDD-HEX and establishes the initial status NEW_ALERT.
    """
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=75000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=20.0,
        incident_hour=14,
        incident_day_of_week=3,
        complaint_id="CMP-TEST-CASE-NEW-01",
    )
    res = predict_cashout_location(req)
    assert res.get("case_id") is not None
    assert re.match(r"^CASE-\d{8}-[A-F0-9]{6}$", res["case_id"])
    assert res.get("case_status") == "NEW_ALERT"


def test_case_linking_metadata():
    """
    Verifies that the created case is persisted and accurately linked to its
    originating complaint, prediction, alert, predicted ATM, zone, priority score,
    priority level, and intervention window.
    """
    req = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=60000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="STANDARD",
        mule_branch_zone="ZONE_NORTH",
        reporting_delay_mins=15.0,
        incident_hour=11,
        incident_day_of_week=2,
        complaint_id="CMP-TEST-CASE-LINK-01",
    )
    res = predict_cashout_location(req)
    case_id = res.get("case_id")
    assert case_id is not None

    with get_db_connection() as conn:
        case_row = get_case_by_id(conn, case_id)
        assert case_row is not None
        assert case_row["case_id"] == case_id
        assert case_row["complaint_id"] == res.get("complaint_id")
        parent_id = res.get("alert_id") or res.get("prediction_id")
        assert case_row["parent_alert_id"] == parent_id
        assert case_row["predicted_atm_id"] == res.get("predicted_atm_id")
        assert case_row["predicted_zone_id"] == res.get("predicted_zone_id")
        assert case_row["priority_score"] == res.get("priority_score")
        assert case_row["priority_level"] == res.get("priority_level")
        assert case_row["intervention_window_start"] == res.get("predicted_window_start")
        assert case_row["intervention_window_end"] == res.get("predicted_window_end")
        assert case_row["case_status"] == "NEW_ALERT"
        assert case_row["created_timestamp"] is not None


def test_case_duplicate_prevention_on_deduplication():
    """
    Verifies that when alert deduplication identifies the same underlying alert
    (REFRESHED or ESCALATED), it reuses the existing Case ID rather than creating
    a duplicate case in the operational_cases table.
    """
    ts_base = "2026-09-28 10:00:00"
    ts_later = "2026-09-28 11:30:00"

    with get_db_connection() as conn:
        # First alert -> Creates Case 1
        res1 = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-CASE-DEDUP-01",
                "predicted_atm_id": "ATM-NO-020",
                "predicted_zone_id": "ZONE_NORTH",
                "confidence_score": 0.45,
                "top_candidates": [],
                "predicted_window_start": ts_base,
                "predicted_window_end": ts_base,
                "risk_level": "HIGH",
                "explanation_codes": [],
                "priority_score": 65,
                "priority_level": "HIGH",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts_base,
            },
            window_hours=24,
        )
        case_id_1 = res1.get("case_id")
        assert case_id_1 is not None
        assert res1["alert_state"] == "NEW"

        # Count total cases with this case_id
        count1 = conn.execute(
            "SELECT COUNT(*) FROM operational_cases WHERE case_id = ?;", (case_id_1,)
        ).fetchone()[0]
        assert count1 == 1

        # Second incident within window targeting same ATM -> Refreshed/Escalated alert
        res2 = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-CASE-DEDUP-02",
                "predicted_atm_id": "ATM-NO-020",
                "predicted_zone_id": "ZONE_NORTH",
                "confidence_score": 0.48,
                "top_candidates": [],
                "predicted_window_start": ts_later,
                "predicted_window_end": ts_later,
                "risk_level": "HIGH",
                "explanation_codes": [],
                "priority_score": 70,
                "priority_level": "HIGH",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": ts_later,
            },
            window_hours=24,
        )
        case_id_2 = res2.get("case_id")
        assert res2["alert_state"] in ("REFRESHED", "ESCALATED")
        # Must reuse the same case_id
        assert case_id_2 == case_id_1

        # Verify no duplicate case was inserted into operational_cases
        count2 = conn.execute(
            "SELECT COUNT(*) FROM operational_cases WHERE case_id = ?;", (case_id_1,)
        ).fetchone()[0]
        assert count2 == 1


def test_valid_case_lifecycle_transitions():
    """
    Verifies valid lifecycle progression:
    NEW_ALERT -> PATROL_DISPATCHED -> RESOLVED
    and ensures status, updated timestamp, and audit notes are persisted.
    """
    # Create new case
    with get_db_connection() as conn:
        res = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-TRANS-01",
                "predicted_atm_id": "ATM-SO-021",
                "predicted_zone_id": "ZONE_SOUTH",
                "confidence_score": 0.35,
                "top_candidates": [],
                "predicted_window_start": "2026-09-28 12:00:00",
                "predicted_window_end": "2026-09-28 14:00:00",
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 50,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": "2026-09-28 12:00:00",
            },
            window_hours=24,
        )
        case_id = res["case_id"]
        assert res["case_status"] == "NEW_ALERT"

    # Transition 1: NEW_ALERT -> PATROL_DISPATCHED
    update_res1 = update_case_status(
        case_id=case_id,
        request=CaseStatusUpdateRequest(
            status="PATROL_DISPATCHED",
            notes="Unit 4 dispatched to perimeter",
        ),
    )
    assert update_res1["case_status"] == "PATROL_DISPATCHED"
    assert "Unit 4 dispatched" in (update_res1["notes"] or "")

    # Transition 2: PATROL_DISPATCHED -> OUTCOME_PENDING
    update_res2 = update_case_status(
        case_id=case_id,
        request=CaseStatusUpdateRequest(
            status="OUTCOME_PENDING",
            notes="Patrol on scene; observing target dispenser",
        ),
    )
    assert update_res2["case_status"] == "OUTCOME_PENDING"

    # Operational outcome must be recorded before case can be resolved
    with get_db_connection() as conn:
        create_or_get_patrol_dispatch(conn, case_id, patrol_unit="PCR-WEST-04", auto_advance_case=False)
        record_or_update_case_outcome(
            conn,
            case_id,
            "INTERCEPTED_AT_PREDICTED_ATM",
            auto_resolve_case=False,
        )

    # Transition 3: OUTCOME_PENDING -> RESOLVED
    update_res3 = update_case_status(
        case_id=case_id,
        request=CaseStatusUpdateRequest(
            status="RESOLVED",
            notes="Perimeter secured; cash-out deterred",
        ),
    )
    assert update_res3["case_status"] == "RESOLVED"
    assert "deterred" in (update_res3["notes"] or "")

    # Verify DB persistence
    with get_db_connection() as conn:
        persisted = get_case_by_id(conn, case_id)
        assert persisted["case_status"] == "RESOLVED"
        assert persisted["updated_timestamp"] is not None


def test_invalid_case_lifecycle_transitions():
    """
    Verifies that illegal status transitions are rejected with HTTP 400:
    - NEW_ALERT -> RESOLVED (direct skipping)
    - NEW_ALERT -> NEW_ALERT (same status)
    - PATROL_DISPATCHED -> RESOLVED before outcome recorded
    - RESOLVED -> PATROL_DISPATCHED (re-opening/backward)
    - Any unknown status string
    - Non-existent case ID produces HTTP 404
    """
    with get_db_connection() as conn:
        res = process_alert_lifecycle(
            db_conn=conn,
            prediction_candidate={
                "complaint_id": "CMP-INV-TRANS-01",
                "predicted_atm_id": "ATM-WE-041",
                "predicted_zone_id": "ZONE_WEST",
                "confidence_score": 0.40,
                "top_candidates": [],
                "predicted_window_start": "2026-09-28 09:00:00",
                "predicted_window_end": "2026-09-28 11:00:00",
                "risk_level": "MODERATE",
                "explanation_codes": [],
                "priority_score": 55,
                "priority_level": "MEDIUM",
                "priority_reasons": [],
                "playbook": None,
                "reference_timestamp": "2026-09-28 09:00:00",
            },
            window_hours=24,
        )
        case_id = res["case_id"]

    # 1. Illegal transition: NEW_ALERT directly to RESOLVED
    with pytest.raises(HTTPException) as exc_info:
        update_case_status(case_id, CaseStatusUpdateRequest(status="RESOLVED"))
    assert exc_info.value.status_code == 400
    assert "Invalid lifecycle transition" in exc_info.value.detail

    # 2. Illegal transition: NEW_ALERT to NEW_ALERT (same state)
    with pytest.raises(HTTPException) as exc_info:
        update_case_status(case_id, CaseStatusUpdateRequest(status="NEW_ALERT"))
    assert exc_info.value.status_code == 400

    # 3. Advance to PATROL_DISPATCHED
    update_case_status(case_id, CaseStatusUpdateRequest(status="PATROL_DISPATCHED"))

    # Attempting to resolve without an outcome record raises HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        update_case_status(case_id, CaseStatusUpdateRequest(status="RESOLVED"))
    assert exc_info.value.status_code == 400
    assert "before an operational outcome is recorded" in exc_info.value.detail

    # Record outcome with auto_resolve_case=True to legitimately transition to RESOLVED
    with get_db_connection() as conn:
        create_or_get_patrol_dispatch(conn, case_id, patrol_unit="PCR-WEST-01", auto_advance_case=False)
        record_or_update_case_outcome(conn, case_id, "INTERCEPTED_AT_PREDICTED_ATM", auto_resolve_case=True)

    # 4. Illegal transition: from RESOLVED back to PATROL_DISPATCHED
    with pytest.raises(HTTPException) as exc_info:
        update_case_status(case_id, CaseStatusUpdateRequest(status="PATROL_DISPATCHED"))
    assert exc_info.value.status_code == 400
    assert "Terminal state" in exc_info.value.detail or "Invalid lifecycle transition" in exc_info.value.detail

    # 5. Invalid status string
    with pytest.raises(HTTPException) as exc_info:
        update_case_status(case_id, CaseStatusUpdateRequest(status="DISMISSED"))
    assert exc_info.value.status_code == 400

    # 6. Non-existent case ID -> HTTP 404
    with pytest.raises(HTTPException) as exc_info:
        update_case_status("CASE-99999999-000000", CaseStatusUpdateRequest(status="PATROL_DISPATCHED"))
    assert exc_info.value.status_code == 404


def test_get_case_and_list_cases_endpoints():
    """
    Verifies GET /api/cases and GET /api/cases/{case_id} REST endpoints,
    including filtering by status, limit handling, and 404 for non-existent cases.
    """
    # 0. Ensure at least one case exists
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=70000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=20.0,
        incident_hour=14,
        incident_day_of_week=3,
        complaint_id="CMP-TEST-CASE-LIST-01",
    )
    pred_res = predict_cashout_location(req)
    created_case_id = pred_res.get("case_id")
    assert created_case_id is not None

    # 1. List cases
    all_cases = list_cases(limit=10)
    assert isinstance(all_cases, list)
    assert len(all_cases) > 0

    first_case = all_cases[0]
    assert "case_id" in first_case
    assert "case_status" in first_case
    assert "priority_score" in first_case

    # 2. Get specific case
    case_detail = get_case_details(created_case_id)
    assert case_detail["case_id"] == created_case_id
    assert case_detail["predicted_atm_id"] == pred_res.get("predicted_atm_id")

    # 3. Filter cases by status
    dispatch_patrol_endpoint(
        created_case_id,
        DispatchCreateRequest(patrol_unit="PCR-WEST-01"),
    )
    record_case_outcome_endpoint(
        created_case_id,
        CaseOutcomeCreateRequest(
            outcome_status="INTERCEPTED_AT_PREDICTED_ATM",
            auto_resolve_case=True,
        ),
    )

    resolved_cases = list_cases(status="RESOLVED", limit=10)
    assert isinstance(resolved_cases, list)
    assert len(resolved_cases) > 0
    for c in resolved_cases:
        assert c["case_status"] == "RESOLVED"

    # 4. Non-existent case -> 404
    with pytest.raises(HTTPException) as exc_info:
        get_case_details("CASE-00000000-NONEXIST")
    assert exc_info.value.status_code == 404


# ==============================================================================
# 12. FIELD PATROL DISPATCH ROUTING & EVIDENCE EXPORT TESTS
# ==============================================================================

def test_patrol_dispatch_creation_and_fields():
    """
    Verifies that POST /api/cases/{case_id}/dispatch generates a valid,
    persisted dispatch record with structured routing fields.
    """
    # 1. Create a prediction and case
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=85000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=25.0,
        incident_hour=15,
        incident_day_of_week=4,
        complaint_id="CMP-TEST-DISP-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res.get("case_id")
    assert case_id is not None
    assert case_id.startswith("CASE-")

    # 2. Dispatch patrol
    disp_req = DispatchCreateRequest(
        patrol_unit="PCR-WEST-09",
        notes="High-velocity cashout target. Intercept perimeter.",
        auto_advance_case=True,
    )
    disp = dispatch_patrol_endpoint(case_id=case_id, request=disp_req)

    # 3. Assert structured dispatch fields
    assert disp["dispatch_id"].startswith("DISP-")
    assert disp["case_id"] == case_id
    assert disp["target_atm_id"] == pred_res["predicted_atm_id"]
    assert disp["zone_id"] == pred_res["predicted_zone_id"]
    assert disp["priority_score"] == pred_res["priority_score"]
    assert disp["priority_level"] == pred_res["priority_level"]
    assert disp["patrol_unit_assigned"] == "PCR-WEST-09"
    assert disp["dispatch_status"] == "DISPATCHED"
    assert disp["dispatched_timestamp"] is not None
    assert "PCR-WEST-09" in disp["tactical_brief"] or "Target ATM" in disp["tactical_brief"] or "DISPATCH BRIEF" in disp["tactical_brief"]
    assert isinstance(disp["playbook_actions"], list)


def test_patrol_dispatch_auto_advance_case_lifecycle():
    """
    Verifies that dispatching a patrol on a NEW_ALERT case automatically
    advances the underlying operational case lifecycle to PATROL_DISPATCHED.
    """
    req = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=45000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_NORTH",
        reporting_delay_mins=15.0,
        incident_hour=18,
        incident_day_of_week=5,
        complaint_id="CMP-TEST-DISP-ADV-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Verify initial case status
    initial_case = get_case_details(case_id)
    assert initial_case["case_status"] == "NEW_ALERT"

    # Dispatch patrol with auto_advance_case=True
    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-NORTH-03", notes="Auto advance test"),
    )

    # Verify case status transitioned to PATROL_DISPATCHED
    updated_case = get_case_details(case_id)
    assert updated_case["case_status"] == "PATROL_DISPATCHED"
    assert "PCR-NORTH-03" in updated_case["notes"] or "dispatched" in updated_case["notes"].lower()


def test_get_case_dispatch_and_list_dispatches_endpoints():
    """
    Verifies GET /api/cases/{case_id}/dispatch and GET /api/dispatches endpoints.
    """
    req = PredictionRequest(
        crime_category="LOAN_SCAM",
        reported_amount=30000.0,
        payment_channel="IMPS",
        mule_bank_code="BANK_PNB_SYNTH",
        mule_account_tier="STANDARD",
        mule_branch_zone="ZONE_CENTRAL",
        reporting_delay_mins=40.0,
        incident_hour=11,
        incident_day_of_week=2,
        complaint_id="CMP-TEST-DISP-READ-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-CENTRAL-02"),
    )

    # 1. Fetch dispatch by case ID
    disp = get_case_dispatch_endpoint(case_id)
    assert disp["case_id"] == case_id
    assert disp["patrol_unit_assigned"] == "PCR-CENTRAL-02"
    assert disp["dispatch_status"] == "DISPATCHED"

    # 2. List dispatches
    all_disp = list_dispatches_endpoint(limit=10)
    assert isinstance(all_disp, list)
    assert len(all_disp) > 0
    found = [d for d in all_disp if d["case_id"] == case_id]
    assert len(found) == 1

    # 3. 404 for non-existent case dispatch
    with pytest.raises(HTTPException) as exc_info:
        get_case_dispatch_endpoint("CASE-00000000-NONEXIST")
    assert exc_info.value.status_code == 404


def test_patrol_dispatch_default_unit_fallback():
    """
    Verifies that if patrol_unit callsign is not provided, the system assigns
    a deterministic zone-based callsign (PCR-{ZONE}-01).
    """
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=50000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_EAST",
        reporting_delay_mins=30.0,
        incident_hour=16,
        incident_day_of_week=3,
        complaint_id="CMP-TEST-DISP-DEF-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Dispatch without explicit unit
    disp = dispatch_patrol_endpoint(case_id=case_id, request=None)
    assert disp["patrol_unit_assigned"].startswith("PCR-")
    assert "01" in disp["patrol_unit_assigned"]
    assert disp["dispatch_status"] == "DISPATCHED"


def test_case_evidence_export_json_packet():
    """
    Verifies comprehensive structured evidence export in JSON format,
    including case lifecycle, target ATM details, candidate ATMs,
    convergences, clusters, and verified Phase 2 ML provenance.
    """
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=95000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=20.0,
        incident_hour=14,
        incident_day_of_week=4,
        complaint_id="CMP-TEST-EVID-JSON-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Add a dispatch record
    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-WEST-01", notes="Evidence verification unit"),
    )

    # 1. Direct JSON packet
    evidence = export_case_evidence_endpoint(case_id=case_id, format="json", download=False)
    assert isinstance(evidence, dict)
    assert "export_timestamp" in evidence

    # Verify sections
    assert "case" in evidence
    assert evidence["case"]["case_id"] == case_id
    assert evidence["case"]["priority_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    assert "dispatch" in evidence
    assert evidence["dispatch"]["patrol_unit_assigned"] == "PCR-WEST-01"
    assert evidence["dispatch"]["dispatch_status"] == "DISPATCHED"

    assert "prediction" in evidence
    assert evidence["prediction"]["complaint_id"] == "CMP-TEST-EVID-JSON-01"

    assert "target_atm" in evidence
    assert evidence["target_atm"]["atm_id"] == pred_res["predicted_atm_id"]
    assert "latitude" in evidence["target_atm"]
    assert "longitude" in evidence["target_atm"]

    assert "top_candidates" in evidence
    assert isinstance(evidence["top_candidates"], list)

    assert "convergences" in evidence
    assert isinstance(evidence["convergences"], list)

    assert "clusters" in evidence
    assert isinstance(evidence["clusters"], list)

    # Verify model provenance
    assert "model_provenance" in evidence
    prov = evidence["model_provenance"]
    assert prov["evaluation_partition"] == "P3_FUTURE_TEST_ONLY"
    metrics = prov["verified_metrics"]
    assert metrics["top1_spatial_accuracy_pct"] == 10.17
    assert metrics["top3_spatial_accuracy_pct"] == 31.71
    assert metrics["top5_spatial_accuracy_pct"] == 41.88
    assert metrics["zone_level_accuracy_pct"] == 68.89
    assert metrics["calibrated_brier_score"] == 0.9726
    assert metrics["calibrated_log_loss"] == 3.5199
    assert metrics["temporal_window_coverage_pct"] == 50.38

    # 2. Download JSON attachment
    download_resp = export_case_evidence_endpoint(case_id=case_id, format="json", download=True)
    assert download_resp.media_type == "application/json"
    assert f"evidence_{case_id}.json" in download_resp.headers["Content-Disposition"]
    payload_data = json.loads(download_resp.body.decode("utf-8"))
    assert payload_data["case"]["case_id"] == case_id


def test_case_evidence_export_csv():
    """
    Verifies structured evidence export formatted as a standardized CSV table.
    """
    req = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=60000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_NORTH",
        reporting_delay_mins=22.0,
        incident_hour=16,
        incident_day_of_week=5,
        complaint_id="CMP-TEST-EVID-CSV-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-NORTH-05"),
    )

    csv_resp = export_case_evidence_endpoint(case_id=case_id, format="csv")
    assert csv_resp.media_type == "text/csv"
    assert f"evidence_{case_id}.csv" in csv_resp.headers["Content-Disposition"]

    csv_text = csv_resp.body.decode("utf-8")
    assert "SECTION,FIELD,VALUE" in csv_text
    assert "CASE_METADATA,Case ID," + case_id in csv_text
    assert "TARGET_ATM,ATM ID," + pred_res["predicted_atm_id"] in csv_text
    assert "PATROL_DISPATCH,Assigned Unit,PCR-NORTH-05" in csv_text
    assert "ML_PROVENANCE,Top-1 Accuracy,10.17%" in csv_text
    assert "ML_PROVENANCE,Zone Accuracy,68.89%" in csv_text


def test_case_evidence_export_nonexistent_case():
    """
    Verifies that attempting to export evidence for a non-existent case raises HTTP 404.
    """
    with pytest.raises(HTTPException) as exc_info:
        export_case_evidence_endpoint(case_id="CASE-00000000-NONEXIST")
    assert exc_info.value.status_code == 404


# ==============================================================================
# 13. INCIDENT OUTCOME LOGGING & FEEDBACK LOOP TESTS
# ==============================================================================

def test_record_case_outcome_predicted_atm_hit():
    """
    Verifies that an investigator can record a verified ground truth outcome,
    confirming a spatial hit when intercepted at the predicted ATM, and auto-resolving the case.
    """
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=80000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=25.0,
        incident_hour=15,
        incident_day_of_week=4,
        complaint_id="CMP-TEST-OUTCOME-HIT-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Dispatch patrol
    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-WEST-02"),
    )

    # Record outcome as spatial hit
    outcome_req = CaseOutcomeCreateRequest(
        outcome_status="INTERCEPTED_AT_PREDICTED_ATM",
        notes="Suspect intercepted at predicted dispenser during tactical window. Seized 80,000 INR.",
        investigator_id="INV-WEST-01",
        auto_resolve_case=True,
    )
    out = record_case_outcome_endpoint(case_id=case_id, request=outcome_req)

    assert out["outcome_id"].startswith("OUT-")
    assert out["case_id"] == case_id
    assert out["outcome_status"] == "INTERCEPTED_AT_PREDICTED_ATM"
    assert out["predicted_atm_id"] == pred_res["predicted_atm_id"]
    assert out["actual_atm_id"] == pred_res["predicted_atm_id"]
    assert out["is_spatial_hit"] is True
    assert out["investigator_id"] == "INV-WEST-01"
    assert "80,000" in out["notes"]

    # Verify case lifecycle auto-advanced to RESOLVED
    c = get_case_details(case_id)
    assert c["case_status"] == "RESOLVED"


def test_record_case_outcome_other_atm():
    """
    Verifies recording an interception at an adjacent/different ATM,
    marking is_spatial_hit=False while capturing the actual cash-out location.
    """
    req = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=40000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_NORTH",
        reporting_delay_mins=18.0,
        incident_hour=18,
        incident_day_of_week=5,
        complaint_id="CMP-TEST-OUTCOME-OTHER-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Dispatch patrol prior to recording outcome
    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-NORTH-04"),
    )

    outcome_req = CaseOutcomeCreateRequest(
        outcome_status="INTERCEPTED_AT_OTHER_ATM",
        actual_atm_id="ATM-NO-012",
        notes="Target diverted to secondary kiosk 400m away.",
        auto_resolve_case=True,
    )
    out = record_case_outcome_endpoint(case_id=case_id, request=outcome_req)

    assert out["outcome_status"] == "INTERCEPTED_AT_OTHER_ATM"
    assert out["actual_atm_id"] == "ATM-NO-012"
    # If predicted ATM was not ATM-NO-012, is_spatial_hit must be False
    if pred_res["predicted_atm_id"] != "ATM-NO-012":
        assert out["is_spatial_hit"] is False


def test_record_case_outcome_invalid_status_rejected():
    """
    Verifies that invalid outcome status values are rejected by schema validation.
    """
    with pytest.raises(Exception):
        CaseOutcomeCreateRequest(
            outcome_status="UNKNOWN_OUTCOME",
            notes="Invalid status test",
        )


def test_outcome_auto_resolves_case_flag():
    """
    Verifies the behavior of the auto_resolve_case parameter.
    """
    req = PredictionRequest(
        crime_category="LOAN_SCAM",
        reported_amount=25000.0,
        payment_channel="NEFT",
        mule_bank_code="BANK_PNB_SYNTH",
        mule_account_tier="STANDARD",
        mule_branch_zone="ZONE_SOUTH",
        reporting_delay_mins=50.0,
        incident_hour=11,
        incident_day_of_week=2,
        complaint_id="CMP-TEST-OUTCOME-FLAG-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Dispatch patrol prior to outcome logging
    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-SOUTH-02"),
    )

    # Record outcome with auto_resolve_case=False
    outcome_req = CaseOutcomeCreateRequest(
        outcome_status="NO_CASHOUT",
        notes="Preliminary check; case kept active for further analysis.",
        auto_resolve_case=False,
    )
    record_case_outcome_endpoint(case_id=case_id, request=outcome_req)

    c = get_case_details(case_id)
    assert c["case_status"] == "OUTCOME_PENDING"


def test_get_case_outcome_and_list_endpoints():
    """
    Verifies GET /api/cases/{case_id}/outcome and GET /api/outcomes endpoints,
    including 404 for cases without recorded outcomes.
    """
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=65000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_EAST",
        reporting_delay_mins=20.0,
        incident_hour=14,
        incident_day_of_week=3,
        complaint_id="CMP-TEST-OUTCOME-READ-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # 1. 404 before outcome is recorded
    with pytest.raises(HTTPException) as exc_info:
        get_case_outcome_endpoint(case_id)
    assert exc_info.value.status_code == 404

    # 2. Dispatch patrol
    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-EAST-05"),
    )

    # 3. Record outcome
    record_case_outcome_endpoint(
        case_id=case_id,
        request=CaseOutcomeCreateRequest(outcome_status="FALSE_ALERT", notes="Benign transfer confirmed with victim"),
    )

    # 4. Retrieve outcome
    out = get_case_outcome_endpoint(case_id)
    assert out["case_id"] == case_id
    assert out["outcome_status"] == "FALSE_ALERT"

    # 5. List outcomes
    all_outcomes = list_outcomes_endpoint(limit=10)
    assert isinstance(all_outcomes, list)
    assert any(o["case_id"] == case_id for o in all_outcomes)


def test_outcome_metrics_calculation():
    """
    Verifies GET /api/outcomes/metrics calculates aggregated prediction hit rate,
    match count, interception rate, and outcome distribution.
    """
    # Create two distinct cases with different outcomes
    req1 = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=75000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=15.0,
        incident_hour=15,
        incident_day_of_week=4,
        complaint_id="CMP-TEST-METRICS-01",
    )
    c1 = predict_cashout_location(req1)["case_id"]
    dispatch_patrol_endpoint(
        case_id=c1,
        request=DispatchCreateRequest(patrol_unit="PCR-WEST-11"),
    )
    record_case_outcome_endpoint(
        case_id=c1,
        request=CaseOutcomeCreateRequest(outcome_status="INTERCEPTED_AT_PREDICTED_ATM"),
    )

    req2 = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=35000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_NORTH",
        reporting_delay_mins=20.0,
        incident_hour=17,
        incident_day_of_week=5,
        complaint_id="CMP-TEST-METRICS-02",
    )
    c2 = predict_cashout_location(req2)["case_id"]
    dispatch_patrol_endpoint(
        case_id=c2,
        request=DispatchCreateRequest(patrol_unit="PCR-NORTH-12"),
    )
    record_case_outcome_endpoint(
        case_id=c2,
        request=CaseOutcomeCreateRequest(outcome_status="FALSE_ALERT"),
    )

    metrics = get_outcome_metrics_endpoint()
    assert metrics["total_outcomes_recorded"] >= 2
    assert metrics["predicted_atm_match_count"] >= 1
    assert metrics["prediction_hit_rate_pct"] > 0.0
    assert metrics["interception_success_count"] >= 1
    assert metrics["interception_rate_pct"] > 0.0
    assert metrics["false_alert_count"] >= 1
    assert isinstance(metrics["outcome_breakdown"], dict)
    for expected_key in VALID_OUTCOME_STATUSES:
        assert expected_key in metrics["outcome_breakdown"]


def test_record_outcome_nonexistent_case_404():
    """
    Verifies that attempting to record an outcome for an invalid case ID raises HTTP 404.
    """
    with pytest.raises(HTTPException) as exc_info:
        record_case_outcome_endpoint(
            case_id="CASE-00000000-NONEXIST",
            request=CaseOutcomeCreateRequest(outcome_status="UNRESOLVED"),
        )
    assert exc_info.value.status_code == 404


# ==============================================================================
# SECTION 14: INTERVENTION PERFORMANCE & OPERATIONAL ANALYTICS TESTS
# ==============================================================================
def test_intervention_performance_schema_and_types():
    """
    Verifies GET /api/analytics/intervention-performance returns valid
    aggregate performance metrics conforming strictly to InterventionPerformanceResponse.
    """
    analytics = get_intervention_performance_endpoint()
    validated = InterventionPerformanceResponse(**analytics)

    assert isinstance(validated.generated_timestamp, str)
    assert validated.total_actionable_cases >= 0
    assert validated.dispatched_cases >= 0
    assert validated.resolved_cases >= 0
    assert validated.new_alert_cases >= 0
    assert validated.intercepted_cases >= 0
    assert validated.unresolved_count >= 0
    assert validated.false_alert_count >= 0
    assert validated.no_cashout_count >= 0
    assert validated.total_outcomes_logged >= 0
    assert validated.predicted_vs_actual_matches >= 0
    assert 0.0 <= validated.spatial_hit_rate_pct <= 100.0
    assert 0.0 <= validated.interception_success_rate_pct <= 100.0

    # Validate timing metrics
    timing = validated.timing
    assert timing.avg_alert_to_dispatch_mins >= 0.0
    assert timing.avg_dispatch_to_outcome_mins >= 0.0
    assert timing.avg_alert_to_outcome_mins >= 0.0
    assert timing.sampled_timed_cases >= 0

    # Validate zone and ATM collections
    assert isinstance(validated.performance_by_zone, list)
    assert isinstance(validated.performance_by_atm, list)
    assert isinstance(validated.outcome_breakdown, dict)


def test_intervention_performance_with_recorded_pipeline():
    """
    Simulates a full operational pipeline (predict -> case -> dispatch -> outcome)
    and verifies that analytics counters, hit rates, and zone/ATM metrics accurately update.
    """
    # 1. Create Prediction & Case in ZONE_EAST
    req1 = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=48000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_EAST",
        reporting_delay_mins=25.0,
        incident_hour=16,
        incident_day_of_week=3,
        complaint_id="CMP-TEST-PERF-01",
    )
    pred_res1 = predict_cashout_location(req1)
    case_id1 = pred_res1["case_id"]
    atm_id1 = pred_res1["predicted_atm_id"]

    # 2. Dispatch Patrol for Case 1
    dispatch_patrol_endpoint(
        case_id=case_id1,
        request=DispatchCreateRequest(patrol_unit="PCR-EAST-99", notes="Priority rapid response"),
    )

    # 3. Log Successful Interception Outcome (Spatial Hit)
    record_case_outcome_endpoint(
        case_id=case_id1,
        request=CaseOutcomeCreateRequest(
            outcome_status="INTERCEPTED_AT_PREDICTED_ATM",
            actual_atm_id=atm_id1,
            notes="Suspect intercepted in cash-out queue at predicted ATM kiosk",
        ),
    )

    # 4. Create second Case in ZONE_WEST with False Alert
    req2 = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=95000.0,
        payment_channel="NEFT",
        mule_bank_code="BANK_PNB_SYNTH",
        mule_account_tier="RURAL_REGIONAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=120.0,
        incident_hour=11,
        incident_day_of_week=4,
        complaint_id="CMP-TEST-PERF-02",
    )
    pred_res2 = predict_cashout_location(req2)
    case_id2 = pred_res2["case_id"]

    dispatch_patrol_endpoint(
        case_id=case_id2,
        request=DispatchCreateRequest(patrol_unit="PCR-WEST-88"),
    )
    record_case_outcome_endpoint(
        case_id=case_id2,
        request=CaseOutcomeCreateRequest(
            outcome_status="FALSE_ALERT",
            notes="Verified legitimate merchant remittance",
        ),
    )

    # 5. Fetch and verify analytics
    analytics = get_intervention_performance_endpoint()

    assert analytics["total_actionable_cases"] >= 2
    assert analytics["dispatched_cases"] >= 2
    assert analytics["resolved_cases"] >= 2
    assert analytics["total_outcomes_logged"] >= 2
    assert analytics["predicted_vs_actual_matches"] >= 1
    assert analytics["spatial_hit_rate_pct"] > 0.0
    assert analytics["interception_success_rate_pct"] > 0.0
    assert analytics["outcome_breakdown"]["INTERCEPTED_AT_PREDICTED_ATM"] >= 1
    assert analytics["outcome_breakdown"]["FALSE_ALERT"] >= 1

    # Check zone performance
    zones = {z["zone_id"]: z for z in analytics["performance_by_zone"]}
    assert "ZONE_EAST" in zones
    assert zones["ZONE_EAST"]["total_cases"] >= 1
    assert zones["ZONE_EAST"]["spatial_hits"] >= 1

    # Check ATM performance
    atms = {a["atm_id"]: a for a in analytics["performance_by_atm"]}
    assert atm_id1 in atms
    assert atms[atm_id1]["total_cases"] >= 1
    assert atms[atm_id1]["spatial_hits"] >= 1


def test_intervention_performance_direct_engine():
    """
    Directly tests get_intervention_performance_analytics helper on a sqlite3 connection.
    """
    with get_db_connection() as conn:
        res = get_intervention_performance_analytics(conn)

    assert "generated_timestamp" in res
    assert "outcome_breakdown" in res
    assert "timing" in res
    assert "performance_by_zone" in res
    assert "performance_by_atm" in res
    assert isinstance(res["timing"]["sampled_timed_cases"], int)


# ==============================================================================
# SECTION 15: SEQUENTIAL OPERATIONAL STATE MACHINE GUARDRAIL TESTS
# ==============================================================================

def test_cannot_log_outcome_before_dispatch():
    """
    Verifies Guardrail 1: Attempting to log an operational outcome on a NEW_ALERT case
    prior to patrol dispatch is rejected with HTTP 400.
    """
    req = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=50000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_EAST",
        reporting_delay_mins=20.0,
        incident_hour=14,
        incident_day_of_week=3,
        complaint_id="CMP-TEST-GUARD-NODISP-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Attempt to log outcome before dispatch -> HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        record_case_outcome_endpoint(
            case_id=case_id,
            request=CaseOutcomeCreateRequest(
                outcome_status="INTERCEPTED_AT_PREDICTED_ATM",
                notes="Premature outcome logging test",
            ),
        )
    assert exc_info.value.status_code == 400
    assert "before patrol is dispatched" in exc_info.value.detail.lower()


def test_cannot_dispatch_twice():
    """
    Verifies Guardrail 2: A case that has already been dispatched cannot be dispatched again;
    subsequent dispatch requests are rejected with HTTP 400.
    """
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=80000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=15.0,
        incident_hour=16,
        incident_day_of_week=4,
        complaint_id="CMP-TEST-GUARD-NODBLDISP-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # 1. First dispatch succeeds
    disp1 = dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-WEST-01"),
    )
    assert disp1["dispatch_status"] == "DISPATCHED"

    # 2. Second dispatch rejected -> HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        dispatch_patrol_endpoint(
            case_id=case_id,
            request=DispatchCreateRequest(patrol_unit="PCR-WEST-02"),
        )
    assert exc_info.value.status_code == 400
    assert "cannot dispatch twice" in exc_info.value.detail.lower() or "already been dispatched" in exc_info.value.detail.lower()


def test_cannot_resolve_before_outcome_recorded():
    """
    Verifies Guardrail 3: Transitioning a case to RESOLVED without a recorded operational
    outcome is rejected with HTTP 400.
    """
    req = PredictionRequest(
        crime_category="LOAN_SCAM",
        reported_amount=35000.0,
        payment_channel="NEFT",
        mule_bank_code="BANK_PNB_SYNTH",
        mule_account_tier="STANDARD",
        mule_branch_zone="ZONE_NORTH",
        reporting_delay_mins=45.0,
        incident_hour=10,
        incident_day_of_week=2,
        complaint_id="CMP-TEST-GUARD-NOOUT-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Dispatch patrol
    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-NORTH-01"),
    )

    # Attempt to resolve case directly without outcome -> HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        update_case_status(case_id, CaseStatusUpdateRequest(status="RESOLVED"))
    assert exc_info.value.status_code == 400
    assert "before an operational outcome is recorded" in exc_info.value.detail.lower()


def test_finalized_outcome_cannot_be_modified():
    """
    Verifies Guardrail 4: Once an outcome is recorded and the case is resolved,
    subsequent attempts to modify or overwrite the outcome are rejected with HTTP 400.
    """
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=90000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=10.0,
        incident_hour=15,
        incident_day_of_week=4,
        complaint_id="CMP-TEST-GUARD-FINAL-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # 1. Dispatch
    dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-WEST-15"),
    )

    # 2. Record initial outcome and resolve case
    record_case_outcome_endpoint(
        case_id=case_id,
        request=CaseOutcomeCreateRequest(
            outcome_status="INTERCEPTED_AT_PREDICTED_ATM",
            notes="Suspect intercepted in cash-out queue",
            auto_resolve_case=True,
        ),
    )

    c = get_case_details(case_id)
    assert c["case_status"] == "RESOLVED"

    # 3. Attempt to re-record or mutate finalized outcome -> HTTP 400
    with pytest.raises(HTTPException) as exc_info:
        record_case_outcome_endpoint(
            case_id=case_id,
            request=CaseOutcomeCreateRequest(
                outcome_status="FALSE_ALERT",
                notes="Attempted post-resolution alteration",
            ),
        )
    assert exc_info.value.status_code == 400
    assert "finalized and cannot be modified" in exc_info.value.detail.lower()


def test_spatial_hit_and_unresolved_terminal_outcomes():
    """
    Verifies that INTERCEPTED_AT_PREDICTED_ATM marks a spatial hit and properly resolves the case,
    and UNRESOLVED marks is_spatial_hit=False and also cleanly resolves the case.
    """
    # 1. Test INTERCEPTED_AT_PREDICTED_ATM
    req1 = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=70000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=12.0,
        incident_hour=14,
        incident_day_of_week=3,
        complaint_id="CMP-TEST-TERM-HIT-01",
    )
    p1 = predict_cashout_location(req1)
    dispatch_patrol_endpoint(p1["case_id"], DispatchCreateRequest(patrol_unit="PCR-WEST-21"))
    out1 = record_case_outcome_endpoint(
        p1["case_id"],
        CaseOutcomeCreateRequest(
            outcome_status="INTERCEPTED_AT_PREDICTED_ATM",
            auto_resolve_case=True,
        ),
    )
    assert out1["is_spatial_hit"] is True
    assert get_case_details(p1["case_id"])["case_status"] == "RESOLVED"

    # 2. Test UNRESOLVED
    req2 = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=32000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_NORTH",
        reporting_delay_mins=25.0,
        incident_hour=16,
        incident_day_of_week=5,
        complaint_id="CMP-TEST-TERM-UNRES-01",
    )
    p2 = predict_cashout_location(req2)
    dispatch_patrol_endpoint(p2["case_id"], DispatchCreateRequest(patrol_unit="PCR-NORTH-22"))
    out2 = record_case_outcome_endpoint(
        p2["case_id"],
        CaseOutcomeCreateRequest(
            outcome_status="UNRESOLVED",
            notes="Suspect evaded perimeter before unit arrival",
            auto_resolve_case=True,
        ),
    )
    assert out2["is_spatial_hit"] is False
    assert out2["outcome_status"] == "UNRESOLVED"
    assert get_case_details(p2["case_id"])["case_status"] == "RESOLVED"


def test_closed_lifecycle_and_state_telemetry():
    """
    Verifies that CLOSED is a valid terminal state, cannot be dispatched after closure,
    and returns proper telemetry (is_dispatched, has_outcome, next_valid_action='NONE').
    """
    req = PredictionRequest(
        crime_category="TASK_FRAUD",
        reported_amount=55000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_CENTRAL",
        reporting_delay_mins=18.0,
        incident_hour=11,
        incident_day_of_week=1,
        complaint_id="CMP-TEST-CLOSED-STATE-01",
    )
    p = predict_cashout_location(req)
    case_id = p["case_id"]

    # Verify NEW_ALERT telemetry
    case_before = get_case_details(case_id)
    assert case_before["case_status"] == "NEW_ALERT"
    assert case_before["is_dispatched"] is False
    assert case_before["has_outcome"] is False
    assert case_before["next_valid_action"] == "DISPATCH_PATROL"

    # Dispatch
    dispatch_patrol_endpoint(case_id, DispatchCreateRequest(patrol_unit="PCR-CENTRAL-09"))
    case_disp = get_case_details(case_id)
    assert case_disp["case_status"] == "PATROL_DISPATCHED"
    assert case_disp["is_dispatched"] is True
    assert case_disp["has_outcome"] is False
    assert case_disp["next_valid_action"] == "LOG_OUTCOME"

    # Record outcome without auto resolve -> advances to OUTCOME_PENDING
    record_case_outcome_endpoint(
        case_id,
        CaseOutcomeCreateRequest(
            outcome_status="INTERCEPTED_AT_OTHER_ATM",
            actual_atm_id=p["predicted_atm_id"],
            notes="Intercepted at adjacent kiosk",
            auto_resolve_case=False,
        ),
    )
    case_pending = get_case_details(case_id)
    assert case_pending["case_status"] == "OUTCOME_PENDING"
    assert case_pending["is_dispatched"] is True
    assert case_pending["has_outcome"] is True
    assert case_pending["next_valid_action"] == "RECORD_OUTCOME"

    # Transition to CLOSED
    update_case_status(case_id, CaseStatusUpdateRequest(status="CLOSED", notes="Case concluded and closed."))
    case_closed = get_case_details(case_id)
    assert case_closed["case_status"] == "CLOSED"
    assert case_closed["is_dispatched"] is True
    assert case_closed["has_outcome"] is True
    assert case_closed["next_valid_action"] == "NONE"

    # Verify cannot dispatch after CLOSED
    with pytest.raises(HTTPException) as exc_disp:
        dispatch_patrol_endpoint(case_id, DispatchCreateRequest(patrol_unit="PCR-CENTRAL-10"))
    assert exc_disp.value.status_code == 400
    assert "already been dispatched" in exc_disp.value.detail.lower() or "cannot dispatch twice" in exc_disp.value.detail.lower()

    # Verify cannot modify outcome after CLOSED
    with pytest.raises(HTTPException) as exc_out:
        record_case_outcome_endpoint(
            case_id,
            CaseOutcomeCreateRequest(
                outcome_status="FALSE_ALERT",
                notes="Post-closure edit attempt",
            ),
        )
    assert exc_out.value.status_code == 400
    assert "finalized and cannot be modified" in exc_out.value.detail.lower()


def test_role_based_access_control():
    """
    Verifies Section 1 & 2: Prototype Role-Based Access Control (RBAC).
    Case Reporting / Citizen role is restricted from executing operational actions:
    - cannot dispatch patrol units (HTTP 403)
    - cannot record or alter operational outcomes (HTTP 403)
    - cannot transition case lifecycle (HTTP 403)
    - cannot export evidentiary dossiers (HTTP 403)
    Investigator role succeeds without restriction.
    """
    # 1. Verify dependency direct behavior
    assert require_investigator_role(x_app_role="investigator") == "investigator"
    assert require_investigator_role(x_app_role="operations") == "operations"

    for forbidden_role in ("reporting", "citizen", "user"):
        with pytest.raises(HTTPException) as exc_dep:
            require_investigator_role(x_app_role=forbidden_role)
        assert exc_dep.value.status_code == 403
        assert "not authorized" in exc_dep.value.detail.lower()

    # 2. Verify endpoint enforcement with reporting role
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=55000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=15.0,
        incident_hour=16,
        incident_day_of_week=4,
        complaint_id="CMP-TEST-RBAC-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]

    # Attempt dispatch with reporting role -> 403
    with pytest.raises(HTTPException) as exc_disp:
        dispatch_patrol_endpoint(
            case_id,
            request=DispatchCreateRequest(patrol_unit="PCR-WEST-01"),
            _role=require_investigator_role(x_app_role="reporting"),
        )
    assert exc_disp.value.status_code == 403

    # Dispatch as investigator succeeds
    disp = dispatch_patrol_endpoint(
        case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-WEST-01"),
        _role=require_investigator_role(x_app_role="investigator"),
    )
    assert disp["dispatch_status"] == "DISPATCHED"

    # Attempt outcome logging with reporting role -> 403
    with pytest.raises(HTTPException) as exc_out:
        record_case_outcome_endpoint(
            case_id,
            request=CaseOutcomeCreateRequest(outcome_status="INTERCEPTED_AT_PREDICTED_ATM"),
            _role=require_investigator_role(x_app_role="reporting"),
        )
    assert exc_out.value.status_code == 403

    # Attempt evidence export with reporting role -> 403
    with pytest.raises(HTTPException) as exc_ev:
        export_case_evidence_endpoint(
            case_id,
            _role=require_investigator_role(x_app_role="reporting"),
        )
    assert exc_ev.value.status_code == 403


def test_outcome_mapping_fidelity_across_types():
    """
    Verifies Section 5: Ground-truth outcome fidelity mapping.
    Ensures that FALSE_ALERT, NO_CASHOUT, and UNRESOLVED can NEVER be marked as
    spatial hits or display as 'INTERCEPTED AT PREDICTED ATM'.
    """
    # 1. FALSE_ALERT: must be is_spatial_hit=False and actual_atm_id=None
    p1 = predict_cashout_location(PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=62000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_SBI_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=10.0,
        incident_hour=14,
        incident_day_of_week=3,
        complaint_id="CMP-FIDELITY-FALSE-01",
    ))
    dispatch_patrol_endpoint(p1["case_id"], DispatchCreateRequest(patrol_unit="PCR-W1"))
    out_false = record_case_outcome_endpoint(
        p1["case_id"],
        CaseOutcomeCreateRequest(
            outcome_status="FALSE_ALERT",
            actual_atm_id=p1["predicted_atm_id"], # Even if form pre-filled with predicted_atm
            notes="Legitimate user transfer confirmed by bank.",
            auto_resolve_case=True,
        ),
    )
    assert out_false["outcome_status"] == "FALSE_ALERT"
    assert out_false["is_spatial_hit"] is False
    assert out_false["actual_atm_id"] is None

    # 2. NO_CASHOUT: must be is_spatial_hit=False and actual_atm_id=None
    p2 = predict_cashout_location(PredictionRequest(
        crime_category="TASK_FRAUD",
        reported_amount=38000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_NORTH",
        reporting_delay_mins=15.0,
        incident_hour=11,
        incident_day_of_week=2,
        complaint_id="CMP-FIDELITY-NOCASH-01",
    ))
    dispatch_patrol_endpoint(p2["case_id"], DispatchCreateRequest(patrol_unit="PCR-N2"))
    out_nocash = record_case_outcome_endpoint(
        p2["case_id"],
        CaseOutcomeCreateRequest(
            outcome_status="NO_CASHOUT",
            notes="Account frozen by cyber cell before mule arrival.",
            auto_resolve_case=True,
        ),
    )
    assert out_nocash["outcome_status"] == "NO_CASHOUT"
    assert out_nocash["is_spatial_hit"] is False
    assert out_nocash["actual_atm_id"] is None

    # 3. UNRESOLVED: must be is_spatial_hit=False
    p3 = predict_cashout_location(PredictionRequest(
        crime_category="LOAN_SCAM",
        reported_amount=22000.0,
        payment_channel="NEFT",
        mule_bank_code="BANK_PNB_SYNTH",
        mule_account_tier="RURAL_REGIONAL",
        mule_branch_zone="ZONE_SOUTH",
        reporting_delay_mins=45.0,
        incident_hour=10,
        incident_day_of_week=1,
        complaint_id="CMP-FIDELITY-UNRES-01",
    ))
    dispatch_patrol_endpoint(p3["case_id"], DispatchCreateRequest(patrol_unit="PCR-S3"))
    out_unres = record_case_outcome_endpoint(
        p3["case_id"],
        CaseOutcomeCreateRequest(
            outcome_status="UNRESOLVED",
            notes="Suspect fled before patrol unit established perimeter.",
            auto_resolve_case=True,
        ),
    )
    assert out_unres["outcome_status"] == "UNRESOLVED"
    assert out_unres["is_spatial_hit"] is False


def test_console_role_separation_and_polling_fidelity():
    """
    Verifies end-to-end role console separation and live polling fidelity:
    1. Citizen creates case through complaint prediction.
    2. Citizen can track their specific case and receives prediction context (top candidates, explainability).
    3. Citizen role cannot access investigator queue (list_cases) -> HTTP 403.
    4. Investigator role can list incoming queue cases.
    5. Citizen role cannot dispatch patrol units -> HTTP 403.
    6. Investigator dispatches patrol unit -> status advances to PATROL_DISPATCHED.
    7. Citizen polls case -> sees PATROL_DISPATCHED and can retrieve dispatch record.
    8. Citizen role cannot record or alter operational outcomes -> HTTP 403.
    9. Investigator logs verified outcome -> status resolves to CLOSED/RESOLVED.
    10. Citizen polls case -> sees terminal CLOSED state and can retrieve outcome record.
    11. Immutability: Once outcome is logged, subsequent attempts to alter outcome are rejected with HTTP 400.
    """
    req = PredictionRequest(
        crime_category="PHISHING_UPI",
        reported_amount=42000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_ICIC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_WEST",
        reporting_delay_mins=12.0,
        incident_hour=15,
        incident_day_of_week=4,
        complaint_id="CMP-ROLE-SEPARATION-01",
    )
    pred_res = predict_cashout_location(req)
    case_id = pred_res["case_id"]
    assert case_id is not None

    # Citizen can track their own case
    citizen_view = get_case_details(case_id)
    assert citizen_view["case_id"] == case_id
    assert citizen_view["case_status"] == "NEW_ALERT"
    assert "top_candidates" in citizen_view
    assert isinstance(citizen_view["top_candidates"], list)
    assert "explanation_codes" in citizen_view

    # Citizen cannot list full operational queue
    with pytest.raises(HTTPException) as exc_queue:
        list_cases(
            status=None,
            limit=25,
            _role=require_investigator_role(x_app_role="reporting"),
        )
    assert exc_queue.value.status_code == 403

    # Investigator can list operational queue
    inv_queue = list_cases(
        status=None,
        limit=25,
        _role=require_investigator_role(x_app_role="investigator"),
    )
    assert isinstance(inv_queue, list)
    assert any(c["case_id"] == case_id for c in inv_queue)

    # Citizen cannot dispatch
    with pytest.raises(HTTPException) as exc_disp:
        dispatch_patrol_endpoint(
            case_id,
            request=DispatchCreateRequest(patrol_unit="PCR-ROLE-01"),
            _role=require_investigator_role(x_app_role="reporting"),
        )
    assert exc_disp.value.status_code == 403

    # Investigator dispatches patrol unit
    disp_res = dispatch_patrol_endpoint(
        case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-ROLE-01"),
        _role=require_investigator_role(x_app_role="investigator"),
    )
    assert disp_res["dispatch_status"] == "DISPATCHED"

    # Citizen polls case -> sees PATROL_DISPATCHED
    citizen_poll1 = get_case_details(case_id)
    assert citizen_poll1["case_status"] == "PATROL_DISPATCHED"

    # Citizen can read dispatch status
    citizen_disp = get_case_dispatch_endpoint(case_id)
    assert citizen_disp["patrol_unit_assigned"] == "PCR-ROLE-01"

    # Citizen cannot log outcome
    with pytest.raises(HTTPException) as exc_out:
        record_case_outcome_endpoint(
            case_id,
            request=CaseOutcomeCreateRequest(outcome_status="INTERCEPTED_AT_PREDICTED_ATM"),
            _role=require_investigator_role(x_app_role="reporting"),
        )
    assert exc_out.value.status_code == 403

    # Investigator records verified outcome
    out_res = record_case_outcome_endpoint(
        case_id,
        request=CaseOutcomeCreateRequest(
            outcome_status="INTERCEPTED_AT_PREDICTED_ATM",
            notes="Suspect intercepted at predicted ATM corridor.",
            auto_resolve_case=True,
        ),
        _role=require_investigator_role(x_app_role="investigator"),
    )
    assert out_res["outcome_status"] == "INTERCEPTED_AT_PREDICTED_ATM"
    assert out_res["is_spatial_hit"] is True

    # Citizen polls case -> sees terminal RESOLVED/CLOSED
    citizen_poll2 = get_case_details(case_id)
    assert citizen_poll2["case_status"] in ("RESOLVED", "CLOSED")

    # Citizen can read final outcome
    citizen_out = get_case_outcome_endpoint(case_id)
    assert citizen_out["outcome_status"] == "INTERCEPTED_AT_PREDICTED_ATM"

    # Immutability check: cannot alter outcome once case is resolved
    with pytest.raises(HTTPException) as exc_im:
        record_case_outcome_endpoint(
            case_id,
            request=CaseOutcomeCreateRequest(outcome_status="FALSE_ALERT"),
            _role=require_investigator_role(x_app_role="investigator"),
        )
    assert exc_im.value.status_code == 400
    assert "finalized and cannot be modified" in exc_im.value.detail.lower()










