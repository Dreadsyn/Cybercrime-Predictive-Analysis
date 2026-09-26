"""
Synthetic Data Generator for Cybercrime Predictive Analytics Framework.

Problem Statement:
"Development of a Predictive Analytics Framework for Cybercrime Complaints to Forecast
Likely Cash Withdrawal Locations in Advance, Enabling Generation of Actionable Intelligence
for Timely and Proactive Cybercrime Intervention."

This module produces 100% synthetic, non-PII, relationally consistent datasets:
1. atm_locations.csv
2. complaints.csv
3. cash_out_events.csv (Historical ground truth only)

STRICT DATA-LEAKAGE RULE ENFORCED:
- No future cash-out fields exist in complaints.csv.
- All target labels (atm_id, withdrawal_timestamp, etc.) reside exclusively in cash_out_events.csv.
"""

import os
import math
import random
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

# ==============================================================================
# CONFIGURATION & CONSTANTS (FIXED SEED FOR REPRODUCIBILITY)
# ==============================================================================
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Geographic simulation centers (Metropolitan Cybercrime Jurisdiction)
ZONES = {
    "ZONE_CENTRAL": {"lat": 28.6300, "lon": 77.2200, "desc": "Commercial & financial core"},
    "ZONE_NORTH":   {"lat": 28.7000, "lon": 77.1500, "desc": "Transport corridor & mixed residential"},
    "ZONE_SOUTH":   {"lat": 28.5300, "lon": 77.2000, "desc": "Affluent commercial & institutional hub"},
    "ZONE_EAST":    {"lat": 28.6200, "lon": 77.2900, "desc": "Dense residential & industrial fringe"},
    "ZONE_WEST":    {"lat": 28.6500, "lon": 77.1000, "desc": "Suburban market & transport nexus"},
}

BANKS = [
    ("BANK_SBI_SYNTH", 0.35),
    ("BANK_HDFC_SYNTH", 0.25),
    ("BANK_ICIC_SYNTH", 0.20),
    ("BANK_PNB_SYNTH", 0.12),
    ("BANK_AXIS_SYNTH", 0.08),
]
BANK_CODES = [b[0] for b in BANKS]
BANK_PROBS = [b[1] for b in BANKS]

CRIME_CATEGORIES = {
    "INVESTMENT_FRAUD": {"weight": 0.28, "amount_range": (35000, 200000), "delay_mu": 3.8, "delay_sigma": 0.6},
    "TASK_FRAUD":       {"weight": 0.24, "amount_range": (20000, 100000), "delay_mu": 3.5, "delay_sigma": 0.5},
    "PHISHING_UPI":     {"weight": 0.26, "amount_range": (5000, 60000),   "delay_mu": 3.0, "delay_sigma": 0.5},
    "EXTORTION":        {"weight": 0.12, "amount_range": (10000, 50000),  "delay_mu": 3.4, "delay_sigma": 0.7},
    "LOAN_SCAM":        {"weight": 0.10, "amount_range": (5000, 40000),   "delay_mu": 4.2, "delay_sigma": 0.6},
}

PAYMENT_CHANNELS = [
    ("UPI", 0.55),
    ("IMPS", 0.30),
    ("NEFT", 0.15),
]

MULE_ACCOUNT_TIERS = [
    ("NEW_DIGITAL", 0.50),
    ("STANDARD", 0.32),
    ("RURAL_REGIONAL", 0.18),
]

ATM_LOCATION_TYPES = [
    ("STANDALONE_KIOSK", 0.45),
    ("BRANCH_ATTACHED", 0.35),
    ("TRANSIT_METRO", 0.20),
]

CASH_CAPACITY_LEVELS = [
    ("HIGH", 0.30),
    ("MEDIUM", 0.50),
    ("LOW", 0.20),
]


