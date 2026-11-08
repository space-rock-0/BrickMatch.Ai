"""Transparent hybrid scoring with deterministic diversity and exclusions."""
import math


def rank_candidates(candidates, catalog, rated_ids=(), k=10, weights=None, theme_cap=None):
    if not 1 <= k <= 100:
        raise ValueError("k must be between 1 and 100")
    weights = weights or {"preference": .5, "visual": .3, "metadata": .2}
    if any(not math.isfinite(v) or v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Invalid ranking weights")
    if theme_cap is not None and theme_cap < 1:
        raise ValueError("Invalid theme cap")
    blocked = set(rated_ids)
    ranked = {}
    for item in candidates:
        set_id = item["set_id"]
        if set_id in blocked or set_id not in catalog:
            continue
        signals = item["signals"]
        if any(not math.isfinite(value) for value in signals.values()):
            raise ValueError("Nonfinite ranking signal")
        active = {name: weight for name, weight in weights.items() if name in signals}
        total = sum(active.values())
        score = sum(signals[name] * weight for name, weight in active.items()) / total if total else 0.
        explanations = [f"{name.replace('_', ' ').capitalize()} signal: {signals[name]:.3f}"
                        for name in sorted(active)] or ["Catalog order fallback; no preference evidence yet"]
        row = {"set_id": set_id, "score": score, "signals": dict(signals),
               "explanations": explanations}
        if set_id not in ranked or score > ranked[set_id]["score"]:
            ranked[set_id] = row
    selected, counts = [], {}
    for item in sorted(ranked.values(), key=lambda row: (-row["score"], row["set_id"])):
        theme = catalog[item["set_id"]]["theme_id"]
        if theme_cap is not None and counts.get(theme, 0) >= theme_cap:
            continue
        selected.append(item)
        counts[theme] = counts.get(theme, 0) + 1
        if len(selected) == k:
            break
    return selected
