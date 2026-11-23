"""
Step 4 -- root-cause analysis of every wrong answer.

Each failed trial is put into exactly one category, checked in this order:

  no_answer         no number could be extracted (format failure)
  trap              the answer equals a known trap value from problems.py,
                    so we know WHICH misreading happened (e.g. "fence-post
                    error: counted 15 posts instead of 16")
  stopped_early     the answer equals one of the correct INTERMEDIATE values,
                    i.e. the model answered a sub-question
  arithmetic_slip   (reasoning shown) a written equation is wrong, e.g.
                    "275 / 24 = 12.46"; we show the exact line
  answer_selection  (reasoning shown) the correct value appears in the
                    reasoning but a different number was reported
  wrong_step        (reasoning shown) the first ground-truth step whose value
                    never appears in the trace -> where the chain broke
  unexplained       (no reasoning shown) wrong, and matches nothing known
  other             anything left over

For reasoning conditions we also mark, step by step, which ground-truth
intermediate values appear in the trace, and find the first line that
introduces a number that is not on the correct path ("first divergent
line"). These are heuristics: they point you to the right line of the log,
which you then confirm by reading it.

Usage:
    python error_analysis.py         (after run_experiment.py / prompt_fix.py)
    python error_analysis.py --mock
"""

import itertools
import json
import os
from collections import Counter

import config
from grading import arithmetic_slips, close, normalise, numbers_in
from problems import PROBLEMS, PROBLEMS_BY_ID
from runner import load_all

CATEGORIES = {
    "trap": "Fell into a known trap",
    "stopped_early": "Answered a sub-question",
    "arithmetic_slip": "Arithmetic slip",
    "wrong_step": "Wrong / missing step",
    "answer_selection": "Right value, wrong one reported",
    "no_answer": "No parseable answer",
    "unexplained": "Unexplained guess (no work shown)",
    "other": "Other",
}


def step_trace(raw_output: str, problem: dict):
    seen = numbers_in(raw_output)
    rows = []
    for label, value in problem["steps"]:
        found = any(close(s, value, rel=0.001, abs_tol=0.011) for s in seen)
        rows.append({"label": label, "value": value, "found": found})
    first_missing = next((i for i, r in enumerate(rows) if not r["found"]), None)
    return rows, first_missing


def _allowed_numbers(problem: dict):
    base = set(numbers_in(problem["question"]))
    base |= {v for _, v in problem["steps"]}
    base |= {problem["answer"]}
    base |= {b / 100 for b in list(base)}            # 10% -> 0.10
    base |= {1 - b / 100 for b in list(base) if b < 100}  # 30% off -> 0.70
    base |= {1 + b / 100 for b in list(base) if b < 100}  # 25% up -> 1.25
    derived = set()
    for a, b in itertools.product(list(base), repeat=2):
        derived.add(a * b)
        if b:
            derived.add(a / b)
    return base | derived


def first_divergent_line(raw_output: str, problem: dict):
    """First line that introduces a number which is not on the correct path."""
    allowed = _allowed_numbers(problem)
    for line in normalise(raw_output).splitlines():
        for v in numbers_in(line):
            if abs(v) <= 12 and float(v).is_integer():
                continue  # step numbers, list markers, small counts
            if not any(close(v, a, rel=0.002, abs_tol=0.011) for a in allowed):
                return line.strip(), v
    return None, None


def classify(trial: dict, problem: dict) -> dict:
    pred = trial["predicted"]
    raw = trial["raw_output"]
    reasoning = trial["condition"] != "standard"
    out = {"category": "other", "detail": "", "breakdown_step": None,
           "evidence_line": None}

    if reasoning:
        trace, first_missing = step_trace(raw, problem)
        out["step_trace"] = trace
        line, value = first_divergent_line(raw, problem)
        out["evidence_line"] = line

    if pred is None:
        out.update(category="no_answer", detail="no number could be extracted")
        return out
    for trap_value, why in problem["traps"].items():
        if close(pred, trap_value, rel=0.001, abs_tol=0.011):
            out.update(category="trap", detail=why)
            return out
    for i, (label, value) in enumerate(problem["steps"][:-1]):
        if close(pred, value, rel=0.001, abs_tol=0.011):
            out.update(category="stopped_early",
                       detail=f"reported step {i + 1} ({label} = {value}) as the answer",
                       breakdown_step=i + 1)
            return out
    if not reasoning:
        out.update(category="unexplained",
                   detail=f"answered {pred:g} with no work shown; matches no known mistake")
        return out

    slips = arithmetic_slips(raw)
    if slips:
        s = slips[0]
        out.update(category="arithmetic_slip",
                   detail=f"wrote {s['expression']} = {s['written']:g} "
                          f"(correct: {s['correct']:g})",
                   evidence_line=s["line"], slips=slips)
        return out
    if any(close(v, problem["answer"], rel=0.001, abs_tol=0.011) for v in numbers_in(raw)):
        out.update(category="answer_selection",
                   detail=f"the correct value {problem['answer']:g} appears in the "
                          f"reasoning, but {pred:g} was reported")
        return out
    if first_missing is not None:
        label = problem["steps"][first_missing][0]
        value = problem["steps"][first_missing][1]
        out.update(category="wrong_step",
                   detail=f"chain breaks at step {first_missing + 1}/{len(problem['steps'])}: "
                          f"'{label}' should be {value:g} but never appears",
                   breakdown_step=first_missing + 1)
        return out
    out.update(detail="all intermediate values appear; inspect the log manually")
    return out


