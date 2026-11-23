# Chain-of-Thought Math Word Problem Solver — Final Results & Error Analysis

**Model:** qwen2.5:3b (via Ollama, run locally) · **Problems:** 5 multi-step word problems

## Steps 2–3 — Results

| Problem | Correct answer | Standard prompting | Zero-shot CoT |
|---|---|---|---|
| P1 – café cups | 216 | FAIL (got 5.0) | PASS (got 216.0) |
| P2 – bookstore discount | 148.5 | FAIL (got 143.05) | PASS (got 148.5) |
| P3 – road-trip fuel | 104 | PASS (got 104.0) | PASS (got 104.0) |
| P4 – classroom supplies | 46.8 | FAIL (got 56.80) | PASS (got 46.8) |
| P5 – savings goal | 550 | FAIL (got 260.0) | PASS (got 550.0) |
| **Accuracy** | | **1/5 (20%)** | **5/5 (100%)** |

CoT took accuracy from 20% to 100% — every problem that failed under standard prompting was fixed once the model was told to reason step by step.

## Step 4 — Root-cause analysis

Zero-shot CoT solved all 5 problems, so there is no CoT failure to diagnose. The real diagnostic value is in *why standard prompting failed* — inspecting the raw transcripts (`logs/*_standard.txt`) shows the failure mode clearly:

**P1 – café cups:** prompt explicitly said "do not show any work." Model output was just `Final Answer: 5` — no reasoning at all, and 5 bears no obvious relationship to any number in the problem (150, 90, 75, 40, 24, 18). This is the clearest case: with no room to reason, the model appears to pattern-match to *some* small plausible-looking number rather than compute anything.

**P2 – bookstore discount:** predicted 143.05 vs. correct 148.50 — close enough that the model likely did attempt the right operations internally but made an arithmetic slip (or dropped a digit) with no visible steps to catch it.

**P4 – classroom supplies:** predicted 56.80 vs. correct 46.80 — off by exactly $10.00, suggesting one pack-cost term (pencils or pens) was miscounted or duplicated.

**P5 – savings goal:** predicted 260 vs. correct 550 — a large miss, consistent with the model skipping a whole step (e.g., forgetting the doubled-rate second half of the trip) with no chain of reasoning to keep it on track.

**Common thread:** every standard-prompting failure occurs when the model has no visible scratch space — forced to output only a number, it cannot track multi-step dependencies (grouping, rounding, sequential totals) reliably.

## Step 5 — Was a further fix tested?

Since zero-shot CoT already reached 100% accuracy, no additional prompt fix was needed on top of it — CoT itself was the fix. The comparison in the table above **is** the tested fix: standard vs. CoT prompting, run on the identical 5 problems, identical model, identical extraction logic.

## Jury Q&A

**Q1: Show me the exact step where the model's reasoning went wrong on your hardest problem.**
The hardest problem for standard prompting was P1 (café cups): forced to answer with no reasoning, the model produced `Final Answer: 5` with zero connection to the problem's numbers (see `logs/P1_cafe_cups_standard.txt`). Under CoT on the same problem, the model correctly worked through: total cups needed (150+90+75=315) → cups still needed after stock (315-40=275) → boxes required, rounding up (275/24 → 12 boxes) → total cost (12×18=216), arriving at the correct `Final Answer: 216` (see `logs/P1_cafe_cups_cot.txt`). The "wrong step" isn't a single miscalculation — it's the complete absence of any intermediate step when reasoning is suppressed.

**Q2: Did your proposed fix actually work when you tested it? What does that tell you?**
Yes — the fix (zero-shot CoT) resolved all 4 problems that failed under standard prompting, taking accuracy from 1/5 (20%) to 5/5 (100%). This tells us the model's failures were **not** a knowledge or capability gap — it clearly *can* do this arithmetic, as shown by the identical correct answers once given room to reason. The failures were purely a **structural/format** problem: without a visible chain of intermediate steps, the model has nothing to track multi-step dependencies against, so it produces an answer disconnected from the problem's actual numbers. Simply asking it to "think step by step" was sufficient to fix every failure case on this problem set.