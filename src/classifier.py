"""
classifier.py

Milestone 3: Random Forest training and evaluation ONLY.

No DSP filtering happens here or anywhere in Milestone 3 — the classifier
is trained directly on hand-crafted features of the raw noisy windows.
"""

import os

import numpy as np
import matplotlib.pyplot as plt
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


def split_dataset(X, y, test_size=0.3, random_state=42):
    """
    Stratified train/test split (stratified so each noise class is
    represented proportionally in both sets).
    """
    return train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )


def train_random_forest(X_train, y_train, n_estimators=100, random_state=42):
    """
    Train a RandomForestClassifier on the given feature matrix/labels.
    """
    model = RandomForestClassifier(
        n_estimators=n_estimators, random_state=random_state
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test):
    """
    Evaluate a trained model on held-out data.

    Returns a dict with: accuracy, report (str), confusion_matrix (ndarray),
    labels (sorted class list matching the confusion matrix axes), y_pred.
    """
    y_pred = model.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, zero_division=0)
    labels = sorted(np.unique(y_test))
    cm = confusion_matrix(y_test, y_pred, labels=labels)

    return {
        "accuracy": accuracy,
        "report": report,
        "confusion_matrix": cm,
        "labels": labels,
        "y_pred": y_pred,
    }


def save_model(model, path):
    """
    Save a trained model to disk with joblib, creating parent directories
    as needed.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    joblib.dump(model, path)


def plot_confusion_matrix(cm, labels, output_path=None):
    """
    Render a confusion matrix as an annotated heatmap. If output_path is
    given, save the figure there (parent directories created as needed).
    Returns the matplotlib Figure.
    """
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, cmap="Blues")

    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title("Confusion Matrix")

    threshold = cm.max() / 2 if cm.size else 0
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(
                j, i, str(cm[i, j]),
                ha="center", va="center",
                color="white" if cm[i, j] > threshold else "black",
            )

    fig.colorbar(im, ax=ax)
    fig.tight_layout()

    if output_path:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fig.savefig(output_path)

    return fig


def plot_feature_importance(model, feature_names, output_path=None):
    """
    Bar chart of Random Forest feature importances, sorted descending.
    If output_path is given, save the figure there. Returns the Figure.
    """
    importances = model.feature_importances_
    order = np.argsort(importances)[::-1]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(range(len(importances)), importances[order])
    ax.set_xticks(range(len(importances)))
    ax.set_xticklabels([feature_names[i] for i in order], rotation=45, ha="right")
    ax.set_ylabel("Importance")
    ax.set_title("Random Forest Feature Importance")
    fig.tight_layout()

    if output_path:
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fig.savefig(output_path)

    return fig