def analyse(out_dir: str) -> dict:
    results = load_all(out_dir)
    if not results:
        raise SystemExit("No results found. Run run_experiment.py first.")
    failures = {c: [] for c in results}
    counts = {}
    for cond, trials in results.items():
        for t in trials:
            if t["correct"]:
                continue
            info = classify(t, PROBLEMS_BY_ID[t["problem_id"]])
            failures[cond].append({
                "problem_id": t["problem_id"], "run": t["run"],
                "predicted": t["predicted"], "expected": t["expected"],
                "log_file": t["log_file"], **info,
            })
        counts[cond] = dict(Counter(f["category"] for f in failures[cond]))

    # "Hardest problem" for the jury question: lowest plain-CoT pass rate
    # (ties -> more steps). Prefer the greedy run's failure if there is one.
    showcase = None
    if "cot" in results and failures["cot"]:
        rate = {p["id"]: sum(t["correct"] for t in results["cot"] if t["problem_id"] == p["id"])
                for p in PROBLEMS}
        failed_ids = {f["problem_id"] for f in failures["cot"]}
        pid = min(failed_ids, key=lambda i: (rate[i], -len(PROBLEMS_BY_ID[i]["steps"])))
        cands = sorted([f for f in failures["cot"] if f["problem_id"] == pid],
                       key=lambda f: f["run"])
        f = cands[0]
        trial = next(t for t in results["cot"]
                     if t["problem_id"] == pid and t["run"] == f["run"])
        std = next((t for t in results.get("standard", [])
                    if t["problem_id"] == pid and t["run"] == f["run"]), None)
        fix = next((t for t in results.get("structured", [])
                    if t["problem_id"] == pid and t["run"] == f["run"]), None)
        showcase = {
            "problem_id": pid,
            "title": PROBLEMS_BY_ID[pid]["title"],
            "answer": PROBLEMS_BY_ID[pid]["answer"],
            "cot_pass": rate[pid],
            "runs": sum(1 for t in results["cot"] if t["problem_id"] == pid),
            "failure": f,
            "raw_output": trial["raw_output"],
            "standard_pred": std["predicted"] if std else None,
            "standard_correct": std["correct"] if std else None,
            "fix_pred": fix["predicted"] if fix else None,
            "fix_correct": fix["correct"] if fix else None,
            "fix_log": fix["log_file"] if fix else None,
        }

    analysis = {"counts": counts, "failures": failures, "showcase": showcase,
                "categories": CATEGORIES}
    with open(os.path.join(out_dir, "error_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, indent=2)
    with open(os.path.join(out_dir, "error_analysis.md"), "w", encoding="utf-8") as fh:
        fh.write(to_markdown(analysis, results))
    return analysis


def to_markdown(analysis, results) -> str:
    L = ["# Step 4 -- Root-cause analysis of every wrong answer", ""]
    conds = [c for c in config.CONDITIONS if c in results]
    L.append("## Failure categories")
    L.append("")
    L.append("| Category | " + " | ".join(config.CONDITION_LABELS[c] for c in conds) + " |")
    L.append("|---|" + "---|" * len(conds))
    for key, label in CATEGORIES.items():
        row = [str(analysis["counts"].get(c, {}).get(key, 0)) for c in conds]
        if any(r != "0" for r in row):
            L.append(f"| {label} | " + " | ".join(row) + " |")
    L.append("| **Total wrong** | " + " | ".join(
        str(len(analysis["failures"][c])) for c in conds) + " |")
    L.append("")

    sc = analysis["showcase"]
    if sc:
        f = sc["failure"]
        L += [f"## Hardest problem under CoT: {sc['problem_id']} "
              f"({sc['cot_pass']}/{sc['runs']} runs correct)", "",
              f"Run {f['run']}: model answered **{f['predicted']}**, correct is "
              f"**{sc['answer']}**.", "",
              f"**Diagnosis ({CATEGORIES[f['category']]}):** {f['detail']}", ""]
        if f.get("evidence_line"):
            L += [f"First line that leaves the correct path:", "",
                  f"> {f['evidence_line']}", ""]
        if f.get("step_trace"):
            L.append("| # | Ground-truth step | Value | In model's reasoning? |")
            L.append("|---|---|---|---|")
            for i, s in enumerate(f["step_trace"], 1):
                L.append(f"| {i} | {s['label']} | {s['value']:g} | "
                         f"{'yes' if s['found'] else '**NO**'} |")
            L.append("")
        L += [f"Full transcript: `{f['log_file']}`", ""]
    else:
        L += ["## No CoT failures", "",
              "Plain CoT answered every trial correctly, so there is no CoT "
              "reasoning chain to diagnose.", ""]

    for c in conds:
        fails = analysis["failures"][c]
        L += [f"## Every failure -- {config.CONDITION_LABELS[c]} ({len(fails)})", ""]
        if not fails:
            L += ["None.", ""]
            continue
        L.append("| Problem | Run | Answer | Correct | Category | Diagnosis |")
        L.append("|---|---|---|---|---|---|")
        for f in sorted(fails, key=lambda x: (x["problem_id"], x["run"])):
            L.append(f"| {f['problem_id']} | {f['run']} | {f['predicted']} | "
                     f"{f['expected']} | {CATEGORIES[f['category']]} | "
                     f"{f['detail'].replace('|', '/')} |")
        L.append("")
    return "\n".join(L)


def main(argv=None):
    args = config.base_parser(__doc__).parse_args(argv)
    out_dir = config.output_dir(args.mock)
    analysis = analyse(out_dir)
    for c, cnt in analysis["counts"].items():
        print(f"{config.CONDITION_LABELS[c]:24s} {sum(cnt.values()):3d} wrong  {cnt}")
    print(f"Saved {out_dir}/error_analysis.md and error_analysis.json")


if __name__ == "__main__":
    main()
