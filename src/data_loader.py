"""
data_loader.py

Reusable helper functions for Milestone 1 of the ECG Noise Classification
project. This module only handles dataset discovery, loading, and basic
inspection using the WFDB library. No signal processing, filtering,
feature extraction, or ML code lives here.
"""

import os
import glob
import wfdb


def find_records(directory):
    """
    Scan a directory for WFDB records by looking for .hea (header) files.
    Returns a sorted list of record names (without extension),
    e.g. ['100', '101', ...].

    We do NOT hard-code record names anywhere - we discover whatever is
    actually present on disk.
    """
    if not os.path.isdir(directory):
        raise FileNotFoundError(
            f"Directory not found: '{directory}'. "
            f"Check that the dataset was downloaded and placed at this exact path."
        )

    header_files = glob.glob(os.path.join(directory, "*.hea"))

    if not header_files:
        raise FileNotFoundError(
            f"No WFDB header (.hea) files found in '{directory}'. "
            f"Expected record header files here. "
            f"Please verify the dataset was downloaded/extracted correctly."
        )

    record_names = sorted(
        os.path.splitext(os.path.basename(f))[0] for f in header_files
    )
    return record_names


def load_record(directory, record_name):
    """
    Load a single WFDB record (signal + header) given its directory and name.
    Returns a wfdb.Record object.
    """
    record_path = os.path.join(directory, record_name)
    try:
        record = wfdb.rdrecord(record_path)
    except Exception as e:
        raise RuntimeError(
            f"Failed to load record '{record_name}' from '{directory}'.\n"
            f"Reason: {e}\n"
            f"Make sure both the .hea file and its matching signal file "
            f"(.dat) exist and are not corrupted."
        ) from e
    return record


def print_record_info(record):
    """
    Print key metadata for a loaded wfdb.Record object.
    Returns the duration in seconds (float).
    """
    duration_sec = record.sig_len / record.fs

    print(f"Record:              {record.record_name}")
    print(f"Sampling frequency:  {record.fs} Hz")
    print(f"Number of samples:   {record.sig_len}")
    print(f"Number of channels:  {record.n_sig}")
    print(f"Channel names:       {record.sig_name}")
    print(f"Duration:            {duration_sec:.2f} seconds")
    print()

    return duration_sec


def find_first_loadable_record(directory):
    """
    Try each discovered record in a directory until one loads successfully.
    Returns (record_name, record_object).

    This avoids hard-coding a record number that might not exist in the
    user's actual downloaded copy of the database.
    """
    candidates = find_records(directory)
    last_error = None

    for name in candidates:
        try:
            record = load_record(directory, name)
            return name, record
        except RuntimeError as e:
            last_error = e
            print(f"[WARNING] Skipping unreadable record '{name}': {e}")
            continue

    raise RuntimeError(
        f"None of the {len(candidates)} record(s) found in '{directory}' "
        f"could be loaded successfully.\nLast error: {last_error}"
    )


def find_named_record(directory, keyword):
    """
    Search for a record whose name matches `keyword` exactly (case-insensitive),
    or, failing that, contains `keyword` as a substring.

    Used to locate 'bw' (baseline wander) and 'ma' (muscle artifact) records
    inside the Noise Stress Test Database, whatever their exact filenames are.
    """
    candidates = find_records(directory)
    keyword_lower = keyword.lower()

    # 1. Exact match first (e.g. a record literally named "bw" or "ma")
    exact_matches = [r for r in candidates if r.lower() == keyword_lower]
    if exact_matches:
        return exact_matches[0]

    # 2. Fallback: substring match
    partial_matches = [r for r in candidates if keyword_lower in r.lower()]
    if partial_matches:
        return partial_matches[0]

    raise FileNotFoundError(
        f"Could not find a record matching '{keyword}' in '{directory}'.\n"
        f"Records actually present: {candidates}"
    )


def extract_segment(record, channel_index=0, duration_sec=4.0, start_sec=0.0):
    """
    Extract a short segment of a signal channel for plotting.
    Returns (time_axis_list, signal_segment_array).
    """
    fs = record.fs

    if channel_index >= record.n_sig:
        raise ValueError(
            f"Requested channel index {channel_index} but record only has "
            f"{record.n_sig} channel(s)."
        )

    start_sample = int(start_sec * fs)
    n_samples = int(duration_sec * fs)
    end_sample = min(start_sample + n_samples, record.sig_len)

    if start_sample >= record.sig_len:
        raise ValueError(
            f"Requested start time {start_sec}s is beyond the record length "
            f"({record.sig_len / fs:.2f}s)."
        )

    segment = record.p_signal[start_sample:end_sample, channel_index]
    time_axis = [start_sec + i / fs for i in range(len(segment))]

    return time_axis, segment
