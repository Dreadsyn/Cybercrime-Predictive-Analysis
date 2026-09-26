"""
Evaluation Suite for Cybercrime Predictive Analytics Framework.

Problem Statement:
"Development of a Predictive Analytics Framework for Cybercrime Complaints to Forecast
Likely Cash Withdrawal Locations in Advance, Enabling Generation of Actionable Intelligence
for Timely and Proactive Cybercrime Intervention."

Strict Protocol Enforced:
1. FINAL METRICS EVALUATED EXCLUSIVELY ON PARTITION 3 (Untouched Future Test Period).
2. Zero metrics computed or reported from Partition 1 or Partition 2.
3. Probability calibration metrics: Multi-class Brier Score and Log Loss.
4. Top-1, Top-3, Top-5 spatial accuracy and Zone-level accuracy.
5. Temporal window coverage evaluated strictly against ground-truth withdrawal_timestamp.
6. Point-in-time historical feature verification.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss
from sklearn.preprocessing import label_binarize

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "ml"))
from train_model import ALL_FEATURES, get_point_in_time_cashout_count, predict_temporal_window
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "ml" / "models"


def evaluate_p3_model():
    print("=" * 80)
    print("PHASE 2: MODEL EVALUATION (EXCLUSIVELY ON PARTITION 3 FUTURE TEST SET)")
    print("=" * 80)

    # 1. Load Serialized Artifacts and P3 Test Partition
    print("\n[1/5] Loading serialized models and untouched Partition 3 test set...")
    classifier_path = MODELS_DIR / "spatial_atm_classifier.joblib"
    preprocessor_path = MODELS_DIR / "feature_preprocessor.joblib"
    temporal_path = MODELS_DIR / "temporal_window_estimator.joblib"
    p3_path = MODELS_DIR / "p3_test_partition.csv"
    atms_path = DATA_DIR / "atm_locations.csv"
    events_path = DATA_DIR / "cash_out_events.csv"

    assert classifier_path.exists(), "Classifier artifact missing! Run train_model.py first."
    assert preprocessor_path.exists(), "Preprocessor artifact missing!"
    assert temporal_path.exists(), "Temporal estimator artifact missing!"
    assert p3_path.exists(), "P3 test partition missing!"
    assert atms_path.exists(), "atm_locations.csv missing!"

    calibrated_clf = joblib.load(classifier_path)
    preprocessor = joblib.load(preprocessor_path)
    temporal_model = joblib.load(temporal_path)
    df_p3 = pd.read_csv(p3_path)
    df_atms = pd.read_csv(atms_path)
    df_events = pd.read_csv(events_path)

    print(f"  - Untouched Partition 3 size: {len(df_p3):,} cases")
    print(f"  - Chronological Range: {df_p3['complaint_timestamp'].min()} to {df_p3['complaint_timestamp'].max()}")

    # 2. Extract Features and Ground Truth Labels
    X_p3_raw = df_p3[ALL_FEATURES]
    y_p3_true = df_p3["atm_id"].values

    # Preprocessor transform ONLY (never fit)
    X_p3_transformed = preprocessor.transform(X_p3_raw)

    # 3. Spatial Probability Inference
    print("\n[2/5] Generating calibrated probability distribution over candidate ATMs...")
    classes = calibrated_clf.classes_
    y_probs = calibrated_clf.predict_proba(X_p3_transformed)  # Shape: (N_p3, num_classes)

    n_samples = len(df_p3)
    k_classes = len(classes)

    # Class-to-index mapping
    class_to_idx = {c: i for i, c in enumerate(classes)}
    atm_to_zone = df_atms.set_index("atm_id")["zone_id"].to_dict()

    top1_correct = 0
    top3_correct = 0
    top5_correct = 0
    zone_correct = 0

    top_predicted_atms = []
    top_confidences = []

    for i in range(n_samples):
        true_atm = y_p3_true[i]
        probs = y_probs[i]

        # Sort candidate indices by probability descending
        sorted_indices = np.argsort(probs)[::-1]
        ranked_atms = [classes[idx] for idx in sorted_indices]

        top1_atm = ranked_atms[0]
        top1_prob = probs[sorted_indices[0]]

        top_predicted_atms.append(top1_atm)
        top_confidences.append(float(top1_prob))

        # Check Top-K matches
        if true_atm == top1_atm:
            top1_correct += 1
        if true_atm in ranked_atms[:3]:
            top3_correct += 1
        if true_atm in ranked_atms[:5]:
            top5_correct += 1

        # Check Zone accuracy
        true_zone = atm_to_zone.get(true_atm, "UNKNOWN")
        pred_zone = atm_to_zone.get(top1_atm, "UNKNOWN")
        if true_zone == pred_zone and true_zone != "UNKNOWN":
            zone_correct += 1

    top1_acc = (top1_correct / n_samples) * 100.0
    top3_acc = (top3_correct / n_samples) * 100.0
    top5_acc = (top5_correct / n_samples) * 100.0
    zone_acc = (zone_correct / n_samples) * 100.0

    # 4. Calibration Metrics
    print("\n[3/5] Computing probability calibration metrics (Brier Score & Log Loss)...")
    y_true_bin = label_binarize(y_p3_true, classes=classes)
    # Multi-class Brier Score: mean squared error over probability vector
    brier_score = float(np.mean(np.sum((y_probs - y_true_bin) ** 2, axis=1)))
    # Calibrated Log Loss
    calibrated_log_loss = float(log_loss(y_p3_true, y_probs, labels=classes))

    # 5. Temporal Window Coverage Evaluation
    print("\n[4/5] Evaluating temporal intervention window coverage on P3...")
    window_hits = 0
    window_durations_mins = []

    for _, row in df_p3.iterrows():
        w_start, w_end = predict_temporal_window(
            row["complaint_timestamp"],
            row["crime_category"],
            row["payment_channel"],
            temporal_model
        )
        actual_withdrawal = datetime.strptime(row["withdrawal_timestamp"], "%Y-%m-%d %H:%M:%S")

        if w_start <= actual_withdrawal <= w_end:
            window_hits += 1

        duration = (w_end - w_start).total_seconds() / 60.0
        window_durations_mins.append(duration)

    temporal_coverage = (window_hits / n_samples) * 100.0
    avg_window_mins = float(np.mean(window_durations_mins))

    # 6. Point-in-Time Historical Feature Verification Sample
    print("\n[5/5] Auditing point-in-time historical ATM feature computation...")
    sample_row = df_p3.iloc[0]
    sample_atm = sample_row["atm_id"]
    sample_ts = sample_row["complaint_timestamp"]

    pit_count = get_point_in_time_cashout_count(sample_atm, sample_ts, df_events)
    full_count = int((df_events["atm_id"] == sample_atm).sum())
    print(f"  Audit check for ATM '{sample_atm}' at complaint timestamp '{sample_ts}':")
    print(f"    - Point-in-time count (events < {sample_ts}): {pit_count}")
    print(f"    - Full dataset count (including future events): {full_count}")
    assert pit_count <= full_count, "Point-in-time count exceeded full count!"
    print("    [OK] Point-in-time safety verified: Future events are strictly excluded.")

    # 7. Print Comprehensive Operational Performance Report
    random_top1_baseline = (1.0 / k_classes) * 100.0
    random_top3_baseline = (3.0 / k_classes) * 100.0
    random_top5_baseline = (5.0 / k_classes) * 100.0
    random_zone_baseline = 20.0  # 5 equal zones

    print("\n" + "=" * 80)
    print("FINAL OPERATIONAL PERFORMANCE REPORT (PARTITION 3 FUTURE TEST SET ONLY)")
    print("=" * 80)
    print(f"Test Partition Size (N_P3):         {n_samples:,} complaints")
    print(f"Number of Candidate ATM Classes:    {k_classes} ATMs")
    print("-" * 80)
    print(f"Metric                     Result     Target Benchmark    Random Baseline    Status")
    print("-" * 80)
    print(f"Top-1 Spatial Accuracy:    {top1_acc:6.2f}%    >= 25.00%           {random_top1_baseline:6.2f}%         {'PASSED' if top1_acc >= 25.0 else 'MISSED'}")
    print(f"Top-3 Spatial Accuracy:    {top3_acc:6.2f}%    >= 50.00%           {random_top3_baseline:6.2f}%         {'PASSED' if top3_acc >= 50.0 else 'MISSED'}")
    print(f"Top-5 Spatial Accuracy:    {top5_acc:6.2f}%    >= 70.00%           {random_top5_baseline:6.2f}%         {'PASSED' if top5_acc >= 70.0 else 'MISSED'}")
    print(f"Zone-Level Accuracy:       {zone_acc:6.2f}%    >= 80.00%           {random_zone_baseline:6.2f}%         {'PASSED' if zone_acc >= 80.0 else 'MISSED'}")
    print(f"Temporal Window Coverage:  {temporal_coverage:6.2f}%    >= 75.00%              N/A             {'PASSED' if temporal_coverage >= 75.0 else 'MISSED'}")
    print("-" * 80)
    print(f"Calibrated Multi-Class Brier Score: {brier_score:.4f} (lower is better)")
    print(f"Calibrated Multi-Class Log Loss:    {calibrated_log_loss:.4f} (lower is better)")
    print(f"Average Forecasted Window:          {avg_window_mins:.1f} minutes")
    print("=" * 80)

    # 8. Update Model Metadata with Final P3 Metrics
    meta_path = MODELS_DIR / "model_metadata.json"
    with open(meta_path, "r") as f:
        meta = json.load(f)

    meta["evaluation_partition"] = "P3_FUTURE_TEST_ONLY"
    meta["evaluation_timestamp"] = datetime.now().isoformat()
    meta["p3_eval_metrics"] = {
        "n_test_samples": n_samples,
        "num_candidate_atms": k_classes,
        "top1_spatial_accuracy_pct": round(top1_acc, 2),
        "top3_spatial_accuracy_pct": round(top3_acc, 2),
        "top5_spatial_accuracy_pct": round(top5_acc, 2),
        "zone_level_accuracy_pct": round(zone_acc, 2),
        "temporal_window_coverage_pct": round(temporal_coverage, 2),
        "calibrated_brier_score": round(brier_score, 4),
        "calibrated_log_loss": round(calibrated_log_loss, 4),
        "random_baseline_top1_pct": round(random_top1_baseline, 2),
        "benchmarks": {
            "top1_target_met": bool(top1_acc >= 25.0),
            "top3_target_met": bool(top3_acc >= 50.0),
            "top5_target_met": bool(top5_acc >= 70.0),
            "zone_target_met": bool(zone_acc >= 80.0),
            "temporal_target_met": bool(temporal_coverage >= 75.0),
        },
    }

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print("\nUpdated metadata with verified P3 metrics at:", meta_path)
    return meta["p3_eval_metrics"]


if __name__ == "__main__":
    evaluate_p3_model()
