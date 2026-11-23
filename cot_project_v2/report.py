"""
Builds the final deliverables from the saved results:

  summary.json      every number the deck uses (single source of truth)
  results_table.md  per-problem table for all three conditions
  REPORT.md         full write-up: Steps 1-5, statistics, limitations, Q&A

All interpretive sentences are generated from the numbers (see findings()),
so the report never claims more than the data shows.

Usage:
    python report.py          (after run_experiment.py, prompt_fix.py)
    python report.py --mock
"""

import json
import os
import sys

import config
import error_analysis
import stats
from problems import PROBLEMS, format_value
from runner import load_all, load_meta

V1_BASELINE = {"standard": "1/5 (20%)", "cot": "5/5 (100%)"}


def pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def pval(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}" if p < 0.1 else f"p = {p:.2f}"


def build_summary(out_dir):
    meta = load_meta(out_dir) or {}
    results = load_all(out_dir)
    if "standard" not in results or "cot" not in results:
        raise SystemExit("Run run_experiment.py first.")
    analysis = error_analysis.analyse(out_dir)
    conds = {c: stats.summarise_condition(t) for c, t in results.items()}
    comparisons = {"standard_vs_cot": stats.paired(results["standard"], results["cot"])}
    if "structured" in results:
        comparisons["cot_vs_structured"] = stats.paired(results["cot"], results["structured"])
    fix = None
    fix_path = os.path.join(out_dir, "fix_results.json")
    if os.path.exists(fix_path):
        with open(fix_path, encoding="utf-8") as f:
            fr = json.load(f)
        fix = {"fixed": len(fr["fixed"]), "broken": len(fr["broken"]),
               "still_wrong": len(fr["still_wrong"]), "cot_failures": fr["cot_failures"],
               "p_value": fr["mcnemar_p"],
               "fixed_examples": fr["fixed"][:5], "broken_examples": fr["broken"][:5]}
    summary = {
        "meta": meta,
        "mock": bool(meta.get("mock")),
        "n_problems": len(PROBLEMS),
        "runs": meta.get("runs", 1),
        "problems": [{k: p[k] for k in ("id", "title", "trap_type", "answer", "origin")}
                     for p in PROBLEMS],
        "conditions": conds,
        "comparisons": comparisons,
        "fix": fix,
        "error_counts": analysis["counts"],
        "categories": analysis["categories"],
        "showcase": analysis["showcase"],
        "v1_baseline": V1_BASELINE,
    }
    summary["findings"] = findings(summary)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary, results, analysis


