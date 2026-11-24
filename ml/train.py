"""Train the small frost-risk classifier (float model).

Run from the repository root, after ml/prepare_dataset.py:
    python ml/train.py

Output in ml/models/ (N = dataset_version):
    model_vN.keras               float model
    model_vN_preprocessing.json  input names, mean and std (needed later by
                                 convert_tflite.py and by the firmware)
    metrics_vN_float.json        F1, confusion matrix, precision and recall

Design decisions:
- Inputs are standardized (subtract mean, divide by std) with statistics
  computed on the TRAIN split only, so nothing leaks from val or test.
- Class imbalance is handled with class weights (see class_weights below).
- The validation split chooses when to stop training (early stopping).
  The test split is evaluated once, at the end, and is never used to choose
  anything.
"""

import argparse
import json

import numpy as np
from sklearn.metrics import (confusion_matrix, f1_score,
                             precision_recall_fscore_support)
from sklearn.utils.class_weight import compute_class_weight
from tensorflow import keras

from dataset_utils import (DEFAULT_CONFIG, feature_columns, load_config,
                           load_dataset, models_dir)


def build_model(n_inputs, n_classes, hidden_units):
    """Small dense network: input -> 16 -> 8 -> output (sizes from the config).

    Dense layers are the cheapest option for a microcontroller: each layer is
    one matrix multiplication, and TFLite Micro supports them in int8.
    """
    layers = [keras.Input(shape=(n_inputs,))]
    for units in hidden_units:
        layers.append(keras.layers.Dense(units, activation="relu"))
    layers.append(keras.layers.Dense(n_classes, activation="softmax"))
    return keras.Sequential(layers)


def class_weights(labels, n_classes):
    """Weight of each class, inversely proportional to how often it appears.

    Why class weights instead of resampling: frost-risk windows are a small
    minority. Weights make each mistake on a rare class cost more during
    training without copying rows (oversampling) or throwing data away
    (undersampling), and the val/test splits keep their real proportions.
    Side effect: the model predicts "risk" more often, so recall goes up and
    precision goes down, and the output probabilities are not calibrated.
    """
    present = np.unique(labels)
    weights = compute_class_weight("balanced", classes=present, y=labels)
    result = {c: 1.0 for c in range(n_classes)}
    result.update({int(c): float(w) for c, w in zip(present, weights)})
    return result


def evaluate(model, inputs, labels, n_classes):
    """Metrics of one split, as a dictionary that can be saved to JSON."""
    predicted = np.argmax(model.predict(inputs, batch_size=4096, verbose=0), axis=1)
    return metrics_from_predictions(labels, predicted, n_classes)


def metrics_from_predictions(labels, predicted, n_classes):
    classes = list(range(n_classes))
    precision, recall, f1, support = precision_recall_fscore_support(
        labels, predicted, labels=classes, zero_division=0)
    return {
        "f1_macro": float(f1_score(labels, predicted, labels=classes,
                                   average="macro", zero_division=0)),
        "per_class": {
            str(c): {"precision": float(precision[c]), "recall": float(recall[c]),
                     "f1": float(f1[c]), "support": int(support[c])}
            for c in classes},
        # rows = real class, columns = predicted class
        "confusion_matrix": confusion_matrix(labels, predicted, labels=classes).tolist(),
    }


def print_metrics(name, metrics):
    print(f"\n--- {name} ---")
    print(f"F1 macro: {metrics['f1_macro']:.4f}")
    for label, values in metrics["per_class"].items():
        # with 3 classes: 0 no risk, 1 caution, 2 risk (with 2 classes: 0 and 1)
        kind = {"0": "no risk", "1": "caution", "2": "risk"}.get(label, label)
        print(f"class {label} ({kind}): precision {values['precision']:.4f}  "
              f"recall {values['recall']:.4f}  F1 {values['f1']:.4f}  "
              f"support {values['support']}")
    print("confusion matrix (rows = real, columns = predicted):")
    for row in metrics["confusion_matrix"]:
        print("  ", row)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    config = load_config(parser.parse_args().config)
    training = config["training"]
    version = config["dataset_version"]
    n_classes = config["labeling"]["num_classes"]

    keras.utils.set_random_seed(training["seed"])  # reproducible runs

    dataset = load_dataset(config)
    columns = feature_columns(dataset)
    print(f"sources: {sorted(dataset['source'].unique())}")
    print(f"inputs: {len(columns)} "
          f"(pressure {'used' if any('pressure' in c for c in columns) else 'not used'})")

    parts = {name: dataset[dataset["split"] == name] for name in ("train", "val", "test")}
    for name, part in parts.items():
        if part.empty:
            raise SystemExit(f"ERROR: the {name} split is empty.")

    # Standardization statistics from TRAIN only
    mean = parts["train"][columns].mean().to_numpy()
    std = parts["train"][columns].std().to_numpy(copy=True)
    std[std == 0] = 1.0  # a constant column would divide by zero

    def inputs_of(part):
        return ((part[columns].to_numpy() - mean) / std).astype("float32")

    x = {name: inputs_of(part) for name, part in parts.items()}
    y = {name: part["label"].to_numpy() for name, part in parts.items()}

    if len(np.unique(y["train"])) < 2:
        raise SystemExit("ERROR: the train split has only one class. "
                         "A classifier cannot be trained.")

    model = build_model(len(columns), n_classes, training["hidden_units"])
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy")
    model.summary()

    weights = class_weights(y["train"], n_classes)
    print(f"class weights: {weights}")

    stop_early = keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=training["early_stopping_patience"],
        restore_best_weights=True)
    model.fit(x["train"], y["train"],
              validation_data=(x["val"], y["val"]),
              epochs=training["max_epochs"], batch_size=training["batch_size"],
              class_weight=weights, callbacks=[stop_early], verbose=2)

    metrics = {
        "dataset_version": version,
        "sources": sorted(dataset["source"].unique().tolist()),
        "n_inputs": len(columns),
        "n_parameters": int(model.count_params()),
        "class_weights": weights,
        "val": evaluate(model, x["val"], y["val"], n_classes),
        "test": evaluate(model, x["test"], y["test"], n_classes),
    }
    print_metrics("validation", metrics["val"])
    print_metrics("test (evaluated once, not used for any decision)", metrics["test"])

    folder = models_dir(config)
    model.save(folder / f"model_v{version}.keras")
    (folder / f"model_v{version}_preprocessing.json").write_text(json.dumps({
        "feature_columns": columns,
        "mean": mean.tolist(),
        "std": std.tolist(),
        "num_classes": n_classes,
    }, indent=2), encoding="utf-8")
    (folder / f"metrics_v{version}_float.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nsaved model and metrics in {folder}")


if __name__ == "__main__":
    main()
