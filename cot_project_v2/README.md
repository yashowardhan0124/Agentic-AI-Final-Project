# Chain-of-Thought Math Word Problem Solver with Error Analysis (v2)

Does telling a small model to "think step by step" fix its math? Where does
it still break, and can a targeted prompt fix those errors?

## Run it (one command)

```bash
# 1. Install Ollama: https://ollama.com/download, then:
ollama pull qwen2.5:3b
# 2. Python deps
pip install -r requirements.txt
# 3. Everything: experiment -> error analysis -> fix -> report -> deck
python run_all.py
```

| Option | Use when |
|---|---|
| `python run_all.py` | full run: 15 problems × 3 prompts × 5 runs = 225 answers (~30–60 min on a laptop CPU, a few min on GPU) |
| `python run_all.py --runs 3` | short on time, still gives variance estimates |
| `python run_all.py --quick` | greedy only (one run), ~10 min |
| `python run_all.py --model qwen2.5:7b` | another model |
| `python run_all.py --mock` | offline pipeline test with **fake** data, written to `outputs_mock/`, every slide stamped MOCK |

Interrupted? Run the same command again. Finished model calls are cached in
`outputs/cache.jsonl` and are not repeated.

Unit tests (no Ollama needed): `python -m unittest discover -s tests -v`

## What it produces (in `outputs/`)

| File | Contents |
|---|---|
| `CoT_Project_Presentation_v2.pptx` | the deck, built from these results (speaker notes included) |
| `REPORT.md` | full write-up, findings, statistics, limitations, jury Q&A |
| `results_table.md` | every problem × every prompt |
| `error_analysis.md` | every wrong answer, categorised, plus the hardest case traced step by step |
| `fix_results.json` | Step 5: what the fix fixed, broke, and left wrong |
| `summary.json` | every number the deck uses |
| `logs/<problem>_<condition>_run<N>.txt` | full prompt + raw model output + grading for every answer |

## How the 5 required steps map to the code

| Step | File |
|---|---|
| 1. Multi-step problems (5 original + 10 new trap problems, each with ground-truth steps and known wrong answers) | `problems.py` |
| 2. Standard prompting | `prompts.py`, `run_experiment.py` |
| 3. Zero-shot CoT | `prompts.py`, `run_experiment.py` |
| 4. Root-cause analysis | `error_analysis.py` |
| 5. Propose + test a fix (structured CoT, tested on **all** problems) | `prompts.py`, `prompt_fix.py` |
| Statistics (Wilson 95% CI, exact McNemar, majority vote) | `stats.py` |
| Report + deck | `report.py`, `build_deck.py` |

## Design decisions (useful for the viva)

- **Run 0 is greedy (temperature 0)**, the same as the v1 run; runs 1–4 are sampled at
  temperature 0.7 with fixed seeds. Pooled accuracy plus a confidence interval answers
  "was it luck?"
- **McNemar test**, because both prompts answer the *same* problem in the *same* run, so
  the outcomes are paired. Only disagreements (one right, one wrong) carry information.
- **Trap values** (`problems.py`): each problem lists wrong answers predicted *in advance*
  with the mistake that produces them. A matching answer tells us which misreading happened,
  even when the model showed no work.
- **Arithmetic-slip detection** re-computes every equation written in the reasoning
  (LaTeX included) and flags wrong results. Rounding up to whole packs is not counted as a slip.
- **The fix is tested on every problem**, not just the failures, so it can be caught
  breaking answers plain CoT got right.
- **The deck and the report are generated from the data**, so a claim can't be
  stronger than the numbers behind it.

## History

`archive/v1_original_run/` is the first evaluation's real run (5 problems, greedy, 1/5 vs 5/5).
The v1 folder also had `dry_run_simulated.py`, `fix_results.json` and `logs/*_structured.txt`.
Those held hand-written stand-in responses from when no model was available, so they are not
part of v2. The mock client replaces them and is clearly labelled.
