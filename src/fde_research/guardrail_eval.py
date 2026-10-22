from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline

from . import config
from .util import utc_now, write_json

RULES = [
    r"ignore (all )?(previous|prior|above) (instructions|prompts)",
    r"disregard (all )?(previous|prior|above)",
    r"forget (all )?(previous|prior|your) (instructions|prompts)",
    r"reveal (your )?(system prompt|instructions)",
    r"print (your )?(system prompt|instructions)",
    r"repeat (the text|everything) above",
    r"you are now",
    r"act as (a |an )?(dan|jailbreak|unrestricted)",
    r"developer mode",
    r"do anything now",
    r"jailbreak",
    r"bypass (the )?(safety|guardrails|filters)",
    r"system prompt",
    r"override (the )?(instructions|rules)",
]


def download() -> Path:
    cfg = config.study()["guardrail"]
    target = config.RAW_DIR / "deepset_prompt_injections.parquet"
    if target.exists() and target.stat().st_size > 1000:
        return target
    config.ensure_dirs()
    response = requests.get(cfg["parquet_url"], timeout=120)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def rule_score(text: str) -> int:
    return int(any(re.search(pattern, str(text), re.I) for pattern in RULES))


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
    }


def build_model() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=50000, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=3000, class_weight="balanced", random_state=20261022)),
        ]
    )


def main() -> None:
    config.ensure_dirs()
    path = download()
    frame = pd.read_parquet(path)
    text_column = "text" if "text" in frame.columns else frame.columns[0]
    label_column = "label" if "label" in frame.columns else frame.columns[-1]
    frame = frame[[text_column, label_column]].dropna()
    frame.columns = ["text", "label"]
    frame["label"] = frame["label"].astype(int)
    frame["rule_pred"] = frame["text"].apply(rule_score)

    cfg = config.study()["guardrail"]
    train, test = train_test_split(
        frame, test_size=float(cfg["test_size"]), random_state=int(cfg["seed"]), stratify=frame["label"]
    )

    rule_metrics = metrics(test["label"].to_numpy(), test["rule_pred"].to_numpy())

    model = build_model()
    cv = StratifiedKFold(n_splits=int(cfg["cv_folds"]), shuffle=True, random_state=int(cfg["seed"]))
    cv_probs = cross_val_predict(model, train["text"], train["label"], cv=cv, method="predict_proba")[:, 1]
    thresholds = np.unique(np.round(cv_probs, 4))
    best_threshold = 0.5
    best_precision = -1.0
    for threshold in thresholds:
        predicted = (cv_probs >= threshold).astype(int)
        recall = recall_score(train["label"], predicted, zero_division=0)
        precision = precision_score(train["label"], predicted, zero_division=0)
        if recall >= float(cfg["recall_target"]) and precision > best_precision:
            best_precision = precision
            best_threshold = float(threshold)

    model.fit(train["text"], train["label"])
    probs = model.predict_proba(test["text"])[:, 1]
    model_metrics = metrics(test["label"].to_numpy(), (probs >= best_threshold).astype(int))
    model_metrics_default = metrics(test["label"].to_numpy(), (probs >= 0.5).astype(int))

    false_positives = test[(test["label"] == 0) & (probs >= best_threshold)][["text"]].head(10).to_dict(orient="records")
    false_negatives = test[(test["label"] == 1) & (probs < best_threshold)][["text"]].head(10).to_dict(orient="records")

    payload = {
        "generated_at": utc_now(),
        "dataset": cfg["dataset"],
        "dataset_sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        "n_total": int(len(frame)),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "label_balance": frame["label"].value_counts().to_dict(),
        "rules": {"patterns": RULES, "test": rule_metrics},
        "classifier": {
            "model": "tfidf(1,2)+logistic_regression(balanced)",
            "selected_threshold": best_threshold,
            "recall_target": float(cfg["recall_target"]),
            "test_at_selected_threshold": model_metrics,
            "test_at_0_5": model_metrics_default,
        },
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }
    write_json(config.RESULTS_DIR / "guardrail_eval.json", payload)
    print(json.dumps(payload, indent=2)[:4000])


if __name__ == "__main__":
    main()