# ---------------------------------------------------------------------------
def findings(s):
    """Data-driven headline findings: (title, body) pairs."""
    C = s["conditions"]
    std, cot = C["standard"], C["cot"]
    cmp = s["comparisons"]["standard_vs_cot"]
    out = []

    d = cot["accuracy"] - std["accuracy"]
    if d > 0 and cmp["p_value"] < 0.05:
        out.append(("Chain-of-thought works, and it isn't luck",
                    f"Zero-shot CoT raised accuracy from {pct(std['accuracy'])} to "
                    f"{pct(cot['accuracy'])} over {cot['trials']} paired trials. It fixed "
                    f"{cmp['b_right_a_wrong']} answers and broke {cmp['a_right_b_wrong']} "
                    f"(McNemar {pval(cmp['p_value'])})."))
    elif d > 0:
        out.append(("CoT helped, but not conclusively",
                    f"Accuracy rose from {pct(std['accuracy'])} to {pct(cot['accuracy'])}, "
                    f"but with this sample the gain is not statistically significant "
                    f"({pval(cmp['p_value'])})."))
    else:
        out.append(("CoT did not help on this set",
                    f"Standard prompting scored {pct(std['accuracy'])} and zero-shot CoT "
                    f"{pct(cot['accuracy'])} ({pval(cmp['p_value'])})."))

    if cot["v1_accuracy"] is not None and cot["v2_accuracy"] is not None:
        gap = cot["v1_accuracy"] - cot["v2_accuracy"]
        if gap > 0.05:
            out.append(("The original 100% doesn't carry over to harder problems",
                        f"Under CoT the model scored {pct(cot['v1_accuracy'])} on the 5 "
                        f"original problems but {pct(cot['v2_accuracy'])} on the 10 new "
                        f"trap problems. Giving the model room to reason is not "
                        f"enough when a problem hides a condition it can misread."))
        else:
            out.append(("The result held up on harder problems",
                        f"Under CoT the model scored {pct(cot['v1_accuracy'])} on the "
                        f"original problems and {pct(cot['v2_accuracy'])} on the 10 new "
                        f"trap problems."))

    cc = s["error_counts"].get("cot", {})
    if cc:
        top, n = max(cc.items(), key=lambda kv: kv[1])
        total = sum(cc.values())
        out.append(("Where CoT still breaks",
                    f"The most common CoT failure was “{s['categories'][top]}” "
                    f"({n} of {total} wrong answers). Every failure is categorised "
                    f"automatically and linked to its transcript."))

    f = s["fix"]
    if f:
        sc = C.get("structured")
        net = f["fixed"] - f["broken"]
        if f["cot_failures"] == 0:
            out.append(("Nothing left for the fix to fix",
                        f"Plain CoT made no errors, so the structured prompt could only be "
                        f"checked for harm: it broke {f['broken']} correct answer(s). The "
                        f"trap problems were not hard enough to separate the two prompts."))
        elif f["fixed"] > f["broken"] and f["p_value"] >= 0.05:
            out.append(("The structured fix helped a little, not conclusively",
                        f"It fixed {f['fixed']} of the {f['cot_failures']} CoT failures but "
                        f"also broke {f['broken']} correct answers (net {net:+d}; accuracy "
                        f"{pct(cot['accuracy'])} \u2192 {pct(sc['accuracy'])}, "
                        f"{pval(f['p_value'])}, not significant). Testing on every problem, "
                        f"not just failures, is what exposes the breakage."))
        elif f["fixed"] > f["broken"]:
            out.append(("A targeted prompt fix closes part of the gap",
                        f"The structured prompt fixed {f['fixed']} of the "
                        f"{f['cot_failures']} CoT failures and broke {f['broken']} "
                        f"correct answers (net {net:+d}; accuracy "
                        f"{pct(cot['accuracy'])} → {pct(sc['accuracy'])}, "
                        f"{pval(f['p_value'])})."))
        else:
            out.append(("The structured fix did not help this model",
                        f"It fixed {f['fixed']} CoT failures but broke {f['broken']} "
                        f"correct answers (net {net:+d}). A 3B model may lose track "
                        f"when the format itself gets more demanding."))

    if std["mean_output_tokens"] and cot["mean_output_tokens"]:
        ratio = cot["mean_output_tokens"] / max(1, std["mean_output_tokens"])
        out.append(("Reasoning has a cost",
                    f"CoT answers averaged {cot['mean_output_tokens']:.0f} output tokens "
                    f"vs {std['mean_output_tokens']:.0f} for standard prompting "
                    f"({ratio:.0f}×), and {cot['mean_latency_s']:.1f} s vs "
                    f"{std['mean_latency_s']:.1f} s per answer."))
    return out


def qa(s):
    """Data-driven answers to the likely jury questions."""
    C = s["conditions"]
    sc = s["showcase"]
    items = []
    if sc:
        f = sc["failure"]
        q1 = (f"Hardest problem under CoT: {sc['title']} ({sc['cot_pass']}/{sc['runs']} runs "
              f"correct). In run {f['run']} the model answered "
              f"{format_value(sc['problem_id'], f['predicted'])} instead of "
              f"{format_value(sc['problem_id'], sc['answer'])}. Diagnosis: {f['detail']}.")
        if f.get("evidence_line"):
            q1 += f" The line where it leaves the correct path: “{f['evidence_line'][:120]}”."
    else:
        q1 = ("Plain CoT made no errors, so the hardest case is a standard-prompting "
              "failure; see error_analysis.md for each one's diagnosis.")
    items.append(("Show me the exact step where the reasoning went wrong on your hardest problem.", q1))

    fx = s["fix"]
    if fx:
        sc_acc = C["structured"]["accuracy"]
        q2 = (f"Tested on all {C['structured']['trials']} trials, not just the failures. It fixed "
              f"{fx['fixed']} of {fx['cot_failures']} CoT failures and broke {fx['broken']} "
              f"(accuracy {pct(C['cot']['accuracy'])} → {pct(sc_acc)}, {pval(fx['p_value'])}). ")
        q2 += ("Errors the fix removes were structural (a missed rule or a skipped "
               "check). Errors that survive point to the model's limits."
               if fx["fixed"] > fx["broken"] else
               "So prompt structure alone can't fix these errors for a 3B model; the "
               "remaining errors look like capability limits, not format problems.")
    else:
        q2 = "Run prompt_fix.py to test the fix."
    items.append(("Did your proposed fix actually work when you tested it? What does that tell you?", q2))

    cmp = s["comparisons"]["standard_vs_cot"]
    lo, hi = C["cot"]["ci95"]
    items.append(("Is 15 problems enough to trust this?",
                  f"Each problem was run {s['runs']}× per prompt ({C['cot']['trials']} graded "
                  f"answers per condition). CoT accuracy is {pct(C['cot']['accuracy'])} "
                  f"(95% CI {pct(lo)}–{pct(hi)}), and the paired McNemar test against "
                  f"standard prompting gives {pval(cmp['p_value'])}. It's still one model "
                  f"and one problem style, which is listed as a limitation."))
    std_t, cot_t = C["standard"]["mean_output_tokens"], C["cot"]["mean_output_tokens"]
    if std_t and cot_t:
        items.append(("What does chain-of-thought cost you?",
                      f"About {cot_t / max(1, std_t):.0f}× the output tokens "
                      f"({cot_t:.0f} vs {std_t:.0f}) and {C['cot']['mean_latency_s']:.1f} s "
                      f"vs {C['standard']['mean_latency_s']:.1f} s per answer on this machine."))
    return items


