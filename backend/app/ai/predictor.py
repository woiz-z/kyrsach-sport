"""ML model training and prediction using scikit-learn."""
import os
import glob
import random
import numpy as np
import joblib
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

MODELS_DIR = os.path.join(os.path.dirname(__file__), "trained_models")
os.makedirs(MODELS_DIR, exist_ok=True)
MODEL_CACHE: dict[str, Pipeline] = {}

LABEL_MAP = {0: "home_win", 1: "draw", 2: "away_win"}
ALGORITHMS = {
    "logistic_regression": LogisticRegression(max_iter=1000, multi_class="multinomial", random_state=42),
    "random_forest": RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42),
    "gradient_boosting": GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42),
}

ALGORITHM_META = {
    "logistic_regression": {
        "display_name": "Логістична регресія",
        "description": "Простий та інтерпретований лінійний класифікатор. Добре підходить для базових прогнозів і швидко навчається.",
    },
    "random_forest": {
        "display_name": "Випадковий ліс",
        "description": "Ансамблевий метод на основі дерев рішень. Стійкий до перенавчання та добре обробляє нелінійні залежності.",
    },
    "gradient_boosting": {
        "display_name": "Градієнтний бустинг",
        "description": "Потужний ансамблевий алгоритм з найвищою точністю. Навчається послідовно, виправляючи помилки попередніх дерев.",
    },
}


def _set_global_seed(seed: int) -> None:
    """Set deterministic seed for reproducible training runs."""
    random.seed(seed)
    np.random.seed(seed)


def _build_estimator(algorithm: str, random_state: int):
    """Build a fresh estimator instance to avoid state leakage between runs."""
    if algorithm == "logistic_regression":
        return LogisticRegression(max_iter=1000, multi_class="multinomial", random_state=random_state)
    if algorithm == "random_forest":
        return RandomForestClassifier(n_estimators=100, max_depth=10, random_state=random_state)
    if algorithm == "gradient_boosting":
        return GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=random_state)
    return None


def _time_split_index(n_samples: int, train_ratio: float = 0.8) -> int:
    """Get split index for chronological train/validation split."""
    idx = int(n_samples * train_ratio)
    return max(1, min(idx, n_samples - 1))


def _safe_timeseries_cv_score(pipeline: Pipeline, X: np.ndarray, y: np.ndarray) -> tuple[float | None, float | None, int]:
    """Run TimeSeriesSplit CV when enough samples are available."""
    if len(X) < 6:
        return None, None, 0

    n_splits = min(5, len(X) - 1)
    if n_splits < 2:
        return None, None, 0

    tscv = TimeSeriesSplit(n_splits=n_splits)
    cv_scores = cross_val_score(pipeline, X, y, cv=tscv, scoring="accuracy")
    return round(float(cv_scores.mean()), 4), round(float(cv_scores.std()), 4), n_splits


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4),
    }


def _build_pipeline(algorithm: str, random_state: int) -> Pipeline:
    clf = _build_estimator(algorithm, random_state=random_state)
    if clf is None:
        raise ValueError(f"Невідомий алгоритм: {algorithm}")
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", clf),
    ])


def rolling_backtest(
    X: np.ndarray,
    y: np.ndarray,
    algorithm: str,
    seed: int = 42,
    min_train_size: int = 20,
    test_size: int = 5,
) -> dict:
    """Evaluate model via rolling time windows to mimic real future predictions."""
    if len(X) < (min_train_size + test_size):
        raise ValueError(
            f"Недостатньо даних для rolling backtest: потрібно >= {min_train_size + test_size}, отримано {len(X)}"
        )

    _set_global_seed(seed)

    windows = []
    i = min_train_size
    while i + test_size <= len(X):
        X_train, y_train = X[:i], y[:i]
        X_test, y_test = X[i:i + test_size], y[i:i + test_size]

        pipeline = _build_pipeline(algorithm, random_state=seed)
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)

        metrics = _compute_metrics(y_test, y_pred)
        windows.append({
            "train_end_idx": i - 1,
            "test_start_idx": i,
            "test_end_idx": i + test_size - 1,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            **metrics,
        })
        i += test_size

    if not windows:
        raise ValueError("Не вдалося сформувати жодне backtest-вікно")

    summary = {
        "accuracy": round(float(np.mean([w["accuracy"] for w in windows])), 4),
        "precision": round(float(np.mean([w["precision"] for w in windows])), 4),
        "recall": round(float(np.mean([w["recall"] for w in windows])), 4),
        "f1": round(float(np.mean([w["f1"] for w in windows])), 4),
        "accuracy_std": round(float(np.std([w["accuracy"] for w in windows])), 4),
        "f1_std": round(float(np.std([w["f1"] for w in windows])), 4),
        "windows": len(windows),
        "test_size": test_size,
        "min_train_size": min_train_size,
    }

    return {
        "summary": summary,
        "windows": windows,
    }


