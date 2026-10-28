
"""
cnn_pipeline.py
Converts 1D ECG windows to 2D Spectrograms and formats them for ResNet-50.
"""
import numpy as np
import tensorflow as tf
from scipy.signal import spectrogram
from tensorflow.keras.applications.resnet50 import preprocess_input as resnet_preprocess
from sklearn.preprocessing import LabelEncoder

def signal_to_spectrogram_images(X_raw, fs=360, img_size=(128, 128)):
    """
    Converts 1D ECG windows into 3-channel 2D Spectrogram images 
    sized and normalized for ResNet-50 input.
    """
    print(f"Converting {len(X_raw)} signals to {img_size} spectrograms...")
    images = []
    for sig in X_raw:
        # 1. Short-Time Fourier Transform (Spectrogram)
        f, t, Sxx = spectrogram(sig, fs=fs, nperseg=64, noverlap=48)
        
        # 2. Convert power to logarithmic dB scale
        Sxx_log = 10 * np.log10(Sxx + 1e-10)
        
        # 3. Min-Max normalization to [0, 255]
        Sxx_norm = (Sxx_log - Sxx_log.min()) / (Sxx_log.max() - Sxx_log.min() + 1e-8)
        Sxx_norm = Sxx_norm * 255.0
        
        # 4. Replicate grayscale image across 3 channels (RGB)
        img_3c = np.stack([Sxx_norm, Sxx_norm, Sxx_norm], axis=-1)
        
        # 5. Resize to input dimensions
        img_resized = tf.image.resize(img_3c, img_size).numpy()
        images.append(img_resized)
        
    return resnet_preprocess(np.array(images))

def encode_labels(y_train, y_test):
    """Encodes string labels ('BW', 'MA', 'PLI') into numerical indices."""
    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)
    y_test_enc = le.transform(y_test)
    return y_train_enc, y_test_enc, le.classes_