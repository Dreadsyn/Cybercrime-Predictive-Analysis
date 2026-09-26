"""
Model Training Pipeline for Cybercrime Predictive Analytics Framework.

Problem Statement:
"Development of a Predictive Analytics Framework for Cybercrime Complaints to Forecast
Likely Cash Withdrawal Locations in Advance, Enabling Generation of Actionable Intelligence
for Timely and Proactive Cybercrime Intervention."

Strict Protocol Enforced:
1. Eligible population: Complaints with verified cash-out events (N = 3,295).
2. Chronological Split strictly by complaint_timestamp:
   - Partition 1 (P1, earliest 60% ~ 1,977): Preprocessing, Base Classifier, Temporal Estimator.
   - Partition 2 (P2, next 20% ~ 659): Probability calibration ONLY via FrozenEstimator.
   - Partition 3 (P3, final 20% ~ 659): Completely held out for final evaluation.
3. Zero Preprocessing Leakage: ColumnTransformer fitted exclusively on P1.
4. Frozen Base Classifier: No refitting of base classifier during calibration.
5. Strict Point-in-Time Historical Feature calculation.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "ml" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

CATEGORICAL_FEATURES = [
    "crime_category",
    "payment_channel",
    "mule_account_tier",
    "mule_branch_zone",
]

NUMERICAL_FEATURES = [
    "reported_amount",
    "reporting_delay_mins",
    "incident_hour",
    "incident_day_of_week",
]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES


# ==============================================================================
# TEMPORAL WINDOW ESTIMATOR (FITTED EXCLUSIVELY ON P1)
# ==============================================================================
def fit_temporal_window_estimator(df_p1: pd.DataFrame) -> dict:
    """
    Fits conditional intervention delay quantiles:
    Delta_t_remaining = time_to_cashout_mins - reporting_delay_mins
    Conditioned on (crime_category, payment_channel).
    Fitted strictly on Partition 1.
    """
    deltas = df_p1["time_to_cashout_mins"] - df_p1["reporting_delay_mins"]
    global_p25 = float(np.percentile(deltas, 25))
    global_p75 = float(np.percentile(deltas, 75))

    conditional_quantiles = {}
    grouped = df_p1.groupby(["crime_category", "payment_channel"])
    for (cat, chan), group in grouped:
        group_deltas = group["time_to_cashout_mins"] - group["reporting_delay_mins"]
        if len(group_deltas) >= 5:
            p25 = float(np.percentile(group_deltas, 25))
            p75 = float(np.percentile(group_deltas, 75))
        else:
            p25 = global_p25
            p75 = global_p75

        conditional_quantiles[f"{cat}|{chan}"] = (p25, p75)

    return {
        "conditional_quantiles": conditional_quantiles,
        "global_p25": global_p25,
        "global_p75": global_p75,
    }


def predict_temporal_window(complaint_ts_str: str, crime_cat: str, channel: str, temporal_model: dict) -> tuple[datetime, datetime]:
    complaint_dt = datetime.strptime(complaint_ts_str, "%Y-%m-%d %H:%M:%S")
    key = f"{crime_cat}|{channel}"
    p25, p75 = temporal_model["conditional_quantiles"].get(key, (temporal_model["global_p25"], temporal_model["global_p75"]))

    window_start = complaint_dt + timedelta(minutes=p25)
    window_end = complaint_dt + timedelta(minutes=p75)
    return window_start, window_end


# ==============================================================================
# POINT-IN-TIME HISTORICAL ATM CASH-OUT COUNTER
# ==============================================================================
def get_point_in_time_cashout_count(atm_id: str, timestamp_str: str, events_df: pd.DataFrame) -> int:
    """
    Calculates historical_cashout_count(a, t) strictly using events where:
    event.atm_id == a AND event.withdrawal_timestamp < t
    Guarantees point-in-time safety with zero future leakage.
    """
    mask = (events_df["atm_id"] == atm_id) & (events_df["withdrawal_timestamp"] < timestamp_str)
    return int(mask.sum())


# ==============================================================================
# MAIN TRAINING PIPELINE
# ==============================================================================
def run_training_pipeline():
    print("=" * 80)
    print("PHASE 2: ML TRAINING PIPELINE (CHRONOLOGICAL THREE-PARTITION ARCHITECTURE)")
    print("=" * 80)

    # 1. Load Datasets
    print("\n[1/6] Loading source datasets...")
    complaints_path = DATA_DIR / "complaints.csv"
    cashouts_path = DATA_DIR / "cash_out_events.csv"
    atms_path = DATA_DIR / "atm_locations.csv"

    assert complaints_path.exists(), "complaints.csv missing!"
    assert cashouts_path.exists(), "cash_out_events.csv missing!"
    assert atms_path.exists(), "atm_locations.csv missing!"

    df_complaints = pd.read_csv(complaints_path)
    df_cashouts = pd.read_csv(cashouts_path)
    df_atms = pd.read_csv(atms_path)

    print(f"  - Total Complaints: {len(df_complaints):,}")
    print(f"  - Total Cash-Out Events: {len(df_cashouts):,}")
    print(f"  - Registered ATMs: {len(df_atms):,}")

    # 2. Eligible Population (Ground-Truth Cash-Out Complaints)
    print("\n[2/6] Defining spatial training population (complaints with verified cash-out)...")
    merged_df = pd.merge(
        df_complaints,
        df_cashouts[["event_id", "complaint_id", "atm_id", "withdrawal_timestamp", "time_to_cashout_mins", "withdrawal_amount"]],
        on="complaint_id",
        how="inner"
    )

    total_eligible = len(merged_df)
    non_cashout_count = len(df_complaints) - total_eligible
    print(f"  - Verified eligible cash-out population: {total_eligible:,} complaints")
    print(f"  - Excluded non-cashout complaints (funds frozen/diverted): {non_cashout_count:,}")
    assert total_eligible == 3295, f"Expected 3,295 eligible cases, found {total_eligible}"

    # 3. Chronological Sorting Strictly by complaint_timestamp
    print("\n[3/6] Sorting chronologically strictly by complaint_timestamp...")
    merged_df = merged_df.sort_values("complaint_timestamp", ascending=True).reset_index(drop=True)

    # Calculate exact chronological partition boundaries
    n1 = int(0.60 * total_eligible)  # 1977
    n2 = int(0.80 * total_eligible)  # 2636

    p1_df = merged_df.iloc[:n1].copy()
    p2_df = merged_df.iloc[n1:n2].copy()
    p3_df = merged_df.iloc[n2:].copy()

    print(f"  - Partition 1 (Training):    {len(p1_df):,} cases ({p1_df['complaint_timestamp'].min()} -> {p1_df['complaint_timestamp'].max()})")
    print(f"  - Partition 2 (Calibration): {len(p2_df):,} cases ({p2_df['complaint_timestamp'].min()} -> {p2_df['complaint_timestamp'].max()})")
    print(f"  - Partition 3 (Future Test): {len(p3_df):,} cases ({p3_df['complaint_timestamp'].min()} -> {p3_df['complaint_timestamp'].max()})")

    # Chronological integrity assertion
    assert p1_df["complaint_timestamp"].max() <= p2_df["complaint_timestamp"].min(), "P1/P2 timestamp overlap detected!"
    assert p2_df["complaint_timestamp"].max() <= p3_df["complaint_timestamp"].min(), "P2/P3 timestamp overlap detected!"
    print("  [OK] Chronological boundary isolation verified.")

    # Target class distribution diagnostics in P1
    y_p1 = p1_df["atm_id"]
    y_p2 = p2_df["atm_id"]
    y_p3 = p3_df["atm_id"]

    p1_counts = y_p1.value_counts()
    print("\n  ATM Class Distribution in P1 (Training):")
    print(f"    - Unique ATM classes in P1: {len(p1_counts)}")
    print(f"    - Min samples in class: {p1_counts.min()} ({p1_counts.idxmin()})")
    print(f"    - Max samples in class: {p1_counts.max()} ({p1_counts.idxmax()})")
    print(f"    - Imbalance ratio (Max/Min): {p1_counts.max() / p1_counts.min():.2f}")

    # 4. Feature Preprocessing (Fitted ONLY on P1)
    print("\n[4/6] Fitting ColumnTransformer strictly on Partition 1...")
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
            (
                "num",
                StandardScaler(),
                NUMERICAL_FEATURES,
            ),
        ]
    )

    X_p1_raw = p1_df[ALL_FEATURES]
    X_p2_raw = p2_df[ALL_FEATURES]
    X_p3_raw = p3_df[ALL_FEATURES]

    # Preprocessor fitted ONLY on P1
    X_p1 = preprocessor.fit_transform(X_p1_raw)
    # Transform P2 and P3 using P1's fitted parameters
    X_p2 = preprocessor.transform(X_p2_raw)
    X_p3 = preprocessor.transform(X_p3_raw)
    print(f"  [OK] Preprocessor fitted on P1. Feature dimension: {X_p1.shape[1]}")

    # 5. Base Spatial Model Fitting on P1 & Calibration on P2
    print("\n[5/6] Fitting Base Classifier on P1 and Calibrating on P2...")
    base_clf = RandomForestClassifier(
        n_estimators=150,
        class_weight="balanced",
        random_state=RANDOM_SEED,
    )
    base_clf.fit(X_p1, y_p1)
    print("  [OK] Base RandomForestClassifier fitted strictly on P1.")

    # Calibration on P2 using FrozenEstimator (Scikit-Learn 1.9.1 API)
    calibrated_clf = CalibratedClassifierCV(
        estimator=FrozenEstimator(base_clf),
        method="sigmoid",
    )
    calibrated_clf.fit(X_p2, y_p2)
    print("  [OK] Probability calibration layer fitted strictly on P2 via FrozenEstimator.")

    # 6. Fit Temporal Window Estimator on P1
    print("\n[6/6] Fitting Temporal Window Estimator strictly on P1...")
    temporal_estimator = fit_temporal_window_estimator(p1_df)
    print("  [OK] Temporal Window Estimator fitted on P1 conditional delay quantiles.")

    # 7. Serialize Artifacts
    print("\n[7/7] Serializing trained models and preprocessor artifacts...")
    joblib.dump(calibrated_clf, MODELS_DIR / "spatial_atm_classifier.joblib")
    joblib.dump(preprocessor, MODELS_DIR / "feature_preprocessor.joblib")
    joblib.dump(temporal_estimator, MODELS_DIR / "temporal_window_estimator.joblib")

    # Save P3 partition to disk for evaluation step to ensure 100% data consistency
    p3_df.to_csv(MODELS_DIR / "p3_test_partition.csv", index=False)

    metadata = {
        "model_name": "Cybercrime_Cashout_Spatial_Predictor",
        "random_seed": RANDOM_SEED,
        "trained_at": datetime.now().isoformat(),
        "total_eligible_population": total_eligible,
        "partition_sizes": {
            "p1_train": len(p1_df),
            "p2_calibration": len(p2_df),
            "p3_future_test": len(p3_df),
        },
        "chronological_boundaries": {
            "p1_start": p1_df["complaint_timestamp"].min(),
            "p1_end": p1_df["complaint_timestamp"].max(),
            "p2_start": p2_df["complaint_timestamp"].min(),
            "p2_end": p2_df["complaint_timestamp"].max(),
            "p3_start": p3_df["complaint_timestamp"].min(),
            "p3_end": p3_df["complaint_timestamp"].max(),
        },
        "target_classes_count": len(base_clf.classes_),
        "target_classes": base_clf.classes_.tolist(),
        "features": {
            "categorical": CATEGORICAL_FEATURES,
            "numerical": NUMERICAL_FEATURES,
            "transformed_dim": X_p1.shape[1],
        },
        "status": "TRAINED_AND_CALIBRATED",
    }

    with open(MODELS_DIR / "model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print("  [OK] Artifacts saved successfully to:", MODELS_DIR)
    print("    - spatial_atm_classifier.joblib")
    print("    - feature_preprocessor.joblib")
    print("    - temporal_window_estimator.joblib")
    print("    - model_metadata.json")
    print("=" * 80)


if __name__ == "__main__":
    run_training_pipeline()
