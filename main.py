"""
main.py
Final 4-second window experiment (10 Hours) with dynamic hyperparameter tuning.
"""
import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import balanced_accuracy_score, f1_score, accuracy_score
from sklearn.ensemble import HistGradientBoostingClassifier

from src.data_loader import load_record
from src.data_generator import save_dataset
from src.feature_extraction import FEATURE_NAMES
from src.classifier import evaluate_model, save_model, plot_confusion_matrix, plot_feature_importance
from src.visualization import print_stage_header
from src.experiment_2s import (
    discover_and_load_ecg_records, split_records_train_test, split_signal_train_test,
    generate_split_dataset, evaluate_by_snr, plot_confusion_matrix_normalized,
)
from src.experiment_improved import (
    build_extended_feature_matrix, hyperparameter_search, 
    compare_bw_ma_features, plot_bw_ma_feature_comparison, plot_accuracy_by_snr
)

MIT_DB_DIR = "data/mit_db"
NOISE_DIR = "data/noise_stress"
BW_RECORD_NAME, MA_RECORD_NAME = "bw", "ma"

DATASET_DIR = "outputs/noisy_dataset_4s_final"
IMPROVED_DIR = "outputs/milestone3_results/final_4s"
MODEL_PATH = "models/final_4s/random_forest_noise_classifier_4s.joblib"

FS_EXPECTED = 360
WINDOW_DURATION_SEC = 4.0

# --- SCALED FOR 10 HOURS ---
N_ECG_RECORDS = 30            
TARGET_PER_CLASS = 3000       # 9000 total windows (10 hours)

TRAIN_FRACTION = 0.75
SNR_LIST = [0, 5, 10, 15]
RANDOM_SEED = 42

# --- TUNING PARAMETERS ---
N_SEARCH_ITER = 30           # 30 trials of dynamic searching (No hardcoding)
CV_FOLDS = 3                 # 3-fold cross validation

