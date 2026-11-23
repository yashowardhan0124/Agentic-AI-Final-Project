"""
Central configuration. Every script reads its settings from here, so a run
can be reproduced by changing one file (or the matching CLI flags).
"""

import argparse
import os

# ---- model / server -------------------------------------------------------
MODEL = os.environ.get("COT_MODEL", "qwen2.5:3b")
OLLAMA_URL = os.environ.get("COT_OLLAMA_URL", "http://localhost:11434")
REQUEST_TIMEOUT_S = 300
NUM_PREDICT = 1024          # hard cap on generated tokens per answer

# ---- experiment design ----------------------------------------------------
# Run 0 is always greedy (temperature 0) -> directly comparable to the v1 run.
# Runs 1..N-1 are sampled at SAMPLE_TEMPERATURE with fixed seeds, so we can
# measure how stable each prompting condition is, not just one lucky pass.
DEFAULT_RUNS = 5
SAMPLE_TEMPERATURE = 0.7

CONDITIONS = ("standard", "cot", "structured")
CONDITION_LABELS = {
    "standard": "Standard prompting",
    "cot": "Zero-shot CoT",
    "structured": "Structured CoT (fix)",
}

# ---- output locations -----------------------------------------------------
REAL_OUTPUT_DIR = "outputs"
MOCK_OUTPUT_DIR = "outputs_mock"   # mock runs can never overwrite real results


def run_settings(run_index: int) -> dict:
    """Temperature + seed for a given run index."""
    if run_index == 0:
        return {"temperature": 0.0, "seed": 0}
    return {"temperature": SAMPLE_TEMPERATURE, "seed": run_index}


def output_dir(mock: bool) -> str:
    path = MOCK_OUTPUT_DIR if mock else REAL_OUTPUT_DIR
    os.makedirs(os.path.join(path, "logs"), exist_ok=True)
    return path


def base_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--mock", action="store_true",
                   help="use the offline mock model (pipeline testing only; "
                        "writes to outputs_mock/, never to outputs/)")
    return p


def add_run_args(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                   help=f"runs per problem per condition (default {DEFAULT_RUNS}; "
                        "run 0 is greedy, the rest are sampled)")
    p.add_argument("--quick", action="store_true",
                   help="shortcut for --runs 1 (greedy only, fastest)")
    p.add_argument("--model", default=MODEL, help=f"Ollama model tag (default {MODEL})")
    p.add_argument("--fresh", action="store_true",
                   help="ignore the response cache and re-query the model")
    return p
