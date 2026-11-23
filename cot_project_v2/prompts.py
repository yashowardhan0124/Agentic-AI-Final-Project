"""
The three prompting conditions.

  standard   : answer only, no reasoning (Step 2)
  cot        : zero-shot chain-of-thought, "Let's think step by step" (Step 3)
  structured : the Step 5 fix. Each line targets one failure category that
               error_analysis.py measures:

     Given numbers  -> stops numbers being dropped or mis-copied (wrong step)
     Rules          -> forces every condition to be stated up front: rounding
                       up, discounts, things already done, what is asked
                       (known-trap errors)
     One op / step  -> keeps arithmetic small and checkable (arithmetic slips)
     Check          -> re-verifies results and that the answer is the
                       quantity asked for (stopped-early errors)

All three end with the same "Final Answer: <number>" line, so the same
extraction code grades all of them identically.
"""

FINAL_LINE = "Final Answer: <number>"


def standard_prompt(question: str) -> str:
    return (
        f"Q: {question}\n"
        "A: Give ONLY the final numeric answer. Do not show any work. "
        "End your response with exactly one line formatted as:\n"
        f"{FINAL_LINE}"
    )


def cot_prompt(question: str) -> str:
    return (
        f"Q: {question}\n"
        "A: Let's think step by step. Work through the problem carefully, "
        "then end your response with exactly one line formatted as:\n"
        f"{FINAL_LINE}"
    )


def structured_prompt(question: str) -> str:
    return (
        f"Q: {question}\n"
        "A: Solve this carefully using exactly this format:\n"
        "Given numbers: <list every number in the problem and what it means>\n"
        "Rules: <list every condition that changes the math, e.g. rounding up "
        "because items come in whole packs, discounts, things already done, "
        "and exactly what quantity the question asks for>\n"
        "Step 1: <one arithmetic operation only, with its result>\n"
        "Step 2: <one arithmetic operation only, with its result>\n"
        "(add as many numbered steps as needed, one operation each)\n"
        "Check: <recompute each step's result, confirm every rule above was "
        "applied, and confirm the answer is the quantity the question asks for>\n"
        f"{FINAL_LINE}"
    )


BUILDERS = {
    "standard": standard_prompt,
    "cot": cot_prompt,
    "structured": structured_prompt,
}


def build_prompt(condition: str, question: str) -> str:
    return BUILDERS[condition](question)
