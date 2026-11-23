"""
Answer extraction, grading, and text normalisation shared by every step.

extract_answer() tries, in order:
  1. the LAST "Final Answer:" line (markdown bold, \\boxed{}, "$1,234.50",
     "216 dollars", "12 boxes, $216" are all handled; a $-amount wins
     over a bare count on the same line)
  2. the last \\boxed{...}
  3. the last number anywhere in the response (logged as a fallback, so a
     format failure is visible in the results rather than hidden)
"""

import re

# Plain number, optionally with thousands separators: 1,234.50 / 216 / 0.5 / -3
NUM = r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_NUM_RE = re.compile(NUM)


def to_float(s: str):
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def normalise(text: str) -> str:
    """Turn LaTeX / markdown maths into plain text so numbers and simple
    equations can be read reliably."""
    t = text
    t = re.sub(r"\\text\{[^}]*\}", " ", t)            # \text{ pencils}
    t = re.sub(r"\\(?:mathrm|textbf|mathbf)\{([^}]*)\}", r"\1", t)
    t = re.sub(r"\\[dt]?frac\{([^}]*)\}\{([^}]*)\}", r"(\1) / (\2)", t)
    t = re.sub(r"\\lceil|\\rceil|\\lfloor|\\rfloor|\\left|\\right", " ", t)
    t = t.replace("\\times", "*").replace("\\cdot", "*").replace("×", "*")
    t = t.replace("\\div", "/").replace("÷", "/")
    t = t.replace("\\approx", "≈").replace("\\$", "$").replace("\\%", "%")
    t = t.replace("\\,", "").replace("\\!", "").replace("\\ ", " ")
    t = t.replace("\\[", " ").replace("\\]", " ").replace("\\(", " ").replace("\\)", " ")
    t = t.replace("**", "").replace("−", "-").replace("–", "-")
    return t


def numbers_in(text: str) -> list:
    """Every number in the text, as floats, in order of appearance."""
    out = []
    for m in _NUM_RE.findall(normalise(text)):
        v = to_float(m)
        if v is not None:
            out.append(v)
    return out


def _number_from_segment(seg: str):
    boxed = re.search(r"\\boxed\{([^}]*)\}", seg)
    if boxed:
        seg = boxed.group(1)
    seg = normalise(seg)
    dollars = re.findall(r"\$\s*(" + NUM + ")", seg)
    if dollars:
        return to_float(dollars[-1])
    nums = _NUM_RE.findall(seg)
    if nums:
        return to_float(nums[0])
    return None


def extract_answer(text: str):
    """Return (value or None, method)."""
    if not text:
        return None, "empty"
    lines = text.splitlines()
    fa_idx = [i for i, ln in enumerate(lines)
              if re.search(r"final\s+answer", ln, re.IGNORECASE)]
    for i in reversed(fa_idx):
        after = re.split(r"final\s+answer", lines[i], flags=re.IGNORECASE)[-1]
        v = _number_from_segment(after)
        if v is None:  # "Final Answer:" with the number on the next line
            nxt = next((ln for ln in lines[i + 1:] if ln.strip()), "")
            v = _number_from_segment(nxt)
        if v is not None:
            return v, "final_answer_line"
    boxed = re.findall(r"\\boxed\{([^}]*)\}", text)
    for b in reversed(boxed):
        v = _number_from_segment(b)
        if v is not None:
            return v, "boxed"
    nums = numbers_in(text)
    if nums:
        return nums[-1], "last_number_fallback"
    return None, "no_number"


def is_correct(predicted, expected, tolerance) -> bool:
    if predicted is None:
        return False
    return abs(predicted - expected) <= tolerance + 1e-6


def close(a: float, b: float, rel: float = 0.005, abs_tol: float = 0.011) -> bool:
    return abs(a - b) <= max(abs_tol, rel * abs(b))


# ---- arithmetic-slip detection -----------------------------------------
# Finds written equations such as "150 + 90 + 75 = 315" or "275 / 24 ≈ 11.46"
# and re-computes the left side. Rounding up/down to a whole number is NOT a
# slip (that is how pack/box problems are meant to be solved).
_EXPR = r"(?:\(?\s*\d+(?:\.\d+)?\s*\)?\s*[-+*/]\s*)+\(?\s*\d+(?:\.\d+)?\s*\)?"
_EQ_RE = re.compile(r"(" + _EXPR + r")\s*(?:=|≈)\s*\$?\s*(" + NUM + ")")


def written_equations(text: str):
    """Yield (expression, written_result, true_result, line) for each
    simple equation in the text."""
    t = normalise(text).replace("$", "")
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    for line in t.splitlines():
        for m in _EQ_RE.finditer(line):
            expr, rhs = m.group(1), to_float(m.group(2))
            if rhs is None or not re.fullmatch(r"[\d.\s+\-*/()]+", expr):
                continue
            try:
                true = eval(expr, {"__builtins__": {}}, {})  # digits/ops only
            except Exception:  # noqa: BLE001
                continue
            yield expr.strip(), rhs, float(true), line.strip()


def arithmetic_slips(text: str):
    """List of equations whose written result is wrong."""
    import math
    slips = []
    for expr, written, true, line in written_equations(text):
        if close(written, true):
            continue
        if written in (math.ceil(true), math.floor(true)):
            continue  # legitimate rounding to a whole unit
        slips.append({"expression": expr, "written": written,
                      "correct": round(true, 4), "line": line})
    return slips