LIMITATIONS = [
    "One small model (qwen2.5:3b): results may not transfer to larger models.",
    "15 hand-written problems in one style (money/quantity word problems).",
    "Step-level diagnosis is heuristic (numbers in the trace), so it's confirmed by reading the log.",
    "Trap values cover the mistakes we anticipated; unanticipated ones fall to other categories.",
]
NEXT_STEPS = [
    "Run the same pipeline on a 7B model and on GSM8K problems.",
    "Few-shot CoT and self-consistency voting as further conditions.",
    "Let the model call a calculator tool, to separate reasoning errors from arithmetic errors.",
]


# ---------------------------------------------------------------------------
def results_table(s):
    conds = [c for c in config.CONDITIONS if c in s["conditions"]]
    C = s["conditions"]
    L = ["| Problem | Correct answer | " + " | ".join(config.CONDITION_LABELS[c] for c in conds) + " |",
         "|---|---|" + "---|" * len(conds)]
    for p in PROBLEMS:
        cells = []
        for c in conds:
            pp = C[c]["per_problem"][p["id"]]
            cells.append(f"{pp['correct']}/{pp['runs']} (greedy: "
                         f"{'PASS' if pp['greedy_correct'] else 'FAIL'}, got {pp['greedy_pred']})")
        L.append(f"| {p['id']} | {p['answer']:g} | " + " | ".join(cells) + " |")
    L.append("| **Accuracy (all runs)** | | " + " | ".join(
        f"**{C[c]['correct']}/{C[c]['trials']} ({pct(C[c]['accuracy'])})**" for c in conds) + " |")
    L.append("| **Greedy run only** | | " + " | ".join(
        f"{C[c]['greedy_correct']}/{C[c]['greedy_n']}" for c in conds) + " |")
    return "\n".join(L)


