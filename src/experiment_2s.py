"""
experiment_2s.py

Improved experiment: multi-record, smaller-window (2s) dataset generation
with a RECORD-LEVEL train/test split, to avoid leaking near-identical
adjacent ECG windows (or noise segments) between train and test.

This module does NOT change the six existing features, the three noise
classes, or the Random Forest algorithm. It only changes how much data
is used and how it is split, building on top of the existing, unchanged
data_loader.py / data_generator.py functions.
"""

import os

import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, classification_report

from src.data_loader import find_records, load_record
from src.data_generator import create_pli, add_noise_at_snr


def discover_and_load_ecg_records(mit_db_dir, n_records, expected_fs, seed=42):
    """
    Discover every valid record in mit_db_dir (via the existing
    find_records()), then randomly select (fixed seed) up to n_records
    of them that actually load and match expected_fs.

    Returns dict {record_name: wfdb.Record}.
    """
    all_names = find_records(mit_db_dir)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(all_names))

    selected = {}
    for idx in order:
        name = all_names[idx]
        if len(selected) >= n_records:
            break
        try:
            record = load_record(mit_db_dir, name)
        except RuntimeError as e:
            print(f"[WARNING] Skipping record '{name}': {e}")
            continue
        if record.fs != expected_fs:
            print(f"[WARNING] Skipping record '{name}': fs={record.fs} Hz (expected {expected_fs} Hz)")
            continue
        selected[name] = record

    if not selected:
        raise RuntimeError(
            f"No usable ECG records found in '{mit_db_dir}' with fs={expected_fs} Hz."
        )
    return selected


def split_records_train_test(record_names, train_fraction=0.8, seed=42):
    """
    Randomly (fixed seed) split record names into train/test groups at
    the RECORD level, so no record's windows appear in both groups.
    """
    rng = np.random.default_rng(seed)
    names = list(record_names)
    rng.shuffle(names)
    n_train = int(round(len(names) * train_fraction))
    n_train = max(1, min(n_train, len(names) - 1)) if len(names) > 1 else len(names)
    return names[:n_train], names[n_train:]


def split_signal_train_test(signal, train_fraction=0.8):
    """
    Temporally split one long noise recording into a train segment
    (first train_fraction of samples) and a test segment (remaining
    samples), so no overlapping noise segment can appear in both sets.
    """
    split_point = int(len(signal) * train_fraction)
    return signal[:split_point], signal[split_point:]


def _generate_windows_for_split(ecg_records, bw_signal, ma_signal, window_samples,
                                 snr_list, target_per_class, fs, rng, split_name, id_offset=0):
    X, y, metadata = [], [], []
    record_names = list(ecg_records.keys())
    sample_id = id_offset
    noise_types = ["BW", "PLI", "MA"]
    per_snr_target = max(1, round(target_per_class / len(snr_list)))

    for noise_type in noise_types:
        for snr_db in snr_list:
            generated, attempts = 0, 0
            max_attempts = per_snr_target * 40
            while generated < per_snr_target and attempts < max_attempts:
                attempts += 1
                record_name = record_names[rng.integers(0, len(record_names))]
                ecg_signal = ecg_records[record_name].p_signal[:, 0]  # channel 0, consistently

                if len(ecg_signal) <= window_samples:
                    continue
                ecg_start = int(rng.integers(0, len(ecg_signal) - window_samples))
                clean_window = ecg_signal[ecg_start: ecg_start + window_samples]

                noise_start = None
                try:
                    if noise_type == "BW":
                        if len(bw_signal) <= window_samples:
                            continue
                        noise_start = int(rng.integers(0, len(bw_signal) - window_samples))
                        noise_window = bw_signal[noise_start: noise_start + window_samples]
                    elif noise_type == "MA":
                        if len(ma_signal) <= window_samples:
                            continue
                        noise_start = int(rng.integers(0, len(ma_signal) - window_samples))
                        noise_window = ma_signal[noise_start: noise_start + window_samples]
                    else:
                        _, noise_window = create_pli(fs, window_samples / fs)

                    noisy_window = add_noise_at_snr(clean_window, noise_window, snr_db)
                except ValueError:
                    continue

                X.append(noisy_window)
                y.append(noise_type)
                metadata.append({
                    "sample_id": sample_id, "split": split_name, "noise_type": noise_type,
                    "snr_db": snr_db, "ecg_record": record_name,
                    "ecg_start_sample": ecg_start, "noise_start_sample": noise_start,
                    "fs": fs, "window_samples": window_samples,
                })
                sample_id += 1
                generated += 1

            if generated < per_snr_target:
                print(f"[WARNING] {split_name}: only generated {generated}/{per_snr_target} "
                      f"for noise_type={noise_type}, snr_db={snr_db}")

    return np.array(X), np.array(y), metadata, sample_id


def generate_split_dataset(ecg_records_train, ecg_records_test, bw_signal_train, bw_signal_test,
                            ma_signal_train, ma_signal_test, window_samples, snr_list,
                            target_per_class_train, target_per_class_test, fs, seed=42):
    """
    Build balanced TRAIN and TEST sets independently from disjoint ECG
    records and disjoint noise segments (no leakage between the two).
    """
    rng = np.random.default_rng(seed)
    X_train, y_train, meta_train, next_id = _generate_windows_for_split(
        ecg_records_train, bw_signal_train, ma_signal_train,
        window_samples, snr_list, target_per_class_train, fs, rng, "train", 0)
    X_test, y_test, meta_test, _ = _generate_windows_for_split(
        ecg_records_test, bw_signal_test, ma_signal_test,
        window_samples, snr_list, target_per_class_test, fs, rng, "test", next_id)
    return X_train, y_train, meta_train, X_test, y_test, meta_test


def evaluate_by_snr(model, X_test_features, y_test, snr_test):
    """
    Evaluate an already-trained model separately for each SNR value
    present in snr_test (no retraining). Returns
    {snr_db: {"accuracy", "report", "n_samples"}}.
    """
    results = {}
    snr_test = np.asarray(snr_test, dtype=float)
    for snr_db in sorted(np.unique(snr_test)):
        mask = snr_test == snr_db
        y_sub = y_test[mask]
        y_pred_sub = model.predict(X_test_features[mask])
        results[float(snr_db)] = {
            "accuracy": accuracy_score(y_sub, y_pred_sub),
            "report": classification_report(y_sub, y_pred_sub, zero_division=0),
            "n_samples": int(mask.sum()),
        }
    return results


def plot_confusion_matrix_normalized(cm_counts, labels, output_path=None):
    """
    Row-normalize a raw-count confusion matrix into percentages and plot
    it as an annotated heatmap.
    """
    cm_counts = np.asarray(cm_counts, dtype=float)
    row_sums = cm_counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    cm_norm = (cm_counts / row_sums) * 100.0

    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm_norm, cmap="Blues", vmin=0, vmax=100)
    ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels); ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted label"); ax.set_ylabel("True label")
    ax.set_title("Confusion Matrix (Normalized %)")

    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{cm_norm[i, j]:.1f}%", ha="center", va="center",
                     color="white" if cm_norm[i, j] > 50 else "black")

    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    if output_path:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fig.savefig(output_path)
    return fig
