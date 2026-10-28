"""
feature_extraction.py
Milestone 3: Core descriptive and spectral feature extraction.
"""
import numpy as np
from scipy import stats
from scipy.signal import welch

_trapezoid = getattr(np, "trapezoid", None) or np.trapz

FEATURE_NAMES = [
    "rms",
    "variance",
    "kurtosis",
    "low_freq_power",
    "pli_power_50hz",
    "high_freq_power",
    "low_freq_ratio",
    "high_freq_ratio",
]

LOW_FREQ_BAND = (0.05, 0.5)     # Cut off sub-0.05 Hz pure DC offset
PLI_BAND = (49.0, 51.0)         # 50 Hz power-line interference
HIGH_FREQ_BAND_MIN_HZ = 20.0    # Muscle artifact / EMG band

def _band_power(freqs, psd, band):
    low, high = band
    mask = np.logical_and(freqs >= low, freqs <= high)
    if not np.any(mask):
        return 0.0
    return float(_trapezoid(psd[mask], freqs[mask]))

def extract_features(window, fs):
    window = np.asarray(window, dtype=float)
    # Remove pure DC offset so it does not distort low-frequency spectral calculations
    window_zero_mean = window - np.mean(window)
    
    rms = float(np.sqrt(np.mean(window ** 2)))
    variance = float(np.var(window))
    kurt = float(stats.kurtosis(window))
    
    # 4-second window (1440 samples) gives 0.25 Hz resolution
    nperseg = len(window)
    freqs, psd = welch(window_zero_mean, fs=fs, nperseg=nperseg)
    total_power = float(_trapezoid(psd, freqs)) + 1e-12
    
    low_freq_power = _band_power(freqs, psd, LOW_FREQ_BAND)
    pli_power = _band_power(freqs, psd, PLI_BAND)
    high_freq_power = _band_power(freqs, psd, (HIGH_FREQ_BAND_MIN_HZ, freqs[-1]))
    
    return {
        "rms": rms,
        "variance": variance,
        "kurtosis": kurt,
        "low_freq_power": low_freq_power,
        "pli_power_50hz": pli_power,
        "high_freq_power": high_freq_power,
        "low_freq_ratio": float(low_freq_power / total_power),
        "high_freq_ratio": float(high_freq_power / total_power),
    }

def build_feature_matrix(X, fs):
    feature_dicts = [extract_features(window, fs) for window in X]
    feature_matrix = np.array(
        [[fd[name] for name in FEATURE_NAMES] for fd in feature_dicts]
    )
    return feature_matrix, FEATURE_NAMES