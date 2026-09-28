"""
Database Connection & Explicit Seeding Module.

Uses Python's standard-library sqlite3 module with foreign keys enabled.
Seeding is strictly explicit via CLI `--setup-db` and reads CSVs in read-only mode.
Never modifies source CSV files.
"""

import csv
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "cybercrime_analytics.db"

# Import table schemas
from backend.app.models import ALL_TABLE_DDL


@contextmanager
def get_db_connection():
    """
    Context manager yielding a thread-safe sqlite3 connection
    with foreign key enforcement and dictionary-accessible rows.
    """
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


REQUIRED_OPERATIONAL_TABLES = {"atm_locations", "complaints", "cash_out_events", "predictions", "operational_cases", "patrol_dispatches"}


def verify_database_readiness(conn) -> tuple[bool, str]:
    """
    Verifies that the SQLite database is initialized and contains all required operational tables.
    Returns (is_ready, error_message).
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = {row[0] for row in cur.fetchall()}
        missing = REQUIRED_OPERATIONAL_TABLES - existing_tables
        if missing:
            return False, f"Database service is uninitialized or missing required operational tables: {', '.join(sorted(missing))}."
        return True, ""
    except Exception:
        return False, "Database connection error or uninitialized database file."


def ensure_db_schema():
    """Ensures operational_cases and patrol_dispatches tables and newly added columns exist for backwards compatibility."""
    if not DB_PATH.exists():
        return
    with get_db_connection() as conn:
        cur = conn.cursor()
        from backend.app.models import SQL_CREATE_OPERATIONAL_CASES, SQL_CREATE_PATROL_DISPATCHES
        cur.execute(SQL_CREATE_OPERATIONAL_CASES)
        cur.execute(SQL_CREATE_PATROL_DISPATCHES)

        cur.execute("PRAGMA table_info(predictions);")
        existing_cols = {row["name"] for row in cur.fetchall()}
        if existing_cols:
            if "priority_score" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN priority_score INTEGER DEFAULT 0;")
            if "priority_level" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN priority_level VARCHAR(20) DEFAULT 'LOW';")
            if "priority_reasons_json" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN priority_reasons_json TEXT DEFAULT '[]';")
            if "playbook_json" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN playbook_json TEXT DEFAULT '{}';")
            if "alert_state" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN alert_state VARCHAR(20) DEFAULT 'NEW';")
            if "occurrence_count" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN occurrence_count INTEGER DEFAULT 1;")
            if "escalation_reason" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN escalation_reason TEXT DEFAULT '';")
            if "parent_alert_id" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN parent_alert_id VARCHAR(32) DEFAULT NULL;")
            if "case_id" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN case_id VARCHAR(32) DEFAULT NULL;")
            if "case_status" not in existing_cols:
                cur.execute("ALTER TABLE predictions ADD COLUMN case_status VARCHAR(30) DEFAULT 'NEW_ALERT';")


def init_db():
    """Creates the SQLite database tables if they do not already exist."""
    print(f"Initializing database at: {DB_PATH}")
    with get_db_connection() as conn:
        for ddl in ALL_TABLE_DDL:
            conn.execute(ddl)
    ensure_db_schema()
    print("  [OK] Table schemas verified.")


def seed_db():
    """
    Explicitly populates SQLite tables from existing CSV datasets in read-only mode.
    Never modifies, overwrites, or transforms the source CSV files.
    Idempotent: skips if data is already present.
    """
    print("\nExecuting explicit database seeding from source CSVs (Read-Only Mode)...")

    atm_csv = DATA_DIR / "atm_locations.csv"
    cmp_csv = DATA_DIR / "complaints.csv"
    evt_csv = DATA_DIR / "cash_out_events.csv"

    assert atm_csv.exists(), f"Missing required file: {atm_csv}"
    assert cmp_csv.exists(), f"Missing required file: {cmp_csv}"
    assert evt_csv.exists(), f"Missing required file: {evt_csv}"

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Seed ATM Locations
        cursor.execute("SELECT COUNT(*) FROM atm_locations;")
        existing_atms = cursor.fetchone()[0]
        if existing_atms == 0:
            with open(atm_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                atms = [
                    (
                        r["atm_id"],
                        r["bank_code"],
                        float(r["latitude"]),
                        float(r["longitude"]),
                        r["zone_id"],
                        r["location_type"],
                        r["cash_capacity_level"],
                        int(r["historical_cashout_count"]),
                        r["operating_status"],
                    )
                    for r in reader
                ]
            cursor.executemany(
                """
                INSERT INTO atm_locations (
                    atm_id, bank_code, latitude, longitude, zone_id,
                    location_type, cash_capacity_level, historical_cashout_count, operating_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                atms,
            )
            print(f"  [OK] Seeded {len(atms)} ATM locations.")
        else:
            print(f"  [SKIP] atm_locations already contains {existing_atms} rows.")

        # 2. Seed Complaints
        cursor.execute("SELECT COUNT(*) FROM complaints;")
        existing_cmps = cursor.fetchone()[0]
        if existing_cmps == 0:
            with open(cmp_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                complaints = [
                    (
                        r["complaint_id"],
                        r["incident_timestamp"],
                        r["complaint_timestamp"],
                        float(r["reporting_delay_mins"]),
                        r["crime_category"],
                        float(r["reported_amount"]),
                        r["payment_channel"],
                        r["mule_bank_code"],
                        r["mule_account_tier"],
                        r["mule_branch_zone"],
                        int(r["incident_hour"]),
                        int(r["incident_day_of_week"]),
                        r["complaint_status"],
                    )
                    for r in reader
                ]
            cursor.executemany(
                """
                INSERT INTO complaints (
                    complaint_id, incident_timestamp, complaint_timestamp, reporting_delay_mins,
                    crime_category, reported_amount, payment_channel, mule_bank_code,
                    mule_account_tier, mule_branch_zone, incident_hour, incident_day_of_week,
                    complaint_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                complaints,
            )
            print(f"  [OK] Seeded {len(complaints)} complaints.")
        else:
            print(f"  [SKIP] complaints already contains {existing_cmps} rows.")

        # 3. Seed Cash-Out Events
        cursor.execute("SELECT COUNT(*) FROM cash_out_events;")
        existing_evts = cursor.fetchone()[0]
        if existing_evts == 0:
            with open(evt_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                events = [
                    (
                        r["event_id"],
                        r["complaint_id"],
                        r["atm_id"],
                        r["withdrawal_timestamp"],
                        float(r["time_to_cashout_mins"]),
                        float(r["withdrawal_amount"]),
                        r["interception_status"],
                    )
                    for r in reader
                ]
            cursor.executemany(
                """
                INSERT INTO cash_out_events (
                    event_id, complaint_id, atm_id, withdrawal_timestamp,
                    time_to_cashout_mins, withdrawal_amount, interception_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                events,
            )
            print(f"  [OK] Seeded {len(events)} cash-out events.")
        else:
            print(f"  [SKIP] cash_out_events already contains {existing_evts} rows.")

    print("\nDatabase setup complete. Verification status:")
    with get_db_connection() as conn:
        cur = conn.cursor()
        for tbl in ["atm_locations", "complaints", "cash_out_events", "predictions"]:
            cur.execute(f"SELECT COUNT(*) FROM {tbl};")
            count = cur.fetchone()[0]
            print(f"  - Table '{tbl}': {count:,} rows")


if __name__ == "__main__":
    if "--setup-db" in sys.argv:
        init_db()
        seed_db()
    else:
        print("Usage: python backend/app/database.py --setup-db")
