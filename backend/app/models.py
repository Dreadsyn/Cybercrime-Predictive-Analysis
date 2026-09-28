"""
Database Schema Definitions for Cybercrime Predictive Analytics Framework.

Defines table DDL for:
1. atm_locations
2. complaints
3. cash_out_events (Historical ground truth)
4. predictions (Actionable intelligence logs)
"""

SQL_CREATE_ATM_LOCATIONS = """
CREATE TABLE IF NOT EXISTS atm_locations (
    atm_id VARCHAR(32) PRIMARY KEY,
    bank_code VARCHAR(20) NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    zone_id VARCHAR(50) NOT NULL,
    location_type VARCHAR(30) NOT NULL,
    cash_capacity_level VARCHAR(20) NOT NULL,
    historical_cashout_count INTEGER NOT NULL DEFAULT 0,
    operating_status VARCHAR(20) NOT NULL DEFAULT 'ONLINE'
);
"""

SQL_CREATE_COMPLAINTS = """
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id VARCHAR(32) PRIMARY KEY,
    incident_timestamp TEXT NOT NULL,
    complaint_timestamp TEXT NOT NULL,
    reporting_delay_mins REAL NOT NULL,
    crime_category VARCHAR(40) NOT NULL,
    reported_amount REAL NOT NULL,
    payment_channel VARCHAR(20) NOT NULL,
    mule_bank_code VARCHAR(20) NOT NULL,
    mule_account_tier VARCHAR(30) NOT NULL,
    mule_branch_zone VARCHAR(50) NOT NULL,
    incident_hour INTEGER NOT NULL,
    incident_day_of_week INTEGER NOT NULL,
    complaint_status VARCHAR(30) NOT NULL DEFAULT 'REGISTERED'
);
"""

SQL_CREATE_CASHOUT_EVENTS = """
CREATE TABLE IF NOT EXISTS cash_out_events (
    event_id VARCHAR(32) PRIMARY KEY,
    complaint_id VARCHAR(32) NOT NULL,
    atm_id VARCHAR(32) NOT NULL,
    withdrawal_timestamp TEXT NOT NULL,
    time_to_cashout_mins REAL NOT NULL,
    withdrawal_amount REAL NOT NULL,
    interception_status VARCHAR(30) NOT NULL DEFAULT 'SUCCESSFUL',
    FOREIGN KEY (complaint_id) REFERENCES complaints (complaint_id) ON DELETE CASCADE,
    FOREIGN KEY (atm_id) REFERENCES atm_locations (atm_id) ON DELETE CASCADE
);
"""

SQL_CREATE_PREDICTIONS = """
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id VARCHAR(32) PRIMARY KEY,
    complaint_id VARCHAR(32),
    prediction_timestamp TEXT NOT NULL,
    predicted_atm_id VARCHAR(32) NOT NULL,
    predicted_zone_id VARCHAR(50) NOT NULL,
    confidence_score REAL NOT NULL,
    top_candidates_json TEXT NOT NULL,
    predicted_window_start TEXT NOT NULL,
    predicted_window_end TEXT NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    explanation_codes_json TEXT NOT NULL,
    action_status VARCHAR(30) NOT NULL DEFAULT 'NEW_ALERT',
    priority_score INTEGER DEFAULT 0,
    priority_level VARCHAR(20) DEFAULT 'LOW',
    priority_reasons_json TEXT DEFAULT '[]',
    playbook_json TEXT DEFAULT '{}',
    alert_state VARCHAR(20) DEFAULT 'NEW',
    occurrence_count INTEGER DEFAULT 1,
    escalation_reason TEXT DEFAULT '',
    parent_alert_id VARCHAR(32) DEFAULT NULL,
    case_id VARCHAR(32) DEFAULT NULL,
    case_status VARCHAR(30) DEFAULT 'NEW_ALERT',
    FOREIGN KEY (predicted_atm_id) REFERENCES atm_locations (atm_id)
);
"""

SQL_CREATE_OPERATIONAL_CASES = """
CREATE TABLE IF NOT EXISTS operational_cases (
    case_id VARCHAR(32) PRIMARY KEY,
    parent_alert_id VARCHAR(32) NOT NULL,
    complaint_id VARCHAR(32),
    predicted_atm_id VARCHAR(32) NOT NULL,
    predicted_zone_id VARCHAR(50) NOT NULL,
    priority_score INTEGER NOT NULL DEFAULT 0,
    priority_level VARCHAR(20) NOT NULL DEFAULT 'LOW',
    intervention_window_start TEXT NOT NULL,
    intervention_window_end TEXT NOT NULL,
    case_status VARCHAR(30) NOT NULL DEFAULT 'NEW_ALERT',
    created_timestamp TEXT NOT NULL,
    updated_timestamp TEXT NOT NULL,
    notes TEXT DEFAULT '',
    FOREIGN KEY (predicted_atm_id) REFERENCES atm_locations (atm_id),
    FOREIGN KEY (parent_alert_id) REFERENCES predictions (prediction_id)
);
"""

ALL_TABLE_DDL = [
    SQL_CREATE_ATM_LOCATIONS,
    SQL_CREATE_COMPLAINTS,
    SQL_CREATE_CASHOUT_EVENTS,
    SQL_CREATE_PREDICTIONS,
    SQL_CREATE_OPERATIONAL_CASES,
]
