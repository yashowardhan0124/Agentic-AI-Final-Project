"""
Step 5 -- test the proposed fix (structured CoT, see prompts.py).

The fix is run on ALL problems with the same runs/seeds as Steps 2-3, not
just on the failures. That lets us report both sides honestly:

  fixed  : trials that were WRONG under plain CoT and RIGHT with the fix
  broken : trials that were RIGHT under plain CoT and WRONG with the fix
           (a fix that only gets tested on failures can never show this)

Trials are paired by (problem, run), and the difference is tested with an
exact McNemar test.

Usage:
    python prompt_fix.py          (after run_experiment.py)
    python prompt_fix.py --mock
"""

import json
import os

import config
import stats
from problems import PROBLEMS
from runner import Cache, load_meta, load_results, make_client, run_condition, save_results


def compare(cot, structured):
    by_key = {(t["problem_id"], t["run"]): t for t in cot}
    fixed, broken, still_wrong, both_right = [], [], [], []
    for s in structured:
        c = by_key.get((s["problem_id"], s["run"]))
        if c is None:
            continue
        row = {"problem_id": s["problem_id"], "run": s["run"],
               "cot_pred": c["predicted"], "fix_pred": s["predicted"],
               "expected": s["expected"],
               "cot_log": c["log_file"], "fix_log": s["log_file"]}
        if not c["correct"] and s["correct"]:
            fixed.append(row)
        elif c["correct"] and not s["correct"]:
            broken.append(row)
        elif not c["correct"] and not s["correct"]:
            still_wrong.append(row)
        else:
            both_right.append(row)
    per_problem = []
    for p in PROBLEMS:
        pc = [t for t in cot if t["problem_id"] == p["id"]]
        ps = [t for t in structured if t["problem_id"] == p["id"]]
        per_problem.append({
            "problem_id": p["id"],
            "cot_correct": sum(t["correct"] for t in pc),
            "fix_correct": sum(t["correct"] for t in ps),
            "runs": len(ps),
        })
    return {
        "fixed": fixed,
        "broken": broken,
        "still_wrong": still_wrong,
        "both_right_count": len(both_right),
        "cot_failures": len(fixed) + len(still_wrong),
        "mcnemar_p": stats.mcnemar_exact(len(fixed), len(broken)),
        "per_problem": per_problem,
    }


def main(argv=None):
    p = config.add_run_args(config.base_parser(__doc__))
    args = p.parse_args(argv)
    out_dir = config.output_dir(args.mock)
    meta = load_meta(out_dir)
    cot = load_results(out_dir, "cot")
    if meta is None or cot is None:
        raise SystemExit("Run run_experiment.py first.")
    runs = meta["runs"]  # always match the runs/seeds used for Steps 2-3

    model_tag = meta.get("model_tag", args.model)  # same model as Steps 2-3
    client = make_client(args.mock, model_tag)
    client.check()
    cache = Cache(out_dir, enabled=not args.fresh)
    print(f"\n=== {config.CONDITION_LABELS['structured']} ({runs} run(s)) ===")
    structured = run_condition("structured", client, out_dir, runs, cache, args.mock)
    save_results(out_dir, "structured", structured)

    result = compare(cot, structured)
    with open(os.path.join(out_dir, "fix_results.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    n = len(structured)
    print(f"\nPlain CoT failures:          {result['cot_failures']} of {n} trials")
    print(f"Fixed by structured prompt:  {len(result['fixed'])}")
    print(f"Broken by structured prompt: {len(result['broken'])}")
    print(f"Still wrong under both:      {len(result['still_wrong'])}")
    print(f"McNemar exact p = {result['mcnemar_p']:.3g}")
    print(f"Saved {out_dir}/fix_results.json")


if __name__ == "__main__":
    main()
