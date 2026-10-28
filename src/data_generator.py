"""
data_generator.py

Milestone 2: Create labeled noisy ECG data for later ML use.

This module ONLY builds the dataset (clean ECG windows mixed with a single
noise type at a controlled SNR, labeled by noise type). It does NOT do any
feature extraction, filtering, or model training — those belong to later
milestones.

Noise types handled:
    - BW  : real Baseline Wander segments from the NSTDB 'bw' record
    - PLI : synthetically generated 50 Hz sinusoidal interference
    - MA  : real Muscle Artifact segments from the NSTDB 'ma' record
"""

import os
import csv

import numpy as np

# Base (pre-scaling) amplitude used to synthesize the 50 Hz PLI waveform.
# This is NOT the final injected amplitude — add_noise_at_snr() rescales
# whatever noise waveform it is given (real or synthetic) so that the
# mixed signal hits the requested target SNR. This constant only fixes
# the *shape* of the raw PLI waveform to a controlled, known value
# (a unit-amplitude sine) instead of an arbitrary/undocumented number.
PLI_BASE_AMPLITUDE = 1.0


def create_pli(fs, duration_sec, amplitude=PLI_BASE_AMPLITUDE, frequency_hz=50.0):
    """
    Generate a synthetic power-line interference (PLI) signal:
        noise(t) = amplitude * sin(2 * pi * frequency_hz * t)

    Returns (time_axis, pli_signal) as numpy arrays.
    """
    n_samples = int(round(duration_sec * fs))
    t = np.arange(n_samples) / fs
    pli_signal = amplitude * np.sin(2 * np.pi * frequency_hz * t)
    return t, pli_signal


def calculate_noise_scaling(clean_signal, noise_signal, target_snr_db):
    """
    Compute the scalar factor that, when multiplied into `noise_signal`,
    makes the mixture clean_signal + (scaling * noise_signal) achieve the
    requested target_snr_db, using:

        SNR(dB) = 10 * log10(P_signal / P_noise)

    Returns a float scaling factor.
    """
    signal_power = np.mean(np.square(clean_signal))
    noise_power = np.mean(np.square(noise_signal))

    if noise_power <= 1e-12:
        raise ValueError(
            "Noise segment has (near) zero power, so it cannot be scaled to "
            "hit a target SNR. This usually means a noise window was pulled "
            "from a flat/silent stretch of the recording — pick a different "
            "starting position."
        )

    target_noise_power = signal_power / (10 ** (target_snr_db / 10.0))
    scaling = np.sqrt(target_noise_power / noise_power)
    return scaling


def add_noise_at_snr(clean_signal, noise_signal, target_snr_db):
    """
    Add `noise_signal` to `clean_signal`, rescaled so the result has the
    requested target_snr_db. clean_signal and noise_signal must be the
    same length.

    Returns the noisy signal as a numpy array.
    """
    clean_signal = np.asarray(clean_signal, dtype=float)
    noise_signal = np.asarray(noise_signal, dtype=float)

    if clean_signal.shape != noise_signal.shape:
        raise ValueError(
            f"Clean signal length ({clean_signal.shape[0]}) and noise signal "
            f"length ({noise_signal.shape[0]}) must match before mixing."
        )

    scaling = calculate_noise_scaling(clean_signal, noise_signal, target_snr_db)
    noisy_signal = clean_signal + scaling * noise_signal
    return noisy_signal


def _get_ecg_channel_index(ecg_record, preferred_name="MLII"):
    """
    Return the index of the preferred ECG channel (MLII) if present,
    otherwise fall back to channel 0 with a warning.
    """
    if preferred_name in ecg_record.sig_name:
        return ecg_record.sig_name.index(preferred_name)

    print(
        f"[WARNING] Channel '{preferred_name}' not found in this ECG record "
        f"(available channels: {ecg_record.sig_name}). Falling back to "
        f"channel index 0."
    )
    return 0


def _random_window(signal_1d, window_samples, rng):
    """
    Pick a random valid start index into `signal_1d` and return
    (start_index, window_slice).
    """
    max_start = len(signal_1d) - window_samples
    if max_start <= 0:
        raise ValueError(
            f"Signal length ({len(signal_1d)}) is shorter than the "
            f"requested window length ({window_samples}); cannot extract a window."
        )
    start = int(rng.integers(0, max_start))
    return start, signal_1d[start:start + window_samples]


