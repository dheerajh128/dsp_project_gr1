
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import wfdb

from scipy.stats import kurtosis
from scipy.signal import welch

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
)

# ============================================================
# 1. CONFIGURATION
# ============================================================

PROJECT_DIR = Path(r"D:\dsp_project")

RECORDS = {
    "100": {
        "path": PROJECT_DIR / "data" / "mit_db" / "100",
        "label": "Clean",
    },
    "118e_6": {
        "path": PROJECT_DIR / "data" / "noise_stress" / "118e_6",
        "label": "Noisy",
    },
}

FS_EXPECTED = 360
WINDOW_SECONDS = 4
WINDOW_SIZE = FS_EXPECTED * WINDOW_SECONDS

OUTPUT_DIR = PROJECT_DIR / "random_forest_figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_NAMES = [
    "RMS",
    "Variance",
    "Kurtosis",
    "Low-frequency power",
    "50-Hz power",
    "High-frequency power",
]

RANDOM_STATE = 42


# ============================================================
# 2. LOAD ECG RECORD
# ============================================================

def load_ecg(record_path):
    """Load one ECG record using its WFDB .hea and .dat files."""

    record_path = Path(record_path)

    header_path = record_path.with_suffix(".hea")
    data_path = record_path.with_suffix(".dat")

    print(f"\nLoading: {record_path}")
    print(f"Header exists: {header_path.exists()}")
    print(f"Data exists: {data_path.exists()}")

    if not header_path.exists():
        raise FileNotFoundError(f"Missing header: {header_path}")

    if not data_path.exists():
        raise FileNotFoundError(f"Missing data: {data_path}")

    record = wfdb.rdrecord(str(record_path))

    if record.p_signal is None:
        raise ValueError(
            f"No physical signal found in {record_path}"
        )

    # Use the first ECG channel.
    signal = record.p_signal[:, 0].astype(float)
    fs = int(round(record.fs))

    if fs != FS_EXPECTED:
        raise ValueError(
            f"Expected {FS_EXPECTED} Hz, but {record_path.name} "
            f"has sampling frequency {fs} Hz."
        )

    if not np.all(np.isfinite(signal)):
        raise ValueError(
            f"Signal {record_path.name} contains NaN or infinite values."
        )

    print(f"Sampling frequency: {fs} Hz")
    print(f"Number of samples: {len(signal)}")
    print(f"Duration: {len(signal) / fs:.2f} seconds")
    print(f"Channels: {record.sig_name}")

    return signal, fs


# ============================================================
# 3. PLOT ECG WAVEFORMS
# ============================================================

def save_signal_plot(signal, title, filename, seconds=10):
    """Save a waveform plot from the actual recording."""

    n_samples = min(len(signal), int(seconds * FS_EXPECTED))
    time = np.arange(n_samples) / FS_EXPECTED

    plt.figure(figsize=(13, 4))
    plt.plot(time, signal[:n_samples], linewidth=0.8)
    plt.title(title)
    plt.xlabel("Time (seconds)")
    plt.ylabel("Amplitude (mV)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=200)
    plt.close()


def save_comparison_plot(clean_window, noisy_window):
    """Compare one clean and one noisy window."""

    time = np.arange(WINDOW_SIZE) / FS_EXPECTED

    fig, axes = plt.subplots(2, 1, figsize=(13, 7))

    axes[0].plot(time, clean_window, linewidth=0.8)
    axes[0].set_title("Clean ECG — 4-second window")
    axes[0].set_ylabel("Amplitude (mV)")
    axes[0].set_xlabel("Time (seconds)")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(time, noisy_window, linewidth=0.8)
    axes[1].set_title("Noisy ECG — 4-second window")
    axes[1].set_ylabel("Amplitude (mV)")
    axes[1].set_xlabel("Time (seconds)")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "clean_vs_noisy.png", dpi=200)
    plt.close()


# ============================================================
# 4. DIVIDE RECORDING INTO FOUR-SECOND WINDOWS
# ============================================================

