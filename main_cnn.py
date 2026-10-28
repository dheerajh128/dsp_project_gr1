
"""
main_cnn.py
ResNet-50 Transfer Learning Pipeline (20-Hour Dataset, 20 Total Epochs)
Combats overfitting using:
  - Option 2: L2 Weight Regularization (Weight Decay: 1e-4)
  - Option 3: Categorical Cross-Entropy with Label Smoothing (0.1)
Training Setup:
  - 5 Warmup Epochs (Backbone Locked)
  - 15 Fine-Tuning Epochs (Top Residual Blocks Unlocked)
  - Comprehensive Training & Validation Loss/Accuracy Curves
"""
import os
import gc
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
from sklearn.metrics import balanced_accuracy_score, classification_report, confusion_matrix
from tensorflow.keras.utils import to_categorical

from src.data_loader import load_record
from src.experiment_2s import (
    discover_and_load_ecg_records, split_records_train_test, split_signal_train_test,
    generate_split_dataset, plot_confusion_matrix_normalized
)
from src.cnn_pipeline import signal_to_spectrogram_images, encode_labels
from src.visualization import print_stage_header
from src.classifier import plot_confusion_matrix

from tensorflow.keras.applications import ResNet50
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout, BatchNormalization
from tensorflow.keras.regularizers import l2
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau

MIT_DB_DIR = "data/mit_db"
NOISE_DIR = "data/noise_stress"
BW_RECORD_NAME, MA_RECORD_NAME = "bw", "ma"
CNN_OUT_DIR = "outputs/milestone3_results/resnet50_opt2_opt3"

FS_EXPECTED = 360
WINDOW_DURATION_SEC = 4.0

# --- 20 HOURS CONFIGURATION ---
N_ECG_RECORDS = 42
TARGET_PER_CLASS = 6000       # 6,000 * 3 classes = 18,000 windows * 4s = 72,000s = 20 Hours
TRAIN_FRACTION = 0.75         # 13,500 train windows / 4,500 test windows
SNR_LIST = [0, 5, 10, 15]
RANDOM_SEED = 42

BATCH_SIZE = 64
WARMUP_EPOCHS = 5             # 5 Epochs locked backbone
FINETUNE_EPOCHS = 15          # 15 Epochs fine-tuning
TOTAL_EPOCHS = WARMUP_EPOCHS + FINETUNE_EPOCHS

# Option 2 & 3 Parameters
L2_REG_FACTOR = 1e-4          # Option 2: L2 Weight Regularization
LABEL_SMOOTHING = 0.1         # Option 3: Label Smoothing factor


def plot_learning_curves(history_dict, output_path):
    """
    Plots training vs validation accuracy and loss across all 20 epochs,
    with an indicator for the fine-tuning transition point.
    """
    acc = history_dict['accuracy']
    val_acc = history_dict['val_accuracy']
    loss = history_dict['loss']
    val_loss = history_dict['val_loss']
    epochs_range = range(1, len(acc) + 1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # --- Accuracy Plot ---
    ax1.plot(epochs_range, acc, label='Training Accuracy', color='#1f77b4', lw=2.5)
    ax1.plot(epochs_range, val_acc, label='Validation / Test Accuracy', color='#ff7f0e', lw=2.5)
    ax1.axvline(x=WARMUP_EPOCHS, color='gray', linestyle='--', label=f'Fine-Tuning Start (Epoch {WARMUP_EPOCHS})')
    ax1.set_xlabel('Epochs', fontsize=12)
    ax1.set_ylabel('Accuracy', fontsize=12)
    ax1.set_title('Training vs. Validation Accuracy (L2 + Label Smoothing)', fontsize=13, fontweight='bold')
    ax1.set_ylim([0.70, 1.0])
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='lower right', fontsize=11)

    # --- Loss Plot (Overfitting Metric) ---
    ax2.plot(epochs_range, loss, label='Training Loss', color='#1f77b4', lw=2.5)
    ax2.plot(epochs_range, val_loss, label='Validation / Test Loss', color='#ff7f0e', lw=2.5)
    ax2.axvline(x=WARMUP_EPOCHS, color='gray', linestyle='--', label=f'Fine-Tuning Start (Epoch {WARMUP_EPOCHS})')
    ax2.set_xlabel('Epochs', fontsize=12)
    ax2.set_ylabel('Cross-Entropy Loss', fontsize=12)
    ax2.set_title('Training vs. Validation Loss (Overfitting Diagnostic)', fontsize=13, fontweight='bold')
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='upper right', fontsize=11)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"\n[Saved] Learning curves plot written to:\n  -> {output_path}")


def build_regularized_resnet50(input_shape=(128, 128, 3), num_classes=3):
    """
    ResNet-50 incorporating Option 2 (L2 Weight Regularization on Dense Layers).
    """
    base_model = ResNet50(input_shape=input_shape, include_top=False, weights='imagenet')
    base_model.trainable = False

    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = BatchNormalization()(x)
    x = Dropout(0.4)(x)
    
    # OPTION 2: L2 Regularization applied to intermediate projection weights
    x = Dense(
        128, 
        activation='relu', 
        kernel_regularizer=l2(L2_REG_FACTOR)
    )(x)
    x = BatchNormalization()(x)
    x = Dropout(0.4)(x)
    
    # OPTION 2: L2 Regularization applied to final softmax output weights
    outputs = Dense(
        num_classes, 
        activation='softmax', 
        kernel_regularizer=l2(L2_REG_FACTOR)
    )(x)

    model = Model(inputs=base_model.input, outputs=outputs)
    return model, base_model