def haversine_km(lat1, lon1, lat2, lon2):
    """Calculates geodesic distance between two points in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


# ==============================================================================
# 1. GENERATE ATM LOCATIONS
# ==============================================================================
def generate_atm_locations(num_atms: int = 50) -> pd.DataFrame:
    """Generates synthetic physical ATM locations distributed across 5 zones."""
    zone_keys = list(ZONES.keys())
    atms_per_zone = num_atms // len(zone_keys)

    records = []
    atm_counter = 1

    for zone_id in zone_keys:
        zone_center = ZONES[zone_id]
        for _ in range(atms_per_zone):
            atm_id = f"ATM-{zone_id.split('_')[1][:2]}-{atm_counter:03d}"
            bank_code = np.random.choice(BANK_CODES, p=BANK_PROBS)

            # Scatter ATMs around zone center (std dev ~ 1.5 km = ~0.015 degrees)
            lat = round(float(np.random.normal(zone_center["lat"], 0.018)), 5)
            lon = round(float(np.random.normal(zone_center["lon"], 0.018)), 5)

            loc_type = np.random.choice(
                [t[0] for t in ATM_LOCATION_TYPES],
                p=[t[1] for t in ATM_LOCATION_TYPES]
            )
            capacity = np.random.choice(
                [c[0] for c in CASH_CAPACITY_LEVELS],
                p=[c[1] for c in CASH_CAPACITY_LEVELS]
            )
            # Most ATMs are online; small operational outage rate
            op_status = np.random.choice(
                ["ONLINE", "MAINTENANCE", "OUT_OF_CASH"],
                p=[0.92, 0.05, 0.03]
            )

            records.append({
                "atm_id": atm_id,
                "bank_code": bank_code,
                "latitude": lat,
                "longitude": lon,
                "zone_id": zone_id,
                "location_type": loc_type,
                "cash_capacity_level": capacity,
                "historical_cashout_count": 0,  # Will be reconciled after event generation
                "operating_status": op_status,
            })
            atm_counter += 1

    df_atms = pd.DataFrame(records)
    return df_atms


# ==============================================================================
# 2. GENERATE CYBERCRIME COMPLAINTS & GROUND-TRUTH CASH-OUT EVENTS
# ==============================================================================
def generate_complaints_and_cashouts(
    df_atms: pd.DataFrame,
    num_complaints: int = 4000,
    start_date: datetime = datetime(2026, 3, 1, 0, 0, 0),
    duration_days: int = 180,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates synthetic complaints and corresponding historical cash-out events
    with sound behavioral, geographic, and temporal signals.
    """
    cat_keys = list(CRIME_CATEGORIES.keys())
    cat_weights = [CRIME_CATEGORIES[k]["weight"] for k in cat_keys]

    channel_keys = [c[0] for c in PAYMENT_CHANNELS]
    channel_weights = [c[1] for c in PAYMENT_CHANNELS]

    tier_keys = [t[0] for t in MULE_ACCOUNT_TIERS]
    tier_weights = [t[1] for t in MULE_ACCOUNT_TIERS]

    zone_keys = list(ZONES.keys())

    complaints = []
    cashouts = []

    # Map ATMs by ID for quick attribute retrieval
    atm_dict = df_atms.set_index("atm_id").to_dict(orient="index")
    atm_list = df_atms["atm_id"].tolist()

    event_counter = 1

    for i in range(1, num_complaints + 1):
        complaint_id = f"CMP-2026-{i:05d}"

        # 1. Incident timestamp across simulation horizon with realistic diurnal curve
        day_offset = random.uniform(0, duration_days)
        # Peak hours: 10:00 to 22:00
        hour_sample = int(np.clip(np.random.normal(15, 4.5), 0, 23))
        minute_sample = random.randint(0, 59)
        second_sample = random.randint(0, 59)

        base_date = start_date + timedelta(days=int(day_offset))
        incident_ts = datetime(
            base_date.year, base_date.month, base_date.day,
            hour_sample, minute_sample, second_sample
        )

        # 2. Modus Operandi / Category
        category = np.random.choice(cat_keys, p=cat_weights)
        cat_cfg = CRIME_CATEGORIES[category]

        # 3. Reported financial loss
        low_amt, high_amt = cat_cfg["amount_range"]
        reported_amount = round(float(np.random.uniform(low_amt, high_amt)), 2)

        # 4. Payment channel
        channel = np.random.choice(channel_keys, p=channel_weights)

        # 5. Mule account characteristics
        mule_bank = np.random.choice(BANK_CODES, p=BANK_PROBS)
        mule_tier = np.random.choice(tier_keys, p=tier_weights)
        mule_zone = np.random.choice(zone_keys)

        # 6. Reporting delay (log-normal distribution in minutes)
        raw_delay = np.random.lognormal(cat_cfg["delay_mu"], cat_cfg["delay_sigma"])
        reporting_delay_mins = round(float(np.clip(raw_delay, 12.0, 720.0)), 1)

        complaint_ts = incident_ts + timedelta(minutes=reporting_delay_mins)

        # Add complaint record (STRICTLY NO FUTURE TARGET COLUMNS)
        complaints.append({
            "complaint_id": complaint_id,
            "incident_timestamp": incident_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "complaint_timestamp": complaint_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "reporting_delay_mins": reporting_delay_mins,
            "crime_category": category,
            "reported_amount": reported_amount,
            "payment_channel": channel,
            "mule_bank_code": mule_bank,
            "mule_account_tier": mule_tier,
            "mule_branch_zone": mule_zone,
            "incident_hour": incident_ts.hour,
            "incident_day_of_week": incident_ts.weekday(),
            "complaint_status": "REGISTERED",
        })

        # ======================================================================
        # 7. SIMULATE GROUND-TRUTH CASH-OUT (HISTORICAL OUTCOME ONLY)
        # ======================================================================
        # ~80% of cyber frauds target physical ATM cash-out; others are diverted online/frozen
        targets_atm = random.random() < 0.82

        if targets_atm:
            # Behavioral choice model: Calculate attractiveness score for every ATM
            # Factors: Bank match (on-us), zone proximity, standalone kiosk, cash capacity
            scores = []
            mule_zone_center = ZONES[mule_zone]

            for atm_id in atm_list:
                atm = atm_dict[atm_id]

                # Filter out offline ATMs at simulation time
                if atm["operating_status"] != "ONLINE":
                    scores.append(0.0001)
                    continue

                # A. Bank affinity (mules prioritize own bank ATM network)
                bank_match = 1.0 if atm["bank_code"] == mule_bank else 0.15

                # B. Geospatial proximity to mule account branch zone
                dist_km = haversine_km(
                    mule_zone_center["lat"], mule_zone_center["lon"],
                    atm["latitude"], atm["longitude"]
                )
                proximity_score = math.exp(-dist_km / 4.5)  # Decay parameter ~4.5 km

                # C. Kiosk preference (unmonitored standalone kiosks preferred)
                loc_type_weight = 1.6 if atm["location_type"] == "STANDALONE_KIOSK" else (
                    1.2 if atm["location_type"] == "TRANSIT_METRO" else 0.7
                )

                # D. High capacity preference for large sums
                capacity_weight = 1.5 if (reported_amount > 50000 and atm["cash_capacity_level"] == "HIGH") else 1.0

                score = (bank_match ** 1.3) * (proximity_score ** 1.5) * loc_type_weight * capacity_weight
                scores.append(score)

            total_score = sum(scores)
            probabilities = [s / total_score for s in scores]

            # Sample the ground truth ATM chosen by the criminal syndicate
            chosen_atm_id = np.random.choice(atm_list, p=probabilities)

            # Temporal latency until cash-out: depends heavily on payment channel velocity
            if channel == "UPI":
                transit_mu, transit_sigma = 3.6, 0.45  # ~25-70 mins
            elif channel == "IMPS":
                transit_mu, transit_sigma = 4.0, 0.40  # ~40-100 mins
            else:  # NEFT
                transit_mu, transit_sigma = 4.8, 0.35  # ~90-200 mins

            time_to_cashout = float(np.clip(np.random.lognormal(transit_mu, transit_sigma), 15.0, 480.0))
            withdrawal_ts = incident_ts + timedelta(minutes=time_to_cashout)

            # Amount withdrawn (capped to reported loss and max ATM single draw limit)
            withdrawal_amount = min(reported_amount, float(random.choice([10000, 20000, 40000, 50000])))

            # Historical police/bank intervention outcome
            # Preemptive interception occurs only if reporting was fast enough before withdrawal
            interception_status = "INTERCEPTED" if (complaint_ts < withdrawal_ts and (withdrawal_ts - complaint_ts).total_seconds() > 1800 and random.random() < 0.25) else "SUCCESSFUL"

            cashouts.append({
                "event_id": f"EVT-2026-{event_counter:05d}",
                "complaint_id": complaint_id,
                "atm_id": chosen_atm_id,
                "withdrawal_timestamp": withdrawal_ts.strftime("%Y-%m-%d %H:%M:%S"),
                "time_to_cashout_mins": round(time_to_cashout, 1),
                "withdrawal_amount": round(withdrawal_amount, 2),
                "interception_status": interception_status,
            })
            event_counter += 1

    df_complaints = pd.DataFrame(complaints)
    df_cashouts = pd.DataFrame(cashouts)

    # Reconcile historical cashout frequency in the ATM dataset
    event_counts = df_cashouts["atm_id"].value_counts().to_dict()
    df_atms["historical_cashout_count"] = df_atms["atm_id"].map(lambda x: event_counts.get(x, 0))

    return df_complaints, df_cashouts


