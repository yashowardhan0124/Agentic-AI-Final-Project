"""
Client for a locally running Ollama server.

Setup on the machine that runs the experiment:
    1. Install Ollama:          https://ollama.com/download
    2. Pull the model:          ollama pull qwen2.5:3b
    3. Make sure it's serving:  ollama serve   (usually auto-starts)

Besides the text, every call records the token counts and wall-clock time
Ollama reports, so the cost of chain-of-thought can be measured, and a
fixed seed so sampled runs are reproducible.
"""

import time

import requests

import config


class OllamaClient:
    name = "ollama"

    def __init__(self, model: str = config.MODEL, base_url: str = config.OLLAMA_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")

    # -- health check + model fingerprint ---------------------------------
    def check(self) -> dict:
        """Fail fast with a clear message, and return the model's digest so
        the exact weights used are recorded alongside the results."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=10)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            raise SystemExit(
                f"\nCannot reach Ollama at {self.base_url}.\n"
                f"Start it with 'ollama serve' and try again. ({e})"
            )
        models = r.json().get("models", [])
        for m in models:
            if m.get("name") in (self.model, f"{self.model}:latest") or m.get("model") == self.model:
                return {
                    "model": self.model,
                    "digest": m.get("digest", "")[:12],
                    "parameter_size": m.get("details", {}).get("parameter_size", ""),
                    "quantization": m.get("details", {}).get("quantization_level", ""),
                }
        available = ", ".join(m.get("name", "?") for m in models) or "none"
        raise SystemExit(
            f"\nModel '{self.model}' is not pulled. Run:  ollama pull {self.model}\n"
            f"(models available: {available})"
        )

    # -- one completion -----------------------------------------------------
    def generate(self, prompt: str, temperature: float, seed: int,
                 max_retries: int = 2) -> dict:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "seed": seed,
                "num_predict": config.NUM_PREDICT,
            },
        }
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                t0 = time.time()
                resp = requests.post(f"{self.base_url}/api/generate", json=payload,
                                     timeout=config.REQUEST_TIMEOUT_S)
                resp.raise_for_status()
                data = resp.json()
                return {
                    "text": data.get("response", "").strip(),
                    "output_tokens": data.get("eval_count"),
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "latency_s": round(time.time() - t0, 3),
                }
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(1 + attempt)
        raise RuntimeError(
            f"Ollama call failed after {max_retries + 1} attempts: {last_err}"
        )