def make_windows(signal, label, record_name):
    windows = []

    for start in range(
        0, len(signal) - WINDOW_SIZE + 1, WINDOW_SIZE
    ):
        window = signal[start:start + WINDOW_SIZE]

        if len(window) != WINDOW_SIZE:
            continue

        windows.append({
            "signal": window.copy(),
            "label": label,
            "record": record_name,
            "start_sample": start,
            "start_time": start / FS_EXPECTED,
        })

    return windows


# ============================================================
# 5. EXTRACT SIX HANDCRAFTED FEATURES
# ============================================================

def extract_features(signal):
    """
    Extract:
    1. RMS
    2. Variance
    3. Kurtosis
    4. Low-frequency power
    5. Power around 50 Hz
    6. High-frequency power
    """

    x = np.asarray(signal, dtype=float)

    # Remove the DC component for feature calculation.
    x = x - np.mean(x)

    rms = np.sqrt(np.mean(x ** 2))
    variance = np.var(x)

    kurt = kurtosis(
        x,
        fisher=True,
        bias=False,
    )

    frequencies, power = welch(
        x,
        fs=FS_EXPECTED,
        nperseg=min(1024, len(x)),
    )

    def calculate_band_power(low, high):
        mask = (
            (frequencies >= low)
            & (frequencies < high)
        )

        if np.count_nonzero(mask) < 2:
            return 0.0

        return float(
            np.trapezoid(
                power[mask],
                frequencies[mask],
            )
        )

    low_frequency_power = calculate_band_power(0.1, 5.0)
    power_50_hz = calculate_band_power(48.0, 52.0)
    high_frequency_power = calculate_band_power(20.0, 100.0)

    return [
        float(rms),
        float(variance),
        float(kurt),
        low_frequency_power,
        power_50_hz,
        high_frequency_power,
    ]


# ============================================================
# 6. VISUALIZE FEATURES
# ============================================================

def save_feature_plots(X, y):
    # Plot features from the first actual window.
    plt.figure(figsize=(12, 5))
    plt.bar(FEATURE_NAMES, X[0])
    plt.title("Six Features Extracted from One ECG Window")
    plt.ylabel("Feature value")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / "example_feature_vector.png",
        dpi=200,
    )
    plt.close()

    # Plot feature distributions for each label.
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))

    for index, ax in enumerate(axes.flat):
        for label in np.unique(y):
            values = X[y == label, index]

            ax.hist(
                values,
                bins=25,
                alpha=0.6,
                label=label,
            )

        ax.set_title(FEATURE_NAMES[index])
        ax.set_xlabel("Feature value")
        ax.set_ylabel("Window count")
        ax.legend()

    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / "feature_distributions.png",
        dpi=200,
    )
    plt.close()


# ============================================================
# 7. TRAIN AND EVALUATE RANDOM FOREST
# ============================================================

def train_random_forest(X, y):
    unique_labels, counts = np.unique(y, return_counts=True)

    if len(unique_labels) < 2:
        print("At least two classes are required.")
        return

    if np.min(counts) < 2:
        print("Each class needs at least two windows.")
        return

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.30,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=RANDOM_STATE,
        class_weight="balanced",
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)

    print("\n" + "=" * 60)
    print("EXPLORATORY RANDOM FOREST RESULTS")
    print("=" * 60)
    print(f"Training windows: {len(X_train)}")
    print(f"Testing windows: {len(X_test)}")
    print(f"Feature matrix shape: {X.shape}")
    print(f"Accuracy: {accuracy:.4f} ({accuracy * 100:.2f}%)")

    report = classification_report(
        y_test,
        predictions,
        zero_division=0,
    )

    print("\nClassification report:")
    print(report)

    # Save report.
    with open(
        OUTPUT_DIR / "classification_report.txt",
        "w",
        encoding="utf-8",
    ) as file:
        file.write("EXPLORATORY RANDOM FOREST RESULTS\n")
        file.write(f"Accuracy: {accuracy:.4f}\n\n")
        file.write(report)

    # Save predictions.
    pd.DataFrame({
        "actual": y_test,
        "predicted": predictions,
    }).to_csv(
        OUTPUT_DIR / "predictions.csv",
        index=False,
    )

    # Confusion matrix.
    labels = model.classes_
    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=labels,
    )

    display = ConfusionMatrixDisplay(
        confusion_matrix=matrix,
        display_labels=labels,
    )

    display.plot(cmap="Blues", values_format="d")
    plt.title("Random Forest — Exploratory Confusion Matrix")
    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / "confusion_matrix.png",
        dpi=200,
    )
    plt.close()

    # Feature importance.
    importance = model.feature_importances_
    order = np.argsort(importance)

    plt.figure(figsize=(10, 5))
    plt.barh(
        np.array(FEATURE_NAMES)[order],
        importance[order],
    )
    plt.xlabel("Feature importance")
    plt.title("Random Forest Feature Importance")
    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / "feature_importance.png",
        dpi=200,
    )
    plt.close()

    return model