# ==============================================================================
# 3. COMPREHENSIVE VALIDATION SUITE
# ==============================================================================
def validate_synthetic_datasets(
    df_atms: pd.DataFrame,
    df_complaints: pd.DataFrame,
    df_cashouts: pd.DataFrame,
) -> dict:
    """
    Validates integrity, relational correctness, and zero-data-leakage rules.
    """
    results = {}

    # A. Row counts
    results["count_atms"] = len(df_atms)
    results["count_complaints"] = len(df_complaints)
    results["count_cashouts"] = len(df_cashouts)
    assert len(df_atms) > 0, "ATM table is empty"
    assert len(df_complaints) > 0, "Complaints table is empty"
    assert len(df_cashouts) > 0, "Cashouts table is empty"

    # B. Primary key uniqueness
    assert df_atms["atm_id"].is_unique, "Duplicate ATM IDs detected!"
    assert df_complaints["complaint_id"].is_unique, "Duplicate Complaint IDs detected!"
    assert df_cashouts["event_id"].is_unique, "Duplicate Event IDs detected!"
    results["uniqueness_check"] = "PASSED"

    # C. Null value checks
    assert df_atms.isna().sum().sum() == 0, "Null values found in ATM locations!"
    assert df_complaints.isna().sum().sum() == 0, "Null values found in Complaints!"
    assert df_cashouts.isna().sum().sum() == 0, "Null values found in Cashouts!"
    results["null_check"] = "PASSED (Zero nulls)"

    # D. Foreign key integrity
    atm_id_set = set(df_atms["atm_id"])
    complaint_id_set = set(df_complaints["complaint_id"])

    invalid_atms = set(df_cashouts["atm_id"]) - atm_id_set
    invalid_complaints = set(df_cashouts["complaint_id"]) - complaint_id_set

    assert len(invalid_atms) == 0, f"Foreign key violation: Unrecognized ATMs {invalid_atms}"
    assert len(invalid_complaints) == 0, f"Foreign key violation: Unrecognized Complaints {invalid_complaints}"
    results["foreign_key_check"] = "PASSED (100% relational integrity)"

    # E. Chronological & mathematical consistency
    complaint_df_indexed = df_complaints.set_index("complaint_id")

    for _, row in df_complaints.iterrows():
        inc_ts = datetime.strptime(row["incident_timestamp"], "%Y-%m-%d %H:%M:%S")
        cmp_ts = datetime.strptime(row["complaint_timestamp"], "%Y-%m-%d %H:%M:%S")
        assert cmp_ts >= inc_ts, f"Complaint time before incident time in {row['complaint_id']}"
        diff_mins = round((cmp_ts - inc_ts).total_seconds() / 60.0, 1)
        assert abs(diff_mins - row["reporting_delay_mins"]) < 0.2, "Reporting delay math mismatch"

    for _, row in df_cashouts.iterrows():
        cmp_row = complaint_df_indexed.loc[row["complaint_id"]]
        inc_ts = datetime.strptime(cmp_row["incident_timestamp"], "%Y-%m-%d %H:%M:%S")
        wth_ts = datetime.strptime(row["withdrawal_timestamp"], "%Y-%m-%d %H:%M:%S")
        assert wth_ts >= inc_ts, f"Withdrawal before incident in event {row['event_id']}"
        diff_mins = round((wth_ts - inc_ts).total_seconds() / 60.0, 1)
        assert abs(diff_mins - row["time_to_cashout_mins"]) < 0.2, "Time to cashout math mismatch"

    results["chronological_check"] = "PASSED"

    # F. STRICT DATA-LEAKAGE CHECK
    prohibited_in_complaints = {
        "atm_id", "withdrawal_timestamp", "withdrawal_amount",
        "time_to_cashout_mins", "interception_status", "target", "label"
    }
    leaked_cols = prohibited_in_complaints.intersection(set(df_complaints.columns))
    assert len(leaked_cols) == 0, f"DATA LEAKAGE DETECTED in complaints: {leaked_cols}"
    results["leakage_check"] = "PASSED (Strict zero-leakage verified)"

    return results


