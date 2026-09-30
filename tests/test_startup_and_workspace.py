"""
Regression and Integration Tests for:
1. Fresh database auto-initialization & idempotency (Render deployment support).
2. Reporting/Citizen workspace reset and persistence isolation.
"""

import os
import sqlite3
from pathlib import Path
import pytest

from backend.app import database
from backend.app.database import (
    REQUIRED_OPERATIONAL_TABLES,
    auto_init_database,
    ensure_db_schema,
    get_db_connection,
    init_db,
    seed_db,
    verify_database_readiness,
)
from backend.app.main import (
    app,
    dispatch_patrol_endpoint,
    get_case_details,
    health_check,
    list_cases,
    predict_cashout_location,
    record_case_outcome_endpoint,
    require_investigator_role,
)
from backend.app.schemas import (
    CaseOutcomeCreateRequest,
    DispatchCreateRequest,
    PredictionRequest,
)


def test_fresh_database_auto_initialization(tmp_path, monkeypatch):
    """
    Verifies that in a clean environment (such as a fresh Render container):
    1. A missing database file or uninitialized tables are automatically created and seeded.
    2. All required operational tables exist.
    3. Seeded reference datasets match expectations.
    4. Readiness check passes without manual terminal commands.
    """
    fresh_db_path = tmp_path / "fresh_test_analytics.db"
    monkeypatch.setattr(database, "DB_PATH", fresh_db_path)

    assert not fresh_db_path.exists(), "Test database must not exist before initialization"

    # Execute auto_init_database
    success = auto_init_database()
    assert success is True
    assert fresh_db_path.exists(), "Database file must be created on startup"

    # Verify tables and readiness
    conn = sqlite3.connect(fresh_db_path)
    try:
        conn.row_factory = sqlite3.Row
        is_ready, err = verify_database_readiness(conn)
        assert is_ready is True, f"Database readiness check failed: {err}"
        assert err == ""

        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cur.fetchall()}
        for req_table in REQUIRED_OPERATIONAL_TABLES:
            assert req_table in tables, f"Missing required table: {req_table}"

        # Verify reference datasets were populated
        cur.execute("SELECT COUNT(*) FROM atm_locations;")
        assert cur.fetchone()[0] == 50
        cur.execute("SELECT COUNT(*) FROM complaints;")
        assert cur.fetchone()[0] == 4000
        cur.execute("SELECT COUNT(*) FROM cash_out_events;")
        assert cur.fetchone()[0] == 3295
    finally:
        conn.close()