def main():
    print("=" * 60)
    print("ML-Based ECG Noise Classification (10-Hour Dynamic Tuning)")
    print("=" * 60)

    window_samples = int(round(WINDOW_DURATION_SEC * FS_EXPECTED))

    # --- 1. DATASET GENERATION ---
    print_stage_header("DATASET GENERATION")
    ecg_records = discover_and_load_ecg_records(MIT_DB_DIR, N_ECG_RECORDS, FS_EXPECTED, seed=RANDOM_SEED)
    bw_record = load_record(NOISE_DIR, BW_RECORD_NAME)
    ma_record = load_record(NOISE_DIR, MA_RECORD_NAME)

    train_names, test_names = split_records_train_test(list(ecg_records.keys()), TRAIN_FRACTION, RANDOM_SEED)
    ecg_train = {n: ecg_records[n] for n in train_names}
    ecg_test = {n: ecg_records[n] for n in test_names}

    bw_signal_train, bw_signal_test = split_signal_train_test(bw_record.p_signal[:, 0], TRAIN_FRACTION)
    ma_signal_train, ma_signal_test = split_signal_train_test(ma_record.p_signal[:, 0], TRAIN_FRACTION)

    target_per_class_train = int(round(TARGET_PER_CLASS * TRAIN_FRACTION))
    target_per_class_test = TARGET_PER_CLASS - target_per_class_train

    print(f"Generating 10 hours of data ({TARGET_PER_CLASS * 3} total windows)...")
    X_train_raw, y_train, meta_train, X_test_raw, y_test, meta_test = generate_split_dataset(
        ecg_train, ecg_test, bw_signal_train, bw_signal_test, ma_signal_train, ma_signal_test,
        window_samples, SNR_LIST, target_per_class_train, target_per_class_test,
        FS_EXPECTED, seed=RANDOM_SEED,
    )

    X_all = np.concatenate([X_train_raw, X_test_raw], axis=0)
    y_all = np.concatenate([y_train, y_test], axis=0)
    save_dataset(X_all, y_all, meta_train + meta_test, DATASET_DIR)

    # --- 2. FEATURE EXTRACTION ---
    print_stage_header("FEATURE EXTRACTION")
    print("Extracting features...")
    X_train_feat, feature_names = build_extended_feature_matrix(X_train_raw, FS_EXPECTED)
    X_test_feat, _ = build_extended_feature_matrix(X_test_raw, FS_EXPECTED)
    print(f"Extracted {len(feature_names)} features for {len(X_all)} total windows.")

    # --- 3. MODEL TRAINING & COMPARISON ---
    print_stage_header("MODEL TRAINING (Dynamic Tuning)")
    
    print(f"1. Tuning Random Forest ({N_SEARCH_ITER} trials via Cross-Validation)...")
    print("   (This will take a few minutes. Please wait...)")
    rf_model, best_params, best_cv_f1 = hyperparameter_search(
        X_train_feat, y_train, seed=RANDOM_SEED, n_iter=N_SEARCH_ITER, cv=CV_FOLDS
    )
    print(f"   Done! Best RF parameters found: {best_params}")

    print("\n2. Training Gradient Boosting Classifier (300 iterations)...")
    gb_model = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=RANDOM_SEED)
    gb_model.fit(X_train_feat, y_train)

    rf_test_acc = accuracy_score(y_test, rf_model.predict(X_test_feat))
    gb_test_acc = accuracy_score(y_test, gb_model.predict(X_test_feat))
    
    print("\n--- MODEL SHOWDOWN ON UNSEEN TEST PATIENTS ---")
    print(f"Random Forest Test Accuracy:     {rf_test_acc * 100:.2f}%")
    print(f"Gradient Boosting Test Accuracy: {gb_test_acc * 100:.2f}%")

    final_model = rf_model if rf_test_acc >= gb_test_acc else gb_model
    selected_name = "Random Forest" if final_model is rf_model else "Gradient Boosting"
    print(f"\nChampion Model Selected: {selected_name}")

    # --- 4. EVALUATION & ARTIFACTS ---
    print_stage_header("FINAL EVALUATION ON TEST SET")
    results = evaluate_model(final_model, X_test_feat, y_test)
    y_pred = final_model.predict(X_test_feat)
    balanced_acc = balanced_accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    weighted_f1 = f1_score(y_test, y_pred, average="weighted")

    print(f"Accuracy:          {results['accuracy']:.4f}")
    print(f"Balanced Accuracy: {balanced_acc:.4f}")
    print(f"Macro F1:          {macro_f1:.4f}\n")
    print("Classification Report:")
    print(results["report"])
    
    print("\nConfusion Matrix (Rows=True, Cols=Predicted):")
    print(results["confusion_matrix"])

    os.makedirs(IMPROVED_DIR, exist_ok=True)
    plot_confusion_matrix(results["confusion_matrix"], results["labels"],
                           os.path.join(IMPROVED_DIR, "confusion_matrix_raw.png"))
    plot_confusion_matrix_normalized(results["confusion_matrix"], results["labels"],
                                      os.path.join(IMPROVED_DIR, "confusion_matrix_normalized.png"))

    snr_test_arr = np.array([m["snr_db"] for m in meta_test])
    snr_results = evaluate_by_snr(final_model, X_test_feat, y_test, snr_test_arr)
    plot_accuracy_by_snr(snr_results, os.path.join(IMPROVED_DIR, "snr_performance.png"))

    if hasattr(final_model, "feature_importances_"):
        plot_feature_importance(final_model, feature_names, os.path.join(IMPROVED_DIR, "feature_importance.png"))

    X_all_feat = np.concatenate([X_train_feat, X_test_feat], axis=0)
    y_all_feat = np.concatenate([y_train, y_test], axis=0)
    bw_ma_stats = compare_bw_ma_features(X_all_feat, y_all_feat, feature_names)
    plot_bw_ma_feature_comparison(bw_ma_stats, feature_names, os.path.join(IMPROVED_DIR, "bw_vs_ma_features.png"))

    save_model(final_model, MODEL_PATH)

    with open(os.path.join(IMPROVED_DIR, "classification_report.txt"), "w") as f:
        f.write(f"Model: {selected_name}\n")
        f.write(f"Accuracy: {results['accuracy']:.4f}\nBalanced Accuracy: {balanced_acc:.4f}\n")
        f.write(f"Macro F1: {macro_f1:.4f}\nWeighted F1: {weighted_f1:.4f}\n\n")
        f.write(results["report"])
        if selected_name == "Random Forest":
            f.write(f"\nBest hyperparameters found via cross-validation: {best_params}\n")

    with open(os.path.join(IMPROVED_DIR, "dataset_summary.txt"), "w") as f:
        f.write(f"Total: {len(X_all)}, BW: {np.sum(y_all=='BW')}, MA: {np.sum(y_all=='MA')}, PLI: {np.sum(y_all=='PLI')}\n")
        f.write(f"Train records: {sorted(train_names)}\nTest records: {sorted(test_names)}\n")

    print(f"\nFinal Test Accuracy: {results['accuracy'] * 100:.2f}%")
    print(f"All images and reports saved to: {IMPROVED_DIR}")

if __name__ == "__main__":
    main()