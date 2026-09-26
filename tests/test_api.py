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

import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.main import (
    generate_playbook_endpoint,
    get_dashboard_stats,
    get_model_information,
    get_zone_hotspots,
    health_check,
    list_atms,
    list_complaints,
    list_predictions,
    predict_cashout_location,
    serve_dashboard,
)
from backend.app.ml_engine import compute_intervention_priority
from backend.app.playbook_engine import generate_investigator_playbook
from backend.app.schemas import PlaybookRequest, PredictionRequest


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

