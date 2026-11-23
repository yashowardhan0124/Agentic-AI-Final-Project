"""
Unit tests -- no Ollama needed. Run from the project folder:

    python -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from error_analysis import classify  # noqa: E402
from grading import arithmetic_slips, extract_answer, is_correct  # noqa: E402
from problems import PROBLEMS, PROBLEMS_BY_ID  # noqa: E402
from stats import mcnemar_exact, wilson  # noqa: E402


class TestExtraction(unittest.TestCase):
    def check(self, text, expected):
        value, _ = extract_answer(text)
        self.assertIsNotNone(value, text)
        self.assertAlmostEqual(value, expected, places=4, msg=text)

    def test_plain(self):
        self.check("Final Answer: 216", 216)

    def test_dollar_and_commas(self):
        self.check("Final Answer: $1,234.50", 1234.50)

    def test_markdown_bold(self):
        self.check("**Final Answer:** 148.5", 148.5)

    def test_boxed(self):
        self.check("so the answer is \\boxed{46.80}", 46.80)

    def test_boxed_inside_final_line(self):
        self.check("Final Answer: \\boxed{550}", 550)

    def test_dollar_amount_beats_count(self):
        self.check("Final Answer: 12 boxes, costing $216", 216)

    def test_units_after_number(self):
        self.check("Final Answer: 216 dollars", 216)

    def test_number_on_next_line(self):
        self.check("Final Answer:\n104", 104)

    def test_last_final_answer_wins(self):
        self.check("Final Answer: 5\nWait, recheck.\nFinal Answer: 216", 216)

    def test_fallback_is_flagged(self):
        value, method = extract_answer("The cost is 216.")
        self.assertEqual((value, method), (216, "last_number_fallback"))

    def test_no_number(self):
        self.assertEqual(extract_answer("I don't know")[0], None)


class TestGrading(unittest.TestCase):
    def test_tolerance(self):
        self.assertTrue(is_correct(148.4, 148.5, 0.5))
        self.assertFalse(is_correct(147.9, 148.5, 0.5))
        self.assertFalse(is_correct(None, 1, 0))


class TestArithmeticSlips(unittest.TestCase):
    def test_correct_chain_is_not_a_slip(self):
        self.assertEqual(arithmetic_slips("150 + 90 + 75 = 315 cups"), [])

    def test_latex_is_understood(self):
        self.assertEqual(arithmetic_slips(r"\[ 28 \text{ students} \times 3 = 84 \]"), [])

    def test_rounding_up_is_not_a_slip(self):
        self.assertEqual(arithmetic_slips("275 / 24 = 12 boxes"), [])

    def test_approximation_is_not_a_slip(self):
        self.assertEqual(arithmetic_slips("275 / 24 ≈ 11.46"), [])

    def test_real_slip_is_found(self):
        slips = arithmetic_slips("Cost = 12 × 18 = 226")
        self.assertEqual(len(slips), 1)
        self.assertEqual(slips[0]["correct"], 216)


class TestProblems(unittest.TestCase):
    def test_last_step_is_the_answer(self):
        for p in PROBLEMS:
            self.assertAlmostEqual(p["steps"][-1][1], p["answer"], places=2, msg=p["id"])

    def test_traps_are_wrong_answers(self):
        for p in PROBLEMS:
            for trap in p["traps"]:
                self.assertFalse(is_correct(trap, p["answer"], p["tolerance"]), p["id"])

    def test_ground_truth_arithmetic(self):
        g = {p["id"]: p["answer"] for p in PROBLEMS}
        self.assertEqual(g["P1_cafe_cups"], math.ceil((150 + 90 + 75 - 40) / 24) * 18)
        self.assertAlmostEqual(g["P2_bookstore_discount"], (13 - 13 // 5) * 15 * 0.9)
        self.assertEqual(g["P6_fence_posts"], (60 // 4 + 1) * 12)
        self.assertAlmostEqual(g["P7_jacket_price"], 80 * 1.25 * 0.70 * 1.05)
        self.assertEqual(g["P8_print_job"], 45 * 24 / 18 + ((45 * 24 - 1) // 300) * 5)
        self.assertEqual(g["P9_school_buses"], math.ceil((214 + 17) / 45) * 350)
        self.assertEqual(g["P11_tank_fill"], 600 / (600 / 30 + 600 / 20 - 600 / 60))
        self.assertEqual(g["P12_phone_bill"], 20 + 5 * 8 + 3 * 5)
        self.assertEqual(g["P14_class_average"], (24 * 72 - 4 * 45 + 90 + 78) / 22)
        self.assertAlmostEqual(g["P15_cookie_flour"], math.ceil(250 * 90 / 12 / 1000) * 3.20)
        # P10: simulate the reading schedule day by day
        left, day = 480 - 125, 0
        while left > 0:
            day += 1
            left -= 50 if (day - 1) % 7 in (5, 6) else 35
        self.assertEqual(g["P10_reading_days"], day)
        # P13: brute-force the ages
        d = next(d for d in range(1, 100) if 3 * d + 12 == 2 * (d + 12))
        self.assertEqual(g["P13_ages"], 3 * d + 5)


class TestClassification(unittest.TestCase):
    def trial(self, pid, cond, raw, pred):
        return {"problem_id": pid, "condition": cond, "raw_output": raw,
                "predicted": pred, "run": 0}

    def test_trap(self):
        p = PROBLEMS_BY_ID["P6_fence_posts"]
        out = classify(self.trial(p["id"], "standard", "Final Answer: 180", 180), p)
        self.assertEqual(out["category"], "trap")
        self.assertIn("fence-post", out["detail"])

    def test_stopped_early(self):
        p = PROBLEMS_BY_ID["P5_savings_goal"]
        out = classify(self.trial(p["id"], "cot", "6*45 = 270\nFinal Answer: 270", 270), p)
        self.assertEqual(out["category"], "stopped_early")

    def test_slip(self):
        p = PROBLEMS_BY_ID["P1_cafe_cups"]
        raw = "150 + 90 + 75 = 315\n315 - 40 = 275\n12 boxes\n12 * 18 = 226\nFinal Answer: 226"
        out = classify(self.trial(p["id"], "cot", raw, 226), p)
        self.assertEqual(out["category"], "arithmetic_slip")
        self.assertIn("12 * 18", out["evidence_line"])

    def test_unexplained_guess(self):
        p = PROBLEMS_BY_ID["P1_cafe_cups"]
        out = classify(self.trial(p["id"], "standard", "Final Answer: 5", 5), p)
        self.assertEqual(out["category"], "unexplained")


class TestStats(unittest.TestCase):
    def test_wilson_contains_point(self):
        lo, hi = wilson(54, 75)
        self.assertTrue(lo < 54 / 75 < hi)

    def test_mcnemar(self):
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertLess(mcnemar_exact(20, 2), 0.001)
        self.assertGreater(mcnemar_exact(5, 4), 0.5)


if __name__ == "__main__":
    unittest.main()