def run_ablation_study(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    feature_groups: dict[str, list[str]],
    algorithm: str,
    seed: int = 42,
    train_ratio: float = 0.8,
) -> dict:
    """Measure impact of feature groups by zeroing them out on validation split."""
    if len(X) < 10:
        raise ValueError("Недостатньо даних для абляції")

    if len(feature_names) != X.shape[1]:
        raise ValueError("Кількість feature_names не збігається з кількістю колонок X")

    _set_global_seed(seed)

    split_idx = _time_split_index(len(X), train_ratio=train_ratio)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    base_pipeline = _build_pipeline(algorithm, random_state=seed)
    base_pipeline.fit(X_train, y_train)
    base_pred = base_pipeline.predict(X_val)
    baseline = _compute_metrics(y_val, base_pred)

    name_to_idx = {name: idx for idx, name in enumerate(feature_names)}
    groups = []
    for group_name, names in feature_groups.items():
        idxs = [name_to_idx[n] for n in names if n in name_to_idx]
        if not idxs:
            continue

        X_train_ab = X_train.copy()
        X_val_ab = X_val.copy()
        X_train_ab[:, idxs] = 0.0
        X_val_ab[:, idxs] = 0.0

        model = _build_pipeline(algorithm, random_state=seed)
        model.fit(X_train_ab, y_train)
        pred = model.predict(X_val_ab)
        m = _compute_metrics(y_val, pred)

        groups.append({
            "group": group_name,
            "features": names,
            "size": len(idxs),
            "accuracy": m["accuracy"],
            "f1": m["f1"],
            "delta_accuracy": round(m["accuracy"] - baseline["accuracy"], 4),
            "delta_f1": round(m["f1"] - baseline["f1"], 4),
        })

    groups.sort(key=lambda g: g["delta_f1"])
    return {
        "baseline": baseline,
        "groups": groups,
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "train_ratio": round(float(train_ratio), 4),
    }


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    algorithm: str = "gradient_boosting",
    seed: int = 42,
    train_ratio: float = 0.8,
    model_key: str | None = None,
) -> dict:
    """Train a model and return metrics + save to disk."""
    if len(X) < 10:
        raise ValueError("Недостатньо даних для тренування (потрібно щонайменше 10 матчів)")

    _set_global_seed(seed)

    pipeline = _build_pipeline(algorithm, random_state=seed)

    # Chronological split for an honest offline estimate on future-like matches.
    split_idx = _time_split_index(len(X), train_ratio=train_ratio)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    pipeline.fit(X_train, y_train)

    y_train_pred = pipeline.predict(X_train)
    y_val_pred = pipeline.predict(X_val)

    train_metrics = _compute_metrics(y_train, y_train_pred)
    val_metrics = _compute_metrics(y_val, y_val_pred)

    cv_accuracy, cv_std, cv_folds = _safe_timeseries_cv_score(pipeline, X, y)

    # Refit final model on full data before saving for inference.
    pipeline.fit(X, y)

    # Full-data metrics are kept for compatibility and overfit diagnostics.
    y_pred = pipeline.predict(X)
    full_metrics = _compute_metrics(y, y_pred)

    resolved_model_key = (model_key or algorithm).strip()
    # Save model with a stable key so different sports do not overwrite each other.
    model_path = os.path.join(MODELS_DIR, f"{resolved_model_key}.joblib")
    joblib.dump(pipeline, model_path)

    return {
        "model_key": resolved_model_key,
        "algorithm": algorithm,
        "accuracy": full_metrics["accuracy"],
        "precision": full_metrics["precision"],
        "recall": full_metrics["recall"],
        "f1": full_metrics["f1"],
        "train_accuracy": train_metrics["accuracy"],
        "train_precision": train_metrics["precision"],
        "train_recall": train_metrics["recall"],
        "train_f1": train_metrics["f1"],
        "val_accuracy": val_metrics["accuracy"],
        "val_precision": val_metrics["precision"],
        "val_recall": val_metrics["recall"],
        "val_f1": val_metrics["f1"],
        "cv_accuracy": cv_accuracy,
        "cv_std": cv_std,
        "cv_folds": cv_folds,
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "train_ratio": round(float(train_ratio), 4),
        "seed": seed,
        "trained_at": datetime.utcnow(),
        "samples": len(X),
    }