# ============================================================
# 8. MAIN PIPELINE
# ============================================================

def main():
    all_windows = []
    example_windows = {}

    print("=" * 60)
    print("ECG RANDOM FOREST VISUALIZATION PIPELINE")
    print("=" * 60)

    for record_name, info in RECORDS.items():
        signal, fs = load_ecg(info["path"])
        label = info["label"]

        # Raw ECG waveform.
        save_signal_plot(
            signal,
            f"{label} ECG — record {record_name}",
            f"{record_name}_raw_ecg.png",
        )

        # Extract windows.
        windows = make_windows(
            signal,
            label,
            record_name,
        )

        if windows:
            example_windows[label] = windows[0]["signal"]

            # Save one four-second window.
            save_signal_plot(
                windows[0]["signal"],
                f"{label} ECG — first 4-second window",
                f"{record_name}_4_second_window.png",
                seconds=WINDOW_SECONDS,
            )

        all_windows.extend(windows)

        print(
            f"Record {record_name}: "
            f"{len(windows)} windows extracted"
        )

    if not all_windows:
        raise RuntimeError(
            "No windows extracted. Check the ECG files and sampling rate."
        )

    # Save clean-vs-noisy comparison.
    if "Clean" in example_windows and "Noisy" in example_windows:
        save_comparison_plot(
            example_windows["Clean"],
            example_windows["Noisy"],
        )

    # Plot the windowing concept.
    plt.figure(figsize=(12, 4))
    t = np.arange(WINDOW_SIZE) / FS_EXPECTED
    plt.plot(t, example_windows["Clean"], linewidth=0.8)
    plt.title(
        f"Windowing: {WINDOW_SECONDS} s × "
        f"{FS_EXPECTED} Hz = {WINDOW_SIZE} samples"
    )
    plt.xlabel("Time (seconds)")
    plt.ylabel("Amplitude (mV)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(
        OUTPUT_DIR / "windowing_example.png",
        dpi=200,
    )
    plt.close()

    # Extract feature matrix.
    X = np.array(
        [
            extract_features(window["signal"])
            for window in all_windows
        ],
        dtype=float,
    )

    y = np.array([
        window["label"]
        for window in all_windows
    ])

    print(f"\nTotal windows: {len(all_windows)}")
    print(f"Feature matrix shape: {X.shape}")
    print(f"Labels: {np.unique(y)}")

    # Save feature data.
    feature_table = pd.DataFrame(
        X,
        columns=FEATURE_NAMES,
    )

    feature_table["label"] = y
    feature_table["record"] = [
        window["record"] for window in all_windows
    ]
    feature_table["start_time_seconds"] = [
        window["start_time"] for window in all_windows
    ]

    feature_table.to_csv(
        OUTPUT_DIR / "extracted_features.csv",
        index=False,
    )

    save_feature_plots(X, y)

    # IMPORTANT:
    # This is only a pipeline demonstration. It uses one recording
    # per class, and randomly splitting windows may put windows from
    # the same record in both training and testing.
    # The score is not a reliable estimate of generalization.
    train_random_forest(X, y)

    print("\n" + "=" * 60)
    print("PIPELINE FINISHED")
    print(f"Output folder: {OUTPUT_DIR.resolve()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
