"""
OFFLINE MOCK MODEL -- for testing the pipeline only. NOT EXPERIMENTAL DATA.

It fabricates plausible-looking responses (some correct, some falling into
the problems' known traps, some with arithmetic slips) so every script,
the report and the deck can be exercised end to end without Ollama.

Safety rails so mock output can never be mistaken for real results:
  * it only runs with --mock
  * it writes to outputs_mock/, never outputs/
  * every log, the report and every deck slide carry a MOCK DATA banner
"""

import hashlib
import random

from problems import PROBLEMS

ACCURACY = {"standard": 0.35, "cot": 0.75, "structured": 0.85}


def _condition_of(prompt: str) -> str:
    if "Given numbers:" in prompt:
        return "structured"
    if "think step by step" in prompt:
        return "cot"
    return "standard"


def _fmt(v: float) -> str:
    return f"{v:g}" if float(v).is_integer() else f"{v:.2f}"


class MockClient:
    name = "mock"

    def __init__(self, model: str = "mock-model"):
        self.model = model

    def check(self) -> dict:
        return {"model": f"MOCK ({self.model})", "digest": "mock",
                "parameter_size": "n/a", "quantization": "n/a"}

    def generate(self, prompt: str, temperature: float, seed: int) -> dict:
        problem = next(p for p in PROBLEMS if p["question"] in prompt)
        cond = _condition_of(prompt)
        h = hashlib.sha256(f"{prompt}|{temperature}|{seed}".encode()).hexdigest()
        rng = random.Random(int(h[:12], 16))
        # harder (v2) problems fail more often
        acc = ACCURACY[cond] - (0.12 if problem["origin"] == "v2" else 0)
        ok = rng.random() < acc
        traps = list(problem["traps"].items())

        if cond == "standard":
            if ok:
                final = problem["answer"]
            elif traps and rng.random() < 0.5:
                final = rng.choice(traps)[0]
            else:
                final = round(problem["answer"] * rng.uniform(0.3, 1.6), 2)
            text = f"Final Answer: {_fmt(final)}"
            return {"text": text, "output_tokens": rng.randint(5, 9),
                    "prompt_tokens": 120, "latency_s": round(rng.uniform(0.2, 0.5), 3)}

        steps = problem["steps"]
        lines = ["[MOCK RESPONSE - NOT REAL MODEL OUTPUT]"]
        if cond == "structured":
            lines.append("Given numbers: (mock)")
            lines.append("Rules: (mock)")
        final = problem["answer"]
        mode = None if ok else rng.choice(["trap", "slip", "skip"])
        if mode == "trap" and not traps:
            mode = "slip"
        skip_at = rng.randrange(len(steps)) if mode == "skip" else None
        slip_at = rng.randrange(len(steps)) if mode == "slip" else None
        for i, (label, value) in enumerate(steps):
            if i == skip_at:
                continue
            if i == slip_at:
                a = rng.randint(20, 90)
                b = rng.randint(2, 9)
                lines.append(f"Step {i + 1}: {label}: {a} * {b} = {a * b + rng.randint(3, 9)}")
                final = round(problem["answer"] * rng.uniform(0.7, 0.95), 2)
                break
            if mode == "trap" and i == len(steps) - 1:
                final = rng.choice(traps)[0]
                lines.append(f"Step {i + 1}: {label.split('(')[0].strip()} = {_fmt(final)}")
                break
            lines.append(f"Step {i + 1}: {label.split('(')[0].strip()} = {_fmt(value)}")
        if mode == "skip":
            final = round(problem["answer"] * rng.uniform(1.1, 1.4), 2)
        if cond == "structured":
            lines.append("Check: (mock)")
        lines.append(f"Final Answer: {_fmt(final)}")
        base = 260 if cond == "cot" else 330
        return {"text": "\n".join(lines),
                "output_tokens": base + rng.randint(-60, 90) + 15 * len(steps),
                "prompt_tokens": 140 if cond == "cot" else 230,
                "latency_s": round(rng.uniform(6, 14), 3)}