def _load_model_cached(model_key: str):
    if model_key in MODEL_CACHE:
        return MODEL_CACHE[model_key]

    model_path = os.path.join(MODELS_DIR, f"{model_key}.joblib")
    if not os.path.exists(model_path):
        return None

    pipeline = joblib.load(model_path)
    MODEL_CACHE[model_key] = pipeline
    return pipeline


def predict(
    features: np.ndarray,
    algorithm: str = "gradient_boosting",
    allows_draw: bool = True,
    model_key: str | None = None,
) -> dict:
    """Load saved model and predict probabilities."""
    resolved_model_key = (model_key or algorithm).strip()
    pipeline = _load_model_cached(resolved_model_key)
    if pipeline is None and resolved_model_key != algorithm:
        pipeline = _load_model_cached(algorithm)
    if pipeline is None:
        # Fallback: simple heuristic
        return _heuristic_predict(features, allows_draw=allows_draw)

    proba = pipeline.predict_proba(features)[0]

    # Map probabilities to labels
    classes = pipeline.classes_
    result = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
    for i, cls in enumerate(classes):
        if cls in LABEL_MAP:
            result[LABEL_MAP[cls]] = round(float(proba[i]), 4)

    predicted = LABEL_MAP[classes[np.argmax(proba)]]
    confidence = round(float(np.max(proba)), 4)

    output = {
        "home_win_prob": result["home_win"],
        "draw_prob": result["draw"],
        "away_win_prob": result["away_win"],
        "predicted_result": predicted,
        "confidence": confidence,
        "model_name": resolved_model_key,
    }

    if not allows_draw:
        home = output["home_win_prob"]
        away = output["away_win_prob"]
        denom = max(home + away, 1e-9)
        output["home_win_prob"] = round(home / denom, 4)
        output["away_win_prob"] = round(away / denom, 4)
        output["draw_prob"] = 0.0
        output["predicted_result"] = "home_win" if output["home_win_prob"] >= output["away_win_prob"] else "away_win"
        output["confidence"] = round(max(output["home_win_prob"], output["away_win_prob"]), 4)

    return output


def _heuristic_predict(features: np.ndarray, allows_draw: bool = True) -> dict:
    """Heuristic fallback when no trained model is available.

    Feature indices follow FEATURE_NAMES order in feature_extractor.py (23 total):
      2: points_diff, 13: home_ppg, 14: away_ppg
    """
    f = features[0]
    home_ppg = float(f[13]) if len(f) > 13 else 1.2
    away_ppg = float(f[14]) if len(f) > 14 else 1.0
    points_diff = float(f[2]) if len(f) > 2 else 0.0

    # Home advantage baseline: ~46% win rate historically
    home_base, away_base, draw_base = 0.46, 0.27, 0.27

    ppg_total = home_ppg + away_ppg
    if ppg_total > 0:
        ppg_shift = (home_ppg / ppg_total - 0.5) * 0.3
    else:
        ppg_shift = 0.0

    points_shift = float(np.clip(points_diff * 0.01, -0.15, 0.15))
    total_shift = ppg_shift + points_shift

    home_win = max(0.1, min(0.8, home_base + total_shift))
    away_win = max(0.1, min(0.8, away_base - total_shift))
    draw_prob = max(0.05, 1.0 - home_win - away_win)

    # Normalise to sum to 1.0
    s = home_win + away_win + draw_prob
    probs = {
        "home_win": round(home_win / s, 4),
        "draw":     round(draw_prob / s, 4),
        "away_win": round(away_win / s, 4),
    }

    if not allows_draw:
        denom = max(probs["home_win"] + probs["away_win"], 1e-9)
        probs["home_win"] = round(probs["home_win"] / denom, 4)
        probs["away_win"] = round(probs["away_win"] / denom, 4)
        probs["draw"] = 0.0

    predicted = max(probs, key=probs.get)

    return {
        "home_win_prob": probs["home_win"],
        "draw_prob": probs["draw"],
        "away_win_prob": probs["away_win"],
        "predicted_result": predicted,
        "confidence": round(max(probs.values()), 4),
        "model_name": "heuristic_fallback",
    }


def get_available_models() -> list:
    """Return list of available algorithms with metadata."""
    models = []
    for algo in ALGORITHMS:
        base_path = os.path.join(MODELS_DIR, f"{algo}.joblib")
        sport_specific = glob.glob(os.path.join(MODELS_DIR, f"{algo}_sport_*.joblib"))
        exists = os.path.exists(base_path) or bool(sport_specific)
        meta = ALGORITHM_META.get(algo, {})
        models.append({
            "name": algo,
            "algorithm": algo,
            "display_name": meta.get("display_name", algo),
            "description": meta.get("description", ""),
            "trained": exists,
            "path": base_path if os.path.exists(base_path) else (sport_specific[0] if sport_specific else None),
        })
    return models
