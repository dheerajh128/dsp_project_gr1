# Report source map

Numerical claims in `DSP_Project_Report.docx` are taken from the files below. Scores that appear only in `Complete_Project_Report.pdf` are labelled as document claims.

## Classical three-class experiments (Group A)

| Claim | Source |
| --- | --- |
| 4 s single-record: 180 windows, 1,440 samples, 126/54 split, accuracy 0.8333, confusion matrix | `outputs/milestone3_results/previous_4s_results/previous_4s_summary.txt` |
| SNR grid 0/5/10 dB and 20 windows per class per SNR | `outputs/noisy_dataset/metadata.csv` |
| 100-tree, 6-feature forest and importances | `models/random_forest_noise_classifier.joblib` (matched by filename and feature count; the summary does not name the file) |
| 2 s initial: 900 windows, 720 samples, test 180, accuracy 0.8500, confusion matrix | `outputs/milestone3_results/previous_2s_initial_results/summary.txt` |
| 15 records, SNR 0/5/10, test records 107, 122, 209 | `outputs/noisy_dataset_2s/metadata.csv` |
| 200-tree, 6-feature forest | `models/random_forest_noise_classifier_2s.joblib` |
| Improved 2 s: accuracy 0.7766, baseline 0.7571, hyperparameters, per-class scores | `outputs/milestone3_results/improved_2s/classification_report.txt` |
| 4,500 windows, 3,372/1,128 split, record lists, 720-sample windows | `outputs/milestone3_results/improved_2s/dataset_summary.txt` and `metadata.csv` |
| 10-feature importances | `models/random_forest_noise_classifier_2s_improved.joblib` and `improved_2s/feature_importance.png` |
| Final 4 s: Gradient Boosting, accuracy 0.8005, macro F1 0.8001, per-class scores | `outputs/milestone3_results/final_4s/classification_report.txt` |
| 9,000 windows, record lists | `outputs/milestone3_results/final_4s/dataset_summary.txt` |
| 6,744/2,256 split, 1,440 samples, SNR 0/5/10/15, 30 records | `outputs/noisy_dataset_4s_final/metadata.csv` |
| Saved object is `HistGradientBoostingClassifier` (max_iter 300, learning_rate 0.05) despite the filename | `models/final_4s/random_forest_noise_classifier_4s.joblib` |
| Per-SNR accuracies 0.8617, 0.8333, 0.7766, 0.7305 | Recomputed from that joblib file and the stored test windows with `build_extended_feature_matrix`. Overall accuracy matched 0.8005. |
| Confusion-matrix counts | The raw PNG files named in `figure_inventory.csv` |

## Exploratory figures (Group B)

| Claim | Source |
| --- | --- |
| Records 100 and 118e_6, 4 s, six features, different bands | `random_forest_visualizations.py` |
| 902 windows, 451 per record, accuracy 1.0000, 271 test rows | `random_forest_figures/classification_report.txt`, `extracted_features.csv`, `predictions.csv` |
| 118e_6 is electrode motion at −6 dB | `data/noise_stress/nstdb.txt` |
| Feature means | `random_forest_figures/extracted_features.csv` |

## Deep learning

| Claim | Source |
| --- | --- |
| CNN accuracy 0.8772 and per-class scores | `outputs/milestone3_results/cnn_6hours/cnn_report.txt` |
| ResNet-101 0.8765 and 0.8590 | `resnet101_6hours/resnet_report.txt`, `resnet101_10hours/resnet_report.txt` |
| Matrix counts | The corresponding `*_confusion_raw.png` files |
| ResNet-50 STFT, 128×128, head, optimiser, epochs | `src/cnn_pipeline.py`, `main_cnn.py` (run not saved; `resnet50_opt2_opt3` is absent) |
| 89.67 / 90.87 / 89.80 and the 512-unit head | `Complete_Project_Report.pdf` only |

## Filters and datasets

| Claim | Source |
| --- | --- |
| SNR scaling and synthetic 50 Hz PLI | `src/data_generator.py` |
| Feature bands 0.05–0.5, 49–51, ≥20 Hz | `src/feature_extraction.py` |
| Butterworth 0.5 Hz, low-pass 35 Hz, notch Q = 30 | `Complete_Project_Report.pdf` Table 2. Not implemented under `src/`. |
| Block diagram and before/after figure | Images extracted from that PDF (`report_final/assets/report_p3_img0.png`, `report_p6_img0.png`) |
| Institution, course ECN15101, Group 1, four students and roll numbers | Page 1 of `Complete_Project_Report.pdf` |
| Cover layout sample and MNNIT seal | `dspreportdemo.pdf` page 1 (scanned; logo cropped from that page) |
| Google Colab QR | The image supplied in the chat, copied to `report_final/assets/colab_qr.png` |
