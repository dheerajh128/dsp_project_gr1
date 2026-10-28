"""
experiment_improved.py
Extended interpretable features, separability stats, and hyperparameter tuning.
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from src.feature_extraction import extract_features, FEATURE_NAMES, LOW_FREQ_BAND, HIGH_FREQ_BAND_MIN_HZ

EXTRA_FEATURE_NAMES = [
    "zero_crossing_rate",
    "spectral_entropy",
    "dominant_frequency_hz",
    "low_high_band_power_ratio",
    "mean_abs_diff",
    "hjorth_mobility",
]

def zero_crossing_rate(window):
    w = window - np.mean(window)
    signs = np.sign(w)
    signs[signs == 0] = 1
    crossings = np.sum(np.abs(np.diff(signs)) > 0)
    return float(crossings / max(1, len(window) - 1))

def spectral_entropy(window, fs):
    w = window - np.mean(window)
    freqs, psd = welch(w, fs=fs, nperseg=len(w))
    psd_norm = psd / (np.sum(psd) + 1e-12)
    psd_norm = psd_norm[psd_norm > 0]
    if len(psd_norm) <= 1:
        return 0.0
    entropy = -np.sum(psd_norm * np.log2(psd_norm))
    max_entropy = np.log2(len(psd_norm))
    return float(entropy / max_entropy) if max_entropy > 0 else 0.0

def dominant_frequency(window, fs):
    w = window - np.mean(window)
    freqs, psd = welch(w, fs=fs, nperseg=len(w))
    return float(freqs[np.argmax(psd)])

def low_high_band_power_ratio(window, fs):
    w = window - np.mean(window)
    freqs, psd = welch(w, fs=fs, nperseg=len(w))
    _trap = getattr(np, "trapezoid", None) or np.trapz
    
    mask_low = np.logical_and(freqs >= LOW_FREQ_BAND[0], freqs <= LOW_FREQ_BAND[1])
    mask_high = np.logical_and(freqs >= HIGH_FREQ_BAND_MIN_HZ, freqs <= freqs[-1])
    
    low = float(_trap(psd[mask_low], freqs[mask_low])) if np.any(mask_low) else 0.0
    high = float(_trap(psd[mask_high], freqs[mask_high])) if np.any(mask_high) else 0.0
    return float(low / (high + 1e-12))

def mean_abs_diff(window):
    """Mean absolute point-to-point change (dramatically higher in MA than BW)."""
    return float(np.mean(np.abs(np.diff(window))))

def hjorth_mobility(window):
    """Ratio of derivative variance to signal variance (mean frequency indicator)."""
    var_zero = np.var(window)
    if var_zero < 1e-12:
        return 0.0
    diff1 = np.diff(window)
    var_d1 = np.var(diff1)
    return float(np.sqrt(var_d1 / var_zero))

def extract_extra_features(window, fs):
    return {
        "zero_crossing_rate": zero_crossing_rate(window),
        "spectral_entropy": spectral_entropy(window, fs),
        "dominant_frequency_hz": dominant_frequency(window, fs),
        "low_high_band_power_ratio": low_high_band_power_ratio(window, fs),
        "mean_abs_diff": mean_abs_diff(window),
        "hjorth_mobility": hjorth_mobility(window),
    }

def build_extended_feature_matrix(X, fs):
    rows = []
    for window in X:
        core = extract_features(window, fs)
        extra = extract_extra_features(window, fs)
        rows.append([core[n] for n in FEATURE_NAMES] + [extra[n] for n in EXTRA_FEATURE_NAMES])
    feature_names_all = list(FEATURE_NAMES) + list(EXTRA_FEATURE_NAMES)
    return np.array(rows), feature_names_all

def hyperparameter_search(X_train, y_train, seed=42, n_iter=15, cv=3):
    """Lighter search space for faster execution."""
    param_dist = {
        "n_estimators": [300, 500],             # Removed 800 and 1000
        "max_depth": [None, 15, 25],
        "min_samples_split": [2, 4],
        "min_samples_leaf": [1, 2],
        "max_features": ["sqrt", "log2"],       # Removed 'None' which causes massive slowdowns
    }
    base_model = RandomForestClassifier(random_state=seed, n_jobs=-1)
    cv_strategy = StratifiedKFold(n_splits=cv, shuffle=True, random_state=seed)
    
    # n_iter changed to 15 (45 total fits instead of 150)
    search = RandomizedSearchCV(
        base_model, param_distributions=param_dist, n_iter=15,
        cv=cv_strategy, scoring="f1_macro", random_state=seed, n_jobs=-1,
    )
    search.fit(X_train, y_train)
    return search.best_estimator_, search.best_params_, search.best_score_

def compare_bw_ma_features(X_features, y, feature_names):
    stats_dict = {}
    for cls in ["BW", "MA"]:
        mask = (y == cls)
        stats_dict[cls] = {
            "mean": X_features[mask].mean(axis=0),
            "std": X_features[mask].std(axis=0),
        }
    return stats_dict

def plot_bw_ma_feature_comparison(stats_dict, feature_names, output_path=None):
    n = len(feature_names)
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 3 * nrows))
    axes = np.array(axes).reshape(-1)
    for i, name in enumerate(feature_names):
        ax = axes[i]
        means = [stats_dict["BW"]["mean"][i], stats_dict["MA"]["mean"][i]]
        stds = [stats_dict["BW"]["std"][i], stats_dict["MA"]["std"][i]]
        ax.bar(["BW", "MA"], means, yerr=stds, color=["tab:orange", "tab:red"], capsize=4)
        ax.set_title(name, fontsize=9)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle("BW vs MA Feature Comparison (mean ± std)")
    fig.tight_layout()
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path)
    return fig

def plot_accuracy_by_snr(snr_results, output_path=None):
    snrs = sorted(snr_results.keys())
    accs = [snr_results[s]["accuracy"] for s in snrs]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(snrs, accs, marker="o", color="tab:blue", lw=2)
    ax.set_xlabel("SNR (dB)")
    ax.set_ylabel("Accuracy")
    ax.set_title("Accuracy by SNR")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path)
    return fig