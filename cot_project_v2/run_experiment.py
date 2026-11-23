"""
Steps 2 + 3 -- standard prompting vs. zero-shot chain-of-thought.

Every problem is run under both conditions, RUNS times each:
  run 0      greedy (temperature 0)  -> same setup as the original v1 run
  run 1..N-1 sampled (temperature 0.7, fixed seeds) -> measures stability

Usage:
    python run_experiment.py              # 5 runs per problem per condition
    python run_experiment.py --quick      # greedy only
    python run_experiment.py --mock       # offline pipeline test (fake data)
"""

import datetime

import config
from runner import Cache, make_client, run_condition, save_meta, save_results


def main(argv=None):
    p = config.add_run_args(config.base_parser(__doc__))
    args = p.parse_args(argv)
    runs = 1 if args.quick else max(1, args.runs)
    out_dir = config.output_dir(args.mock)

    client = make_client(args.mock, args.model)
    model_info = client.check()
    print(f"Model: {model_info}")
    save_meta(out_dir, {
        "model": model_info,
        "model_tag": args.model,
        "runs": runs,
        "sample_temperature": config.SAMPLE_TEMPERATURE,
        "num_predict": config.NUM_PREDICT,
        "mock": args.mock,
        "started": datetime.datetime.now().isoformat(timespec="seconds"),
    })

    cache = Cache(out_dir, enabled=not args.fresh)
    for condition in ("standard", "cot"):
        print(f"\n=== {config.CONDITION_LABELS[condition]} ===")
        trials = run_condition(condition, client, out_dir, runs, cache, args.mock)
        save_results(out_dir, condition, trials)
        acc = sum(t["correct"] for t in trials) / len(trials)
        print(f"--> {condition}: {acc:.0%} correct over {len(trials)} trials")

    print(f"\nSaved results_standard.json, results_cot.json and logs/ in {out_dir}/")


if __name__ == "__main__":
    main()
