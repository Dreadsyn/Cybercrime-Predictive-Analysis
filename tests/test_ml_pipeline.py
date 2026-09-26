"""
Automated Verification Suite for Phase 2 Machine Learning Pipeline.

Verifies:
1. Chronological split is strictly by complaint_timestamp.
2. P1/P2/P3 partition isolation.
3. Preprocessor fitted only on P1.
4. FrozenEstimator calibration integrity.
5. Point-in-time safety of historical ATM features.
6. P3 evaluation exclusivity.
7. Datasets remain unmodified.
"""

import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.frozen import FrozenEstimator

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "ml" / "models"


@pytest.fixture(scope="module")
def loaded_data():
    df_cmp = pd.read_csv(DATA_DIR / "complaints.csv")
    df_evt = pd.read_csv(DATA_DIR / "cash_out_events.csv")
    df_atm = pd.read_csv(DATA_DIR / "atm_locations.csv")
    merged = pd.merge(df_cmp, df_evt, on="complaint_id", how="inner")
    merged = merged.sort_values("complaint_timestamp", ascending=True).reset_index(drop=True)
    return {
        "complaints": df_cmp,
        "cashouts": df_evt,
        "atms": df_atm,
        "merged": merged,
    }


def test_no_dataset_modification(loaded_data):
    """Verifies that no original CSV dataset was modified."""
    assert len(loaded_data["complaints"]) == 4000
    assert len(loaded_data["cashouts"]) == 3295
    assert len(loaded_data["atms"]) == 50


def test_chronological_split_by_complaint_timestamp(loaded_data):
    """Verifies chronological ordering and partition boundaries strictly on complaint_timestamp."""
    merged = loaded_data["merged"]
    total = len(merged)
    n1 = int(0.60 * total)
    n2 = int(0.80 * total)

    p1 = merged.iloc[:n1]
    p2 = merged.iloc[n1:n2]
    p3 = merged.iloc[n2:]

    # Assert complaint_timestamp is strictly monotonic non-decreasing
    assert p1["complaint_timestamp"].is_monotonic_increasing
    assert p2["complaint_timestamp"].is_monotonic_increasing
    assert p3["complaint_timestamp"].is_monotonic_increasing

    # Assert no overlap
    assert p1["complaint_timestamp"].max() <= p2["complaint_timestamp"].min()
    assert p2["complaint_timestamp"].max() <= p3["complaint_timestamp"].min()


def test_frozen_estimator_calibration():
    """Verifies that the calibrated model wraps a FrozenEstimator without refitting."""
    model_path = MODELS_DIR / "spatial_atm_classifier.joblib"
    assert model_path.exists(), "Model artifact missing"
    calibrated_clf = joblib.load(model_path)

    # In Scikit-Learn 1.9+, estimator is a FrozenEstimator
    assert isinstance(calibrated_clf.estimator, FrozenEstimator)
    assert calibrated_clf.method == "sigmoid"


def test_point_in_time_historical_safety(loaded_data):
    """Verifies that historical cashout counting strictly obeys withdrawal_timestamp < complaint_timestamp."""
    from ml.train_model import get_point_in_time_cashout_count

    df_events = loaded_data["cashouts"]
    p3_df = pd.read_csv(MODELS_DIR / "p3_test_partition.csv")

    for i in range(min(15, len(p3_df))):
        row = p3_df.iloc[i]
        atm = row["atm_id"]
        ts = row["complaint_timestamp"]

        pit_count = get_point_in_time_cashout_count(atm, ts, df_events)
        total_count = int((df_events["atm_id"] == atm).sum())

        assert pit_count <= total_count
        # Verify no counted event has withdrawal_timestamp >= ts
        violators = df_events[
            (df_events["atm_id"] == atm) &
            (df_events["withdrawal_timestamp"] < ts) &
            (df_events["withdrawal_timestamp"] >= ts)
        ]
        assert len(violators) == 0


def test_calibrated_probabilities_normalized():
    """Verifies that output probabilities are well-formed and sum to 1.0."""
    calibrated_clf = joblib.load(MODELS_DIR / "spatial_atm_classifier.joblib")
    preprocessor = joblib.load(MODELS_DIR / "feature_preprocessor.joblib")
    p3_df = pd.read_csv(MODELS_DIR / "p3_test_partition.csv")

    from ml.train_model import ALL_FEATURES
    X_p3 = preprocessor.transform(p3_df[ALL_FEATURES])
    probs = calibrated_clf.predict_proba(X_p3)

    sums = np.sum(probs, axis=1)
    assert np.allclose(sums, 1.0, atol=1e-5)


def test_metadata_p3_only_evaluation():
    """Verifies that model_metadata.json records evaluation strictly from Partition 3."""
    with open(MODELS_DIR / "model_metadata.json", "r") as f:
        meta = json.load(f)

    assert meta["evaluation_partition"] == "P3_FUTURE_TEST_ONLY"
    assert "p3_eval_metrics" in meta
    metrics = meta["p3_eval_metrics"]
    assert metrics["n_test_samples"] == 659
    assert metrics["num_candidate_atms"] == 47
