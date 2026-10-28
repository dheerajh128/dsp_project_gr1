"""
visualization.py

Demo/visualization layer helpers.

This module ONLY formats terminal output and produces matplotlib plots
of signals/values that are computed elsewhere (data_loader.py,
data_generator.py, feature_extraction.py, classifier.py). It does not
change any dataset, feature, or model logic.
"""

import matplotlib.pyplot as plt


def print_stage_header(title):
    """Print a consistently formatted stage header block."""
    print("=" * 60)
    print(title)
    print("=" * 60)


def print_feature_table(feature_names, feature_values):
    """
    Print a simple aligned ASCII table of feature name -> value, in the
    order given by `feature_names` / `feature_values` (must correspond
    1:1).
    """
    print("=" * 50)
    print("FEATURE EXTRACTION")
    print("=" * 50)
    print(f"{'Feature':<25}{'Value':>15}")
    print("-" * 50)
    for name, value in zip(feature_names, feature_values):
        print(f"{name:<25}{value:>15.6f}")
    print("=" * 50)


def plot_signal(time_axis, signal, title, xlabel="Time (s)", ylabel="Amplitude", color="tab:blue"):
    """
    Generic single-line plot, used for the raw ECG segment, the clean
    4-second ECG window, and each individual noise signal.
    """
    plt.figure(figsize=(10, 3))
    plt.plot(time_axis, signal, color=color)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()


def plot_noise_addition_comparison(time_axis, clean, ecg_plus_bw, ecg_plus_pli, ecg_plus_ma, snr_db):
    """
    4-panel comparison figure, all sharing the same time axis and built
    from the SAME clean ECG window: clean ECG, ECG+BW, ECG+PLI, ECG+MA.
    """
    fig, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=True)

    axes[0].plot(time_axis, clean, color="black")
    axes[0].set_title("Stage 4A — Clean ECG")

    axes[1].plot(time_axis, ecg_plus_bw, color="tab:orange")
    axes[1].set_title(f"Stage 4B — ECG + BW (SNR = {snr_db} dB)")

    axes[2].plot(time_axis, ecg_plus_pli, color="tab:green")
    axes[2].set_title(f"Stage 4C — ECG + 50 Hz PLI (SNR = {snr_db} dB)")

    axes[3].plot(time_axis, ecg_plus_ma, color="tab:red")
    axes[3].set_title(f"Stage 4D — ECG + MA (SNR = {snr_db} dB)")
    axes[3].set_xlabel("Time (s)")

    for ax in axes:
        ax.set_ylabel("Amplitude")

    fig.tight_layout()
    return fig


def plot_feature_bar_chart(feature_names, feature_values, title="Stage 5 — Extracted ECG Features"):
    """
    Bar chart of the six feature values for a single demonstration
    window, in their natural (unsorted) order.
    """
    plt.figure(figsize=(7, 4))
    plt.bar(feature_names, feature_values, color="tab:purple")
    plt.title(title)
    plt.ylabel("Feature value")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