def main():
    print("=" * 60)
    print("ResNet-50 20-Hour Run with L2 Regularization & Label Smoothing")
    print("=" * 60)

    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print(f"Accelerating on GPU: {gpus[0].name}")
    else:
        print("[WARNING] No GPU detected! Running on CPU.")

    window_samples = int(round(WINDOW_DURATION_SEC * FS_EXPECTED))

    # --- 1. DATASET GENERATION (20 Hours) ---
    print_stage_header("DATASET GENERATION (20 Hours)")
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

    print(f"Synthesizing 20 hours ({TARGET_PER_CLASS * 3} windows)...")
    X_train_raw, y_train, _, X_test_raw, y_test, _ = generate_split_dataset(
        ecg_train, ecg_test, bw_signal_train, bw_signal_test, ma_signal_train, ma_signal_test,
        window_samples, SNR_LIST, target_per_class_train, target_per_class_test,
        FS_EXPECTED, seed=RANDOM_SEED,
    )

    # --- 2. SPECTROGRAMS & ONE-HOT ENCODING ---
    print_stage_header("SPECTROGRAM CONVERSION")
    X_train_img = signal_to_spectrogram_images(X_train_raw, FS_EXPECTED, img_size=(128, 128))
    X_test_img = signal_to_spectrogram_images(X_test_raw, FS_EXPECTED, img_size=(128, 128))

    y_train_idx, y_test_idx, class_names = encode_labels(y_train, y_test)
    
    # One-hot encoding required for label smoothing
    y_train_cat = to_categorical(y_train_idx, num_classes=3)
    y_test_cat = to_categorical(y_test_idx, num_classes=3)

    del X_train_raw, X_test_raw, ecg_records
    gc.collect()

    # --- 3. STAGE 1: WARMUP TRAINING (5 EPOCHS) ---
    print_stage_header(f"STAGE 1: WARMUP (Epochs 1-{WARMUP_EPOCHS} - Frozen Backbone)")
    model, base_model = build_regularized_resnet50(input_shape=(128, 128, 3), num_classes=3)
    
    # OPTION 3: Categorical Cross-Entropy with Label Smoothing
    loss_fn = tf.keras.losses.CategoricalCrossentropy(label_smoothing=LABEL_SMOOTHING)

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss=loss_fn,
        metrics=['accuracy']
    )

    os.makedirs(CNN_OUT_DIR, exist_ok=True)
    best_weights_path = os.path.join(CNN_OUT_DIR, "best_resnet50_opt2_opt3.weights.h5")

    callbacks = [
        ModelCheckpoint(filepath=best_weights_path, monitor='val_loss', save_best_only=True, save_weights_only=True, verbose=1),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, min_lr=1e-6, verbose=1),
        EarlyStopping(monitor='val_loss', patience=7, restore_best_weights=True, verbose=1)
    ]

    history_stage1 = model.fit(
        X_train_img, y_train_cat,
        validation_data=(X_test_img, y_test_cat),
        epochs=WARMUP_EPOCHS,
        batch_size=BATCH_SIZE,
        verbose=1
    )

    # --- 4. STAGE 2: FINE-TUNING (15 EPOCHS) ---
    print_stage_header(f"STAGE 2: FINE-TUNING (Epochs {WARMUP_EPOCHS+1}-{TOTAL_EPOCHS} - Unfrozen conv5)")
    base_model.trainable = True
    # Freeze all layers except the last residual block (conv5_block*)
    for layer in base_model.layers[:-25]:
        layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
        loss=loss_fn,
        metrics=['accuracy']
    )

    history_stage2 = model.fit(
        X_train_img, y_train_cat,
        validation_data=(X_test_img, y_test_cat),
        epochs=TOTAL_EPOCHS,
        initial_epoch=WARMUP_EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1
    )

    # Combine histories across all 20 epochs
    combined_history = {}
    for key in history_stage1.history.keys():
        combined_history[key] = history_stage1.history[key] + history_stage2.history[key]

    plot_learning_curves(combined_history, os.path.join(CNN_OUT_DIR, "accuracy_loss_curves.png"))

    if os.path.exists(best_weights_path):
        model.load_weights(best_weights_path)

    # --- 5. FINAL EVALUATION ---
    print_stage_header("FINAL EVALUATION ON HELD-OUT TEST PATIENTS")
    y_pred_probs = model.predict(X_test_img)
    y_pred_idx = np.argmax(y_pred_probs, axis=1)

    test_acc = np.mean(y_pred_idx == y_test_idx)
    bal_acc = balanced_accuracy_score(y_test_idx, y_pred_idx)

    print(f"\nFinal Test Accuracy: {test_acc * 100:.2f}%")
    print(f"Final Balanced Acc:  {bal_acc * 100:.2f}%")

    report = classification_report(y_test_idx, y_pred_idx, target_names=class_names)
    print("\nClassification Report:\n", report)

    cm = confusion_matrix(y_test_idx, y_pred_idx)
    plot_confusion_matrix(cm, class_names, os.path.join(CNN_OUT_DIR, "confusion_raw.png"))
    plot_confusion_matrix_normalized(cm, class_names, os.path.join(CNN_OUT_DIR, "confusion_norm.png"))

    with open(os.path.join(CNN_OUT_DIR, "report.txt"), "w") as f:
        f.write("Model: ResNet-50 (L2 Regularization + Label Smoothing)\n")
        f.write(f"Setup: 20 Hours, 5 Warmup + 15 Fine-Tuning Epochs\n")
        f.write(f"Accuracy: {test_acc:.4f}\nBalanced Accuracy: {bal_acc:.4f}\n\n{report}")

    print(f"\nArtifacts successfully saved to: {CNN_OUT_DIR}")


if __name__ == "__main__":
    main()