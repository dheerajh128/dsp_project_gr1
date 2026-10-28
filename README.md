# Intelligent ECG Noise Classification and Dynamic DSP Filtering

A Digital Signal Processing (DSP) project that combines **deep learning and classical digital filters** to automatically identify noise in ECG signals and select an appropriate filter for restoration.

## Overview

Electrocardiogram (ECG) signals can be corrupted by different types of noise, affecting the reliability of cardiac signal analysis. This project implements an intelligent pipeline that classifies the dominant noise type using a CNN and dynamically routes the signal through a corresponding DSP filter.

The system focuses on three common ECG noise classes:

- **Baseline Wander (BW):** Low-frequency drift in the ECG baseline.
- **Muscle Artifact (MA):** High-frequency and broadband interference caused by muscle activity.
- **Power-Line Interference (PLI):** Electrical interference around 50 Hz.

## Project Pipeline

1. Load clean ECG signals and noise recordings.
2. Generate labelled noisy ECG windows at controlled signal-to-noise ratios (SNRs).
3. Compute the Short-Time Fourier Transform (STFT) and generate log-magnitude spectrograms.
4. Classify each spectrogram using an ImageNet-pretrained ResNet-50 CNN.
5. Route the ECG window to the DSP filter associated with the predicted noise class.
6. Evaluate classification performance and inspect the restored signals in the time and frequency domains.

## System Architecture

```text
          Noisy ECG Signal
                  |
          Fixed-Length Windows
                  |
           STFT Spectrogram
                  |
          ResNet-50 Classifier
                  |
          Predicted Noise Class
           /       |       \
          BW       MA       PLI
          |        |         |
       High-Pass  Low-Pass   Notch
        Filter    Filter    Filter
          \        |        /
             Restored ECG
                  |
       Time/Frequency Evaluation
```

## Technologies Used

- **Python** — signal processing and model development
- **NumPy and SciPy** — numerical operations and DSP filters
- **Matplotlib** — signal plots and evaluation visualizations
- **Scikit-learn** — Random Forest baseline and evaluation metrics
- **TensorFlow/Keras** — ResNet-50 CNN training and inference
- **STFT and FFT** — time-frequency analysis

## Dataset

The project uses ECG recordings from the following PhysioNet datasets:

- [MIT-BIH Arrhythmia Database](https://physionet.org/content/mitdb/1.0.0/) — clean ECG reference signals.
- [MIT-BIH Noise Stress Test Database](https://physionet.org/content/nstdb/1.0.0/) — baseline-wander and muscle-artifact noise recordings.

Power-line interference is modelled at 50 Hz. Refer to the implementation for its exact generation or sourcing method.

The CNN experiment uses labelled noisy ECG windows generated at SNR levels of **0, 5, 10 and 15 dB**. The reported held-out test set contains 4,500 windows, with 1,500 samples per class.

> The original ECG datasets are not included in this README. Follow their respective dataset terms and instructions when downloading and using them.

## DSP Filter Bank

| Noise class | Filter | Purpose |
|---|---|---|
| BW | 4th-order Butterworth high-pass filter, 0.5 Hz | Reduce slow baseline drift |
| MA | 4th-order Butterworth low-pass filter, 35 Hz | Attenuate high-frequency noise |
| PLI | IIR notch filter, 50 Hz, Q = 30 | Suppress power-line interference |

The classifier selects the filter; the restoration stage uses conventional DSP techniques for predictable signal processing.

## Machine Learning Experiments

Two approaches were investigated:

### 1. Random Forest baseline

The initial approach uses engineered ECG features, including RMS, variance, kurtosis, and frequency-band power.

A record-level split produced approximately **77.7% accuracy** in the original three-class experiment.

An additional exploratory Clean-vs-Noisy experiment reported 100% accuracy on 271 samples. This is a separate binary experiment and should not be compared directly with the three-class results.

### 2. ResNet-50 classifier

A pretrained ResNet-50 was adapted to classify spectrograms into BW, MA and PLI. Different classifier-head configurations and regularization strategies were evaluated.

| Configuration | Test accuracy |
|---|---:|
| Baseline ResNet-50 | 89.67% |
| ResNet-50 + L2 regularization + label smoothing | **90.87%** |
| 64-unit bottleneck + dropout | 89.80% |

The best reported configuration achieved **90.87% accuracy** on the held-out test set. PLI classification was nearly perfect, while most remaining errors occurred between BW and MA.

These are classification results; they do not establish equivalent quantitative performance for ECG restoration.

## Evaluation and Visualizations

The project includes visualizations and results for:

- Clean and noisy ECG recordings
- Four-second ECG windows
- Feature distributions and feature importance
- Confusion matrices
- Accuracy versus SNR
- Classification reports
- Time-domain and frequency-domain filter verification

## Repository Structure

The structure below is illustrative. Adapt it to match the files actually present in the repository.

```text
dsp_project/
├── data/
│   ├── mit_db/
│   └── noise_stress/
├── outputs/
│   └── milestone3_results/
├── random_forest_figures/
├── src/
├── notebooks/
├── README.md
└── .gitignore
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/dheerajh128/dsp_project_gr1.git
cd dsp_project_gr1
```

### 2. Create a Python environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

If the repository contains a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

Otherwise, install the packages required by the specific scripts or notebooks. Check the project's imports and environment before running the pipeline.

### 4. Prepare the datasets

Download the required PhysioNet datasets and place the records in the locations expected by the project scripts. Verify the dataset paths before running the experiments.

### 5. Run the project

Run the relevant notebook or Python entry point documented in the source code. The exact execution command depends on the implementation included in this repository.

## Limitations

- BW and MA have overlapping frequency characteristics, making them harder to distinguish.
- A fixed low-pass filter cannot eliminate all muscle artifact without potentially affecting useful ECG components.
- The reported filter verification is primarily visual and spectral; comprehensive restoration metrics such as RMSE and SNR improvement remain future work.
- Classification results depend on the dataset, record split, preprocessing, and training configuration.

## Future Improvements

- Evaluate restoration quantitatively using RMSE, SNR improvement, and QRS morphology preservation.
- Compare the dynamic filter bank with fixed-filter baselines.
- Improve discrimination between baseline wander and muscle artifact.
- Evaluate across additional patients and ECG recordings.
- Repeat training runs to measure the variability of model performance.

## Team

**Group 1 — B.Tech. Electronics and Communication Engineering**

Digital Signal Processing — ECN15101

- Ayush Kumar Jha
- Bayapureddy Dheerajh Reddy
- Bhaskar Jalan
- Bhawani Singh Shekhawat

## Acknowledgements

We acknowledge PhysioNet and the contributors to the MIT-BIH Arrhythmia Database and MIT-BIH Noise Stress Test Database for making ECG research data available.

## License

Add an appropriate license before distributing this repository. Dataset use remains subject to the original dataset terms.
