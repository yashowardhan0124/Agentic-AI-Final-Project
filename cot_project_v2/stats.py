"""
Small, dependency-free statistics used by the report and the deck.

  wilson()        95% confidence interval for an accuracy (k correct of n)
  mcnemar_exact() paired test: did condition B fix more trials than it broke,
                  beyond what chance would produce?
  summarise()     every per-condition number the report/deck needs
"""

import math
from collections import Counter

from problems import PROBLEMS


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the two discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def majority_vote_correct(trials, problem) -> bool:
    """Self-consistency: most common answer across all runs (ties -> greedy)."""
    preds = [round(t["predicted"], 2) for t in trials if t["predicted"] is not None]
    if not preds:
        return False
    counts = Counter(preds).most_common()
    top = [v for v, c in counts if c == counts[0][1]]
    if len(top) > 1:
        greedy = next((t for t in trials if t["run"] == 0), None)
        if greedy and greedy["predicted"] is not None and round(greedy["predicted"], 2) in top:
            choice = round(greedy["predicted"], 2)
        else:
            choice = top[0]
    else:
        choice = top[0]
    return abs(choice - problem["answer"]) <= problem["tolerance"] + 1e-6


def summarise_condition(trials):
    n = len(trials)
    k = sum(t["correct"] for t in trials)
    runs = sorted({t["run"] for t in trials})
    per_run = [sum(t["correct"] for t in trials if t["run"] == r) /
               max(1, sum(1 for t in trials if t["run"] == r)) for r in runs]
    greedy = [t for t in trials if t["run"] == 0]
    sampled = [t for t in trials if t["run"] > 0]
    per_problem = {}
    mv = 0
    for p in PROBLEMS:
        pt = [t for t in trials if t["problem_id"] == p["id"]]
        per_problem[p["id"]] = {
            "correct": sum(t["correct"] for t in pt),
            "runs": len(pt),
            "greedy_correct": next((t["correct"] for t in pt if t["run"] == 0), None),
            "greedy_pred": next((t["predicted"] for t in pt if t["run"] == 0), None),
        }
        mv += majority_vote_correct(pt, p)
    lo, hi = wilson(k, n)
    v1 = [t for t in trials if t["problem_id"] in {p["id"] for p in PROBLEMS if p["origin"] == "v1"}]
    v2 = [t for t in trials if t not in v1]
    return {
        "trials": n,
        "correct": k,
        "accuracy": k / n if n else 0,
        "ci95": [lo, hi],
        "greedy_correct": sum(t["correct"] for t in greedy),
        "greedy_n": len(greedy),
        "sampled_accuracy": (sum(t["correct"] for t in sampled) / len(sampled)) if sampled else None,
        "per_run_accuracy": per_run,
        "per_run_mean": _mean(per_run),
        "per_run_sd": _sd(per_run),
        "majority_vote_correct": mv,
        "v1_accuracy": sum(t["correct"] for t in v1) / len(v1) if v1 else None,
        "v2_accuracy": sum(t["correct"] for t in v2) / len(v2) if v2 else None,
        "mean_output_tokens": _mean([t["output_tokens"] for t in trials]),
        "mean_latency_s": _mean([t["latency_s"] for t in trials]),
        "extraction_fallbacks": sum(t["extraction_method"] != "final_answer_line" for t in trials),
        "per_problem": per_problem,
    }


def paired(a_trials, b_trials):
    """Discordant counts between two conditions over matched (problem, run)."""
    a = {(t["problem_id"], t["run"]): t["correct"] for t in a_trials}
    b_only = a_only = 0
    for t in b_trials:
        key = (t["problem_id"], t["run"])
        if key not in a:
            continue
        if t["correct"] and not a[key]:
            b_only += 1
        elif a[key] and not t["correct"]:
            a_only += 1
    return {"b_right_a_wrong": b_only, "a_right_b_wrong": a_only,
            "p_value": mcnemar_exact(b_only, a_only)}