def write_report(out_dir, s):
    C = s["conditions"]
    conds = [c for c in config.CONDITIONS if c in C]
    m = s["meta"].get("model", {})
    L = []
    if s["mock"]:
        L += ["> **MOCK DATA -- produced by mock_client.py to test the pipeline. "
              "These are NOT real model results.**", ""]
    L += ["# Chain-of-Thought Math Word Problem Solver -- v2 Results & Error Analysis", "",
          f"**Model:** {m.get('model', '?')} (digest `{m.get('digest', '?')}`, "
          f"{m.get('parameter_size', '')} {m.get('quantization', '')}) via Ollama  ",
          f"**Problems:** {s['n_problems']} (5 original + 10 new trap problems)  ",
          f"**Runs:** {s['runs']} per problem per condition (run 0 greedy, the rest sampled at "
          f"T={s['meta'].get('sample_temperature')})  ",
          f"**Run started:** {s['meta'].get('started', '?')}", ""]

    L += ["## Headline findings", ""]
    for i, (t, b) in enumerate(s["findings"], 1):
        L.append(f"{i}. **{t}.** {b}")
    L += ["", "## Step 1 -- Problems", "",
          "| # | Problem | What makes it hard | Answer | Set |", "|---|---|---|---|---|"]
    for p in PROBLEMS:
        L.append(f"| {p['id'].split('_')[0]} | {p['title']} | {p['trap_type']} | "
                 f"{p['answer']:g} | {'original' if p['origin'] == 'v1' else 'new'} |")

    L += ["", "## Steps 2-3 (+5) -- Accuracy", "", results_table(s), ""]
    L += ["| Metric | " + " | ".join(config.CONDITION_LABELS[c] for c in conds) + " |",
          "|---|" + "---|" * len(conds)]
    rows = [
        ("Accuracy, all runs", lambda c: f"{pct(C[c]['accuracy'])}"),
        ("95% CI (Wilson)", lambda c: f"{pct(C[c]['ci95'][0])}-{pct(C[c]['ci95'][1])}"),
        ("Per-run mean ± SD", lambda c: f"{pct(C[c]['per_run_mean'])} ± {pct(C[c]['per_run_sd'])}"),
        ("Greedy run", lambda c: f"{C[c]['greedy_correct']}/{C[c]['greedy_n']}"),
        ("Majority vote across runs", lambda c: f"{C[c]['majority_vote_correct']}/{s['n_problems']}"),
        ("Original 5 problems", lambda c: pct(C[c]['v1_accuracy'])),
        ("New 10 problems", lambda c: pct(C[c]['v2_accuracy'])),
        ("Mean output tokens", lambda c: f"{C[c]['mean_output_tokens']:.0f}" if C[c]['mean_output_tokens'] else "n/a"),
        ("Mean latency (s)", lambda c: f"{C[c]['mean_latency_s']:.1f}" if C[c]['mean_latency_s'] else "n/a"),
        ("Answers needing extraction fallback", lambda c: str(C[c]['extraction_fallbacks'])),
    ]
    for label, fn in rows:
        L.append(f"| {label} | " + " | ".join(fn(c) for c in conds) + " |")
    L.append("")
    for key, label in (("standard_vs_cot", "Standard -> CoT"), ("cot_vs_structured", "CoT -> Structured")):
        if key in s["comparisons"]:
            c = s["comparisons"][key]
            L.append(f"- **{label}:** fixed {c['b_right_a_wrong']}, broke {c['a_right_b_wrong']} "
                     f"paired trials -- exact McNemar {pval(c['p_value'])}")
    L += ["", f"For reference, the original v1 run (5 problems, greedy only) scored "
              f"{s['v1_baseline']['standard']} standard vs {s['v1_baseline']['cot']} CoT "
              f"(archived in `archive/v1_original_run/`).", ""]

    L += ["## Step 4 -- Root-cause analysis", "",
          "Full per-failure table and the hardest-case step trace: `error_analysis.md`.", "",
          "| Category | " + " | ".join(config.CONDITION_LABELS[c] for c in conds) + " |",
          "|---|" + "---|" * len(conds)]
    for key, label in s["categories"].items():
        vals = [str(s["error_counts"].get(c, {}).get(key, 0)) for c in conds]
        if any(v != "0" for v in vals):
            L.append(f"| {label} | " + " | ".join(vals) + " |")
    L.append("")

    L += ["## Step 5 -- Proposed fix: structured CoT", "",
          "Each line of the prompt targets one Step-4 failure category:", "",
          "- `Given numbers` -- stops values being dropped or mis-copied (wrong step)",
          "- `Rules` -- states rounding / discounts / what is asked up front (known traps)",
          "- one operation per step -- keeps arithmetic checkable (arithmetic slips)",
          "- `Check` -- re-verifies and confirms the quantity asked for (answered a sub-question)", ""]
    if s["fix"]:
        f = s["fix"]
        L += [f"Tested on **all** problems and runs (paired with plain CoT): fixed **{f['fixed']}**, "
              f"broke **{f['broken']}**, still wrong **{f['still_wrong']}** "
              f"(McNemar {pval(f['p_value'])}). Details: `fix_results.json`.", ""]

    L += ["## Jury Q&A", ""]
    for q, a in qa(s):
        L += [f"**Q: {q}**  ", a, ""]
    L += ["## Limitations", ""] + [f"- {x}" for x in LIMITATIONS]
    L += ["", "## Next steps", ""] + [f"- {x}" for x in NEXT_STEPS] + [""]

    with open(os.path.join(out_dir, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    with open(os.path.join(out_dir, "results_table.md"), "w", encoding="utf-8") as f:
        f.write(results_table(s) + "\n")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = config.base_parser(__doc__).parse_args(argv)
    out_dir = config.output_dir(args.mock)
    s, _, _ = build_summary(out_dir)
    write_report(out_dir, s)
    print(results_table(s))
    print()
    for t, b in s["findings"]:
        print(f"* {t}: {b}")
    print(f"\nSaved {out_dir}/REPORT.md, results_table.md, summary.json, error_analysis.md")


if __name__ == "__main__":
    main()
