"""
Runs the whole project end to end:

  Steps 2+3  run_experiment.py   standard vs zero-shot CoT, every problem x runs
  Step 4     error_analysis.py   categorise every wrong answer, trace hardest case
  Step 5     prompt_fix.py       structured-CoT fix on all problems, fixed vs broken
  Report     report.py           REPORT.md, results_table.md, summary.json
  Deck       build_deck.py       CoT_Project_Presentation_v2.pptx from the results

Usage:
    python run_all.py              # full run, 5 runs per problem (~30-60 min on CPU)
    python run_all.py --runs 3     # faster, still gives variance estimates
    python run_all.py --quick      # greedy only, ~10 min
    python run_all.py --mock       # offline pipeline test with FAKE data

Interrupted? Just run the same command again -- finished model calls are
cached in outputs/cache.jsonl and are not repeated.
"""

import time

import build_deck
import config
import error_analysis
import prompt_fix
import report
import run_experiment


def main():
    p = config.add_run_args(config.base_parser(__doc__))
    args = p.parse_args()
    passthrough = []
    if args.mock:
        passthrough.append("--mock")
    run_args = passthrough + ["--runs", str(1 if args.quick else args.runs),
                              "--model", args.model] + (["--fresh"] if args.fresh else [])

    t0 = time.time()
    stages = [
        ("STEPS 2+3: standard vs zero-shot CoT", run_experiment.main, run_args),
        ("STEP 4: root-cause analysis", error_analysis.main, passthrough),
        ("STEP 5: structured-CoT fix", prompt_fix.main, run_args),
        ("REPORT", report.main, passthrough),
        ("DECK", build_deck.main, passthrough),
    ]
    for title, fn, a in stages:
        print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
        fn(a)

    out = config.output_dir(args.mock)
    print(f"\nAll done in {(time.time() - t0) / 60:.1f} min. Deliverables in {out}/:")
    print("  REPORT.md                        full write-up + jury Q&A")
    print("  CoT_Project_Presentation_v2.pptx deck built from these results")
    print("  results_table.md / summary.json  numbers")
    print("  error_analysis.md                every failure, categorised")
    print("  fix_results.json                 Step 5 fixed vs broken")
    print("  logs/                            every raw transcript")
    if args.mock:
        print("\n  NOTE: --mock was used. These are FAKE results for pipeline testing.")


if __name__ == "__main__":
    main()