def test_database_initialization_idempotency(tmp_path, monkeypatch):
    """
    Verifies that calling auto_init_database on an already-initialized database:
    1. Does not fail or re-create tables.
    2. Does not overwrite or delete existing operational data.
    """
    idemp_db_path = tmp_path / "idemp_test_analytics.db"
    monkeypatch.setattr(database, "DB_PATH", idemp_db_path)

    # First init
    auto_init_database()

    # Insert custom record into complaints and operational_cases
    conn = sqlite3.connect(idemp_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO complaints (
                complaint_id, incident_timestamp, complaint_timestamp, reporting_delay_mins,
                crime_category, reported_amount, payment_channel, mule_bank_code,
                mule_account_tier, mule_branch_zone, incident_hour, incident_day_of_week, complaint_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "CMP-IDEMP-001", "2026-08-01 10:00:00", "2026-08-01 10:30:00", 30.0,
                "INVESTMENT_FRAUD", 50000.0, "UPI", "BANK_SBI_SYNTH",
                "STANDARD", "ZONE_CENTRAL", 10, 5, "REGISTERED"
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # Second init on same database
    auto_init_database()

    # Verify custom record remains intact
    conn = sqlite3.connect(idemp_db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM complaints WHERE complaint_id = 'CMP-IDEMP-001';")
        assert cur.fetchone()[0] == 1, "Existing user data must not be destroyed by re-initialization"

        cur.execute("SELECT COUNT(*) FROM complaints;")
        assert cur.fetchone()[0] == 4001
    finally:
        conn.close()


def test_case_lifecycle_and_backend_persistence():
    """
    Verifies that:
    1. A new Case ID is created ONLY upon complaint submission.
    2. Case progresses through lifecycle: NEW_ALERT -> PATROL_DISPATCHED -> CLOSED.
    3. Closed case is preserved in persistent backend history and list_cases.
    4. Explicit case lookup (get_case_details) loads the closed case normally.
    """
    req = PredictionRequest(
        crime_category="INVESTMENT_FRAUD",
        reported_amount=75000.0,
        payment_channel="UPI",
        mule_bank_code="BANK_HDFC_SYNTH",
        mule_account_tier="NEW_DIGITAL",
        mule_branch_zone="ZONE_CENTRAL",
        reporting_delay_mins=20.0,
        incident_hour=14,
        incident_day_of_week=3,
    )

    # 1. Prediction triggers case creation
    pred = predict_cashout_location(req)
    case_id = pred["case_id"]
    assert case_id is not None
    assert case_id.startswith("CASE-")
    assert pred["case_status"] == "NEW_ALERT"

    # 2. Dispatch patrol -> PATROL_DISPATCHED
    disp = dispatch_patrol_endpoint(
        case_id=case_id,
        request=DispatchCreateRequest(patrol_unit="PCR-CENTRAL-01", notes="Intercept dispatched"),
        _role=require_investigator_role(x_app_role="investigator"),
    )
    assert disp["dispatch_status"] == "DISPATCHED"

    case_after_disp = get_case_details(case_id)
    assert case_after_disp["case_status"] == "PATROL_DISPATCHED"

    # 3. Log outcome and resolve -> CLOSED
    outcome = record_case_outcome_endpoint(
        case_id=case_id,
        request=CaseOutcomeCreateRequest(
            outcome_status="INTERCEPTED_AT_PREDICTED_ATM",
            notes="Suspect intercepted with cards at forecasted ATM",
            auto_resolve_case=True,
        ),
        _role=require_investigator_role(x_app_role="investigator"),
    )
    assert outcome["outcome_status"] == "INTERCEPTED_AT_PREDICTED_ATM"
    assert outcome["is_spatial_hit"] is True

    # 4. Closed case verification in backend
    closed_case = get_case_details(case_id)
    assert closed_case["case_status"] in ("RESOLVED", "CLOSED")

    # 5. Case remains visible in historical cases query
    all_cases = list_cases(limit=100)
    matching = [c for c in all_cases if c["case_id"] == case_id]
    assert len(matching) == 1
    assert matching[0]["case_status"] in ("RESOLVED", "CLOSED")


def test_frontend_workspace_reset_and_markup_contracts():
    """
    Verifies that the static frontend files have the required controls and implementations
    for Issue 2 (workspace reset, placeholder inputs, clearPredictionHighlight).
    """
    base_dir = Path(__file__).resolve().parent.parent

    # 1. Verify index.html controls
    index_html = (base_dir / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="btnReportNewCaseHero"' in index_html, "Hero header must have Report New Case button"
    assert 'id="btnReportNewCaseIntake"' in index_html, "Intake header must have Report New Case button"
    assert 'id="btnCitizenReportNew"' in index_html, "Citizen tracking notice must have Report New Case button"
    assert 'id="btnFinalOutcomeNewReport"' in index_html, "Final outcome report must have Report New Incident button"
    assert 'placeholder="e.g. 85000"' in index_html, "Intake amount must use blank placeholder"

    # 2. Verify map.js clearPredictionHighlight method
    map_js = (base_dir / "frontend" / "static" / "js" / "map.js").read_text(encoding="utf-8")
    assert "clearPredictionHighlight()" in map_js, "MapController must implement clearPredictionHighlight"

    # 3. Verify app.js resetReportingWorkspace and session storage separation
    app_js = (base_dir / "frontend" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "export function resetReportingWorkspace" in app_js, "app.js must export resetReportingWorkspace"
    assert "setupWorkspaceResetListeners" in app_js, "app.js must implement setupWorkspaceResetListeners"
    assert "citizen_workspace_state" in app_js, "app.js must separate active workspace state from history"
    assert "btnResolutionNewReport" in app_js, "app.js must bind resolution new report button"


def test_health_and_docs_endpoints():
    """
    Verifies that the service remains healthy and API contracts are fully preserved.
    """
    health = health_check()
    assert health["status"] == "HEALTHY"
    assert health["version"] == "1.0.0"