def generate_noisy_dataset(
    ecg_record,
    bw_record,
    ma_record,
    window_samples,
    snr_list,
    samples_per_class_per_snr=20,
    seed=42,
):
    """
    Build a labeled dataset of noisy ECG windows.

    For each noise type in {BW, PLI, MA} and each SNR value in `snr_list`,
    generate `samples_per_class_per_snr` windows by:
        1. Picking a random clean ECG window (channel MLII).
        2. Picking/generating a matching-length noise window (BW/MA use a
           random real segment; PLI is synthesized fresh each time).
        3. Mixing them at the target SNR via add_noise_at_snr().

    Exactly one noise type is present per window (no mixing of noise types).

    Returns:
        X (np.ndarray): shape (n_samples, window_samples)
        y (np.ndarray): shape (n_samples,), dtype=str, values in {'BW','PLI','MA'}
        metadata (list[dict]): one dict per sample with sample_id, noise_type,
            snr_db, ecg_start_sample, noise_start_sample, fs, window_samples
    """
    rng = np.random.default_rng(seed)

    ecg_channel_index = _get_ecg_channel_index(ecg_record, "MLII")
    ecg_signal = ecg_record.p_signal[:, ecg_channel_index]
    bw_signal = bw_record.p_signal[:, 0]
    ma_signal = ma_record.p_signal[:, 0]
    fs = ecg_record.fs

    X = []
    y = []
    metadata = []
    sample_id = 0

    noise_types = ["BW", "PLI", "MA"]

    for noise_type in noise_types:
        for snr_db in snr_list:
            generated = 0
            attempts = 0
            max_attempts = samples_per_class_per_snr * 20  # safety margin

            while generated < samples_per_class_per_snr and attempts < max_attempts:
                attempts += 1

                ecg_start, clean_window = _random_window(ecg_signal, window_samples, rng)

                noise_start = None
                try:
                    if noise_type == "BW":
                        noise_start, noise_window = _random_window(bw_signal, window_samples, rng)
                    elif noise_type == "MA":
                        noise_start, noise_window = _random_window(ma_signal, window_samples, rng)
                    elif noise_type == "PLI":
                        _, noise_window = create_pli(fs, window_samples / fs)
                    else:
                        raise ValueError(f"Unknown noise type: {noise_type}")

                    noisy_window = add_noise_at_snr(clean_window, noise_window, snr_db)

                except ValueError as e:
                    # e.g. a zero-power noise segment was drawn — retry with a
                    # different random window instead of silently skipping.
                    print(f"[WARNING] Retrying {noise_type} sample (attempt {attempts}): {e}")
                    continue

                X.append(noisy_window)
                y.append(noise_type)
                metadata.append({
                    "sample_id": sample_id,
                    "noise_type": noise_type,
                    "snr_db": snr_db,
                    "ecg_start_sample": ecg_start,
                    "noise_start_sample": noise_start,
                    "fs": fs,
                    "window_samples": window_samples,
                })
                sample_id += 1
                generated += 1

            if generated < samples_per_class_per_snr:
                print(
                    f"[WARNING] Only generated {generated}/{samples_per_class_per_snr} "
                    f"samples for noise_type={noise_type}, snr_db={snr_db} "
                    f"after {attempts} attempts."
                )

    X = np.array(X)
    y = np.array(y)
    return X, y, metadata


def save_dataset(X, y, metadata, output_dir):
    """
    Save X, y as .npy files and metadata as a CSV file inside output_dir.
    Creates output_dir (and parents) if it doesn't exist.
    """
    os.makedirs(output_dir, exist_ok=True)

    x_path = os.path.join(output_dir, "X.npy")
    y_path = os.path.join(output_dir, "y.npy")
    meta_path = os.path.join(output_dir, "metadata.csv")

    np.save(x_path, X)
    np.save(y_path, y)

    if metadata:
        fieldnames = list(metadata[0].keys())
        with open(meta_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(metadata)

    print(f"Saved X to:        {x_path}")
    print(f"Saved y to:        {y_path}")
    print(f"Saved metadata to: {meta_path}")