# ==============================================================================
# MAIN EXECUTION ENTRY POINT
# ==============================================================================
def main():
    print("=" * 80)
    print("CYBERCRIME PREDICTIVE ANALYTICS - SYNTHETIC DATA GENERATOR")
    print(f"Random Seed: {RANDOM_SEED}")
    print("=" * 80)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[1/3] Generating ATM infrastructure dataset (50 ATMs across 5 Zones)...")
    df_atms = generate_atm_locations(num_atms=50)

    print("[2/3] Simulating 4,000 complaints and historical cash-out events...")
    df_complaints, df_cashouts = generate_complaints_and_cashouts(
        df_atms, num_complaints=4000
    )

    print("[3/3] Running automated validation and leakage checks...")
    val_results = validate_synthetic_datasets(df_atms, df_complaints, df_cashouts)
    for k, v in val_results.items():
        print(f"  [OK] {k}: {v}")

    # Export to CSV
    atm_path = DATA_DIR / "atm_locations.csv"
    complaints_path = DATA_DIR / "complaints.csv"
    cashouts_path = DATA_DIR / "cash_out_events.csv"

    df_atms.to_csv(atm_path, index=False)
    df_complaints.to_csv(complaints_path, index=False)
    df_cashouts.to_csv(cashouts_path, index=False)

    print("\nDatasets saved successfully to:", DATA_DIR)
    print(f"  - atm_locations.csv    : {len(df_atms):,} rows")
    print(f"  - complaints.csv       : {len(df_complaints):,} rows")
    print(f"  - cash_out_events.csv  : {len(df_cashouts):,} rows")
    print("=" * 80)


if __name__ == "__main__":
    main()
