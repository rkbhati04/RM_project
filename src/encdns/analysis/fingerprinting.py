"""Leakage-safe, repeat-held-out domain fingerprinting evaluation."""
from __future__ import annotations
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from .stats import empirical_p_value, wilson_interval

FEATURE_GROUPS = {"volume": ["n_pkts", "n_up", "n_down", "bytes_up", "bytes_down", "bytes_total", "ratio_bytes_down_up"], "size_stats": ["up_mean", "up_std", "up_max", "down_mean", "down_std", "down_max"], "timing": ["duration", "iat_mean", "iat_std", "iat_median", "iat_max", "t_first_down"], "bursts": ["n_bursts", "burst_len_mean", "burst_len_max", "burst_bytes_mean", "burst_bytes_max"], "handshake": [f"pkt_{index:02d}" for index in range(20)]}

def available_features(frame: pd.DataFrame) -> list[str]:
    return [column for group in FEATURE_GROUPS.values() for column in group if column in frame.columns]

def select_headline_repeats(
    frame: pd.DataFrame, repeat_start: int, repeat_end: int, target_k: int
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Select headline repeats and retain domains meeting the successful-repeat target."""
    selected = frame[frame["repeat"].between(repeat_start, repeat_end)].copy()
    counts = selected.groupby("domain")["repeat"].nunique()
    dropped = {
        str(domain): f"{int(count)} successful repeats; required {target_k}"
        for domain, count in counts.items()
        if count < target_k
    }
    kept = set(counts[counts >= target_k].index)
    selected = selected[selected["domain"].isin(kept)].copy()
    sampled = [
        group.sample(n=target_k, random_state=17)
        for _, group in selected.groupby("domain", sort=False)
    ]
    if not sampled:
        return selected.iloc[0:0].reset_index(drop=True), dropped
    return pd.concat(sampled, ignore_index=True), dropped

def _evaluate(frame: pd.DataFrame, features: list[str], seed: int, estimators: int, permute: bool = False) -> dict[str, float] | None:
    clean = frame.dropna(subset=features + ["domain", "repeat"]).copy()
    if clean.domain.nunique() < 2 or clean.repeat.nunique() < 2:
        return None
    actual, predicted, top_five = [], [], 0
    rng = np.random.default_rng(seed)
    repeats = sorted(clean.repeat.unique())
    folds = [repeats[index:index + 2] for index in range(0, len(repeats), 2)]
    for held_out in folds:
        train, test = clean[~clean.repeat.isin(held_out)], clean[clean.repeat.isin(held_out)]
        labels = train.domain.to_numpy()
        if permute:
            labels = rng.permutation(labels)
        known = test.domain.isin(set(labels))
        if not known.any():
            continue
        model = RandomForestClassifier(n_estimators=estimators, class_weight="balanced_subsample", n_jobs=1, random_state=seed + int(held_out[0]))
        model.fit(train[features].to_numpy(float), labels)
        test_x, test_y = test.loc[known, features].to_numpy(float), test.loc[known, "domain"].to_numpy()
        probabilities = model.predict_proba(test_x)
        predictions = model.classes_[probabilities.argmax(axis=1)]
        positions = np.argsort(probabilities, axis=1)[:, -min(5, len(model.classes_)):]
        top_five += sum(test_y[index] in model.classes_[positions[index]] for index in range(len(test_y)))
        actual.extend(test_y); predicted.extend(predictions)
    if not actual:
        return None
    accuracy = accuracy_score(actual, predicted)
    lower, upper = wilson_interval(sum(a == b for a, b in zip(actual, predicted)), len(actual))
    return {"accuracy": accuracy, "ci_low": lower, "ci_high": upper, "top5": top_five / len(actual), "macro_f1": f1_score(actual, predicted, average="macro"), "n_test": len(actual)}

def evaluate(
    frame: pd.DataFrame,
    seeds: list[int],
    permutations: int,
    estimators: int,
    features: list[str] | None = None,
    repeat_start: int = 8,
    repeat_end: int = 19,
    target_k: int = 10,
    workers: int = 1,
) -> dict[str, float] | None:
    features = features or available_features(frame)
    frame = frame.copy()
    frame["repeat"] = pd.to_numeric(frame["repeat"], errors="coerce")
    frame, dropped = select_headline_repeats(frame, repeat_start, repeat_end, target_k)
    repeats_per_domain = target_k
    if frame.empty:
        return None
    observed = Parallel(n_jobs=workers, backend="loky")(
        delayed(_evaluate)(frame, features, seed, 100) for seed in seeds
    )
    observed = [result for result in observed if result is not None]
    if not observed:
        return None
    mean_accuracy = float(np.mean([result["accuracy"] for result in observed]))
    # The null uses one designated seed and is shared across all reported seeds.
    null_results = Parallel(n_jobs=workers, backend="loky")(
        delayed(_evaluate)(frame, features, seeds[0] + 10000 + index, 50, True)
        for index in range(permutations)
    )
    null = [result["accuracy"] for result in null_results if result is not None]
    reference = observed[0]
    return {
        "n": int(len(frame)), "domains": int(frame.domain.nunique()),
        "repeats_per_domain": repeats_per_domain, "accuracy": mean_accuracy,
        "accuracy_seed_sd": float(np.std([result["accuracy"] for result in observed])),
        "ci_low": float(reference["ci_low"]), "ci_high": float(reference["ci_high"]),
        "top5": float(np.mean([result["top5"] for result in observed])),
        "macro_f1": float(np.mean([result["macro_f1"] for result in observed])),
        "chance": 1 / frame.domain.nunique(), "p_value": empirical_p_value(mean_accuracy, null),
        "n_permutations": len(null), "dropped_domains": "; ".join(
            f"{domain} ({reason})" for domain, reason in sorted(dropped.items())
        ),
    }
