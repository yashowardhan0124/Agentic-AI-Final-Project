"""
Builds CoT_Project_Presentation_v2.pptx from summary.json (written by
report.py). Every number, chart and finding on the slides comes from the
saved results, so the deck always matches the data. Speaker notes with
talking points are added to every slide.

Usage:
    python build_deck.py          (after report.py)
    python build_deck.py --mock   (deck from mock data: every slide is
                                   stamped MOCK DATA)

Requires: pip install python-pptx
"""

import json
import os

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

import config
import prompts
import report
from problems import PROBLEMS, PROBLEMS_BY_ID, format_value

DECK_NAME = "CoT_Project_Presentation_v2.pptx"

# ---- palette (matches the v1 deck) ----------------------------------------
NAVY, NAVY_DEEP, NAVY_MID = "1E2761", "141A45", "39408A"
ICE, WHITE = "CADCFC", "FFFFFF"
INK, MUTED, FAINT = "1B1F3B", "5B6088", "9AA0C3"
CARD, CARD2, BORDER = "F4F6FB", "EEF1FA", "D6DCEF"
GREEN, GREEN_BG, GREEN_ON_DARK = "1E8F5F", "E4F5EC", "8EE7B8"
RED, RED_BG, RED_ON_DARK = "C0392B", "FCEAE8", "F0A6A0"
AMBER, AMBER_BG = "A86400", "FFF3DC"
BLUE, BLUE_BG, BLUE_ON_DARK = "3653B8", "E6ECFB", "9DB4FF"
HEAD, BODY = "Cambria", "Calibri"

COND_COLOR = {"standard": RED, "cot": GREEN, "structured": BLUE}
COND_BG = {"standard": RED_BG, "cot": GREEN_BG, "structured": BLUE_BG}
COND_ON_DARK = {"standard": RED_ON_DARK, "cot": GREEN_ON_DARK, "structured": BLUE_ON_DARK}
SHORT = {"standard": "Standard", "cot": "Zero-shot CoT", "structured": "Structured CoT"}

W, H = 13.333, 7.5


def rgb(h):
    return RGBColor.from_string(h)


def pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


# ---- drawing helpers --------------------------------------------------------
def rect(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE, radius=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    st = s._element.find(qn("p:style"))
    if st is not None:  # drop theme style -> flat shapes, no shadow
        s._element.remove(st)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(0.75)
    else:
        s.line.fill.background()
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def card(slide, x, y, w, h, fill=CARD, line=None):
    return rect(slide, x, y, w, h, fill, line, MSO_SHAPE.ROUNDED_RECTANGLE, 0.06)


def text(slide, x, y, w, h, content, size=12, color=INK, bold=False, font=BODY,
         align="l", anchor="t", italic=False, spacing=None, line_spacing=None):
    """content: str, or list of paragraphs; a paragraph is a str or a list of
    (text, {overrides}) runs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    paras = content if isinstance(content, list) else [content]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        if line_spacing:
            p.line_spacing = line_spacing
        runs = para if isinstance(para, list) else [(para, {})]
        for txt, o in runs:
            r = p.add_run()
            r.text = txt
            f = r.font
            f.name = o.get("font", font)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", italic)
            f.color.rgb = rgb(o.get("color", color))
            sp = o.get("spacing", spacing)
            if sp:
                r._r.get_or_add_rPr().set("spc", str(int(sp)))
    return tb


def circle_num(slide, x, y, d, label, fill, color=WHITE, size=12):
    c = rect(slide, x, y, d, d, fill, shape=MSO_SHAPE.OVAL)
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.name = Pt(size), True, BODY
    r.font.color.rgb = rgb(color)
    return c


def pill(slide, x, y, w, h, label, fg, bg, size=10, bold=True):
    s = rect(slide, x, y, w, h, bg, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.25)
    tf = s.text_frame
    tf.margin_left = tf.margin_right = Inches(0.08)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size, r.font.bold, r.font.name = Pt(size), bold, BODY
    r.font.color.rgb = rgb(fg)
    return s


class Deck:
    def __init__(self, summary):
        self.s = summary
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    def new(self, dark=False, notes=""):
        slide = self.prs.slides.add_slide(self.blank)
        self.n += 1
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = rgb(NAVY if dark else WHITE)
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
        return slide

    def header(self, slide, kicker, title, dark=False, sub=None):
        text(slide, 0.6, 0.5, 9, 0.3, kicker.upper(), 10, ICE if dark else NAVY_MID,
             bold=True, spacing=300)
        text(slide, 0.6, 0.82, 12.1, 0.7, title, 28, WHITE if dark else INK, font=HEAD, bold=True)
        if sub:
            text(slide, 0.6, 1.45, 12, 0.35, sub, 12, ICE if dark else MUTED, italic=True)

    def finish(self, slide, dark=False):
        text(slide, 12.2, 7.0, 0.6, 0.25, f"{self.n:02d}", 9, FAINT if not dark else NAVY_MID, align="r")
        if self.s["mock"]:
            rect(slide, 0, 0, W, 0.32, RED)
            text(slide, 0.3, 0.06, W - 0.6, 0.22,
                 "MOCK DATA - pipeline test only, NOT real model results. "
                 "Run  python run_all.py  with Ollama to build the real deck.",
                 10, WHITE, bold=True, align="c")


# ---- chart styling ----------------------------------------------------------
def style_axis_text(axis, color, size=10):
    axis.tick_labels.font.size = Pt(size)
    axis.tick_labels.font.color.rgb = rgb(color)
    axis.tick_labels.font.name = BODY


def style_chart(chart, label_color, grid_color, legend=True):
    chart.font.name = BODY
    chart.font.size = Pt(10)
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.color.rgb = rgb(label_color)
        chart.legend.font.size = Pt(11)
    va, ca = chart.value_axis, chart.category_axis
    style_axis_text(va, label_color)
    style_axis_text(ca, label_color)
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb(grid_color)
    va.major_gridlines.format.line.width = Pt(0.5)
    va.format.line.fill.background()
    ca.format.line.color.rgb = rgb(grid_color)
    ca.has_major_gridlines = False


# =============================================================================
def build(summary, out_path):
    d = Deck(summary)
    s = summary
    C = s["conditions"]
    conds = [c for c in config.CONDITIONS if c in C]
    runs = s["runs"]
    model = s["meta"].get("model_tag") or s["meta"].get("model", {}).get("model", "qwen2.5:3b")
    total_answers = sum(C[c]["trials"] for c in conds)
    std, cot = C["standard"], C["cot"]
    stc = C.get("structured")
    cmp_sc = s["comparisons"]["standard_vs_cot"]
    fix = s["fix"]

    # ---- 1. title ----------------------------------------------------------
    sl = d.new(dark=True, notes=(
        "v2 of the project. Since the first evaluation I tripled the problem set, ran every "
        f"problem {runs} times per prompt, added a statistical test, automated the error "
        "analysis, and actually tested a prompt fix on every problem."))
    rect(sl, 9.6, -1.6, 5.2, 5.2, NAVY_DEEP, shape=MSO_SHAPE.OVAL)
    rect(sl, -1.4, 5.2, 3.6, 3.6, NAVY_DEEP, shape=MSO_SHAPE.OVAL)
    text(sl, 0.8, 1.15, 9, 0.3, "REASONING FRAMEWORK DEEP-DIVE  ·  v2", 11, ICE, bold=True, spacing=300)
    text(sl, 0.8, 1.6, 9.5, 1.9, ["Chain-of-Thought Math", "Word Problem Solver"], 46, WHITE,
         font=HEAD, bold=True)
    text(sl, 0.8, 3.55, 9.5, 0.4,
         "With error analysis: measuring, explaining, and fixing what step-by-step prompting changes",
         15, ICE)
    rect(sl, 0.8, 4.55, 9.6, 0.02, NAVY_MID)
    stats_row = [(str(s["n_problems"]), "PROBLEMS TESTED"), (str(len(conds)), "PROMPTING CONDITIONS"),
                 (str(total_answers), "GRADED ANSWERS"), (model, "MODEL, VIA OLLAMA")]
    for i, (big, small) in enumerate(stats_row):
        x = 0.8 + i * 2.45
        text(sl, x, 4.8, 2.4, 0.6, big, 28, WHITE, font=HEAD, bold=True)
        text(sl, x, 5.45, 2.4, 0.3, small, 9, ICE, bold=True, spacing=150)
    d.finish(sl, True)

    # ---- 2. the question -----------------------------------------------------
    sl = d.new(notes=(
        "The core question is unchanged: does telling a model to think step by step fix its math? "
        "v2 adds a third prompt, the structured CoT fix, which I designed from the error analysis."))
    d.header(sl, "The question", "")
    text(sl, 0.6, 1.0, 6.2, 2.0, ["Does telling a model to", "“think step by step”",
                                  "actually fix its math?"], 32, INK, font=HEAD, bold=True)
    text(sl, 0.6, 3.6, 5.9, 2.0,
         f"A small 3B-parameter model solved the same {s['n_problems']} multi-step word problems "
         f"under three different prompts, {runs} times each. Same model, same questions: "
         "only the instruction changed.", 14, MUTED, line_spacing=1.15)
    quotes = [
        ("standard", "STANDARD PROMPTING", "“Give only the final numeric answer. Do not show any work.”"),
        ("cot", "ZERO-SHOT CHAIN-OF-THOUGHT", "“Let’s think step by step. Work through the problem carefully, then answer.”"),
        ("structured", "STRUCTURED CoT (THE FIX)", "“Given numbers → Rules → one operation per step → Check → Final Answer”"),
    ]
    for i, (c, lab, q) in enumerate(quotes):
        y = 0.9 + i * 2.0
        card(sl, 7.2, y, 5.5, 1.75, COND_BG[c])
        text(sl, 7.5, y + 0.25, 5.0, 0.3, lab, 10, COND_COLOR[c], bold=True, spacing=200)
        text(sl, 7.5, y + 0.62, 5.0, 1.0, q, 15, INK, font=HEAD, italic=True)
    d.finish(sl)

    # ---- 3. methodology ------------------------------------------------------
    sl = d.new(notes=(
        "Same five steps as the brief. What changed since v1 is in the strip at the bottom: "
        "more problems, repeated runs, real statistics, automatic error categories, and a fix "
        "that is tested on every problem so we can see what it breaks as well as what it fixes."))
    d.header(sl, "Methodology", "Five steps, run end to end by one command")
    steps = [
        ("Collect problems", f"{s['n_problems']} multi-step problems: the 5 originals plus 10 built around known traps"),
        ("Standard prompting", "Ask for the final number only, with no reasoning shown"),
        ("Zero-shot CoT", "Add “let’s think step by step” and re-run everything"),
        ("Root-cause analysis", "Every wrong answer auto-classified; hardest case traced step by step"),
        ("Propose + test a fix", "Structured CoT on all problems: count what it fixes and what it breaks"),
    ]
    cw = (W - 1.2 - 4 * 0.2) / 5
    for i, (t, b) in enumerate(steps):
        x = 0.6 + i * (cw + 0.2)
        card(sl, x, 1.95, cw, 2.75)
        circle_num(sl, x + 0.25, 2.2, 0.5, str(i + 1), NAVY, size=14)
        text(sl, x + 0.25, 2.95, cw - 0.5, 0.35, t, 14, INK, bold=True, font=HEAD)
        text(sl, x + 0.25, 3.45, cw - 0.45, 1.2, b, 11, MUTED, line_spacing=1.1)
    card(sl, 0.6, 5.0, W - 1.2, 1.75, CARD2)
    text(sl, 0.9, 5.2, 6, 0.3, "WHAT CHANGED SINCE v1", 10, NAVY_MID, bold=True, spacing=250)
    chips = ["5 → 15 problems", f"1 → {runs} runs per prompt", "95% CI + McNemar test",
             "Automatic error taxonomy", "Fix tested on every problem"]
    x = 0.9
    for ch in chips:
        w_ = 0.083 * len(ch) + 0.45
        pill(sl, x, 5.6, w_, 0.42, ch, NAVY, WHITE, size=11)
        x += w_ + 0.15
    text(sl, 0.9, 6.25, 11.5, 0.3,
         f"v1 result for reference: {s['v1_baseline']['standard']} standard vs "
         f"{s['v1_baseline']['cot']} CoT, on 5 problems with one greedy run each.",
         11, MUTED, italic=True)
    d.finish(sl)

    # ---- 4. problems ---------------------------------------------------------
    sl = d.new(notes=(
        "P1 to P5 are the original problems, unchanged. P6 to P15 are new, and each hides one "
        "specific trap: fence-post counting, chained percentages, remainders, a drain working "
        "against two pipes, tiered pricing, an algebra question that asks for a future age, and so on. "
        "Every problem also lists its known wrong answers, which is what lets the error analysis "
        "say exactly which misreading happened."))
    d.header(sl, "Step 1", f"{s['n_problems']} multi-step word problems")
    cw, ch_, gx, gy = (W - 1.2 - 4 * 0.15) / 5, 1.6, 0.15, 0.13
    for i, p in enumerate(PROBLEMS):
        r_, c_ = divmod(i, 5)
        x, y = 0.6 + c_ * (cw + gx), 1.65 + r_ * (ch_ + gy)
        new = p["origin"] == "v2"
        card(sl, x, y, cw, ch_, CARD if new else BLUE_BG)
        pid = p["id"].split("_")[0]
        text(sl, x + 0.18, y + 0.14, 1.5, 0.25,
             [[(pid, {"bold": True, "color": NAVY_MID}),
               ("   NEW" if new else "   ORIGINAL", {"color": GREEN if new else BLUE, "size": 8})]], 9,
             spacing=100)
        text(sl, x + 0.18, y + 0.42, cw - 0.3, 0.3, p["title"], 13, INK, bold=True, font=HEAD)
        text(sl, x + 0.18, y + 0.76, cw - 0.3, 0.3, p["trap_type"], 10, MUTED)
        text(sl, x + 0.18, y + 1.12, cw - 0.3, 0.35, format_value(p["id"], p["answer"]), 15, INK,
             bold=True, font=HEAD)
    d.finish(sl)

    # ---- 5. headline results (dark) -----------------------------------------
    sl = d.new(dark=True, notes=(
        f"Headline numbers pool every run: {std['trials']} answers per prompt. Standard prompting "
        f"got {pct(std['accuracy'])}, zero-shot CoT {pct(cot['accuracy'])}"
        + (f", the structured fix {pct(stc['accuracy'])}" if stc else "") +
        ". The chart shows how often each problem was solved across the runs."))
    d.header(sl, "Steps 2 + 3 + 5 · Results", "Accuracy across every run", dark=True)
    for i, c in enumerate(conds):
        x = 0.6 + i * 3.1
        text(sl, x, 1.55, 3.0, 0.8, pct(C[c]["accuracy"]), 44, COND_ON_DARK[c], font=HEAD, bold=True)
        text(sl, x, 2.35, 3.0, 0.3, SHORT[c].upper(), 10, ICE, bold=True, spacing=150)
        text(sl, x, 2.62, 3.0, 0.3,
             f"{C[c]['correct']}/{C[c]['trials']} answers · greedy {C[c]['greedy_correct']}/{C[c]['greedy_n']}",
             10, ICE)
    p_txt = report.pval(cmp_sc["p_value"])
    card(sl, 9.95, 1.6, 2.8, 1.25, NAVY_DEEP)
    text(sl, 10.15, 1.72, 2.5, 0.3, "STANDARD → CoT", 9, ICE, bold=True, spacing=150)
    text(sl, 10.15, 1.98, 2.5, 0.45,
         f"{100 * (cot['accuracy'] - std['accuracy']):+.0f} pts", 22, WHITE, font=HEAD, bold=True)
    text(sl, 10.15, 2.47, 2.5, 0.3, f"McNemar {p_txt}", 10, ICE)
    cd = CategoryChartData()
    cd.categories = [p["id"].split("_")[0] for p in PROBLEMS]
    for c in conds:
        pp = C[c]["per_problem"]
        cd.add_series(SHORT[c], [100 * pp[p["id"]]["correct"] / max(1, pp[p["id"]]["runs"]) for p in PROBLEMS])
    gf = sl.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(3.05),
                             Inches(12.3), Inches(3.85), cd)
    ch = gf.chart
    style_chart(ch, ICE, NAVY_MID)
    ch.value_axis.maximum_scale, ch.value_axis.minimum_scale = 100, 0
    ch.value_axis.major_unit = 25
    ch.value_axis.tick_labels.number_format = '0"%"'
    ch.value_axis.tick_labels.number_format_is_linked = False
    plot = ch.plots[0]
    plot.gap_width, plot.overlap = 60, 0
    for i, c in enumerate(conds):
        ser = plot.series[i]
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = rgb(COND_ON_DARK[c])
    text(sl, 0.6, 6.95, 9, 0.3, "Bars: % of runs in which each problem was answered correctly",
         9, ICE, italic=True)
    d.finish(sl, True)

    # ---- 6. full breakdown table -------------------------------------------
    sl = d.new(notes=(
        "Every problem under every prompt. Each cell is how many of the runs got it right. Green "
        "means all runs, amber means some, red means none. Full transcripts for every cell are in "
        "outputs/logs."))
    d.header(sl, "Full breakdown", "Every problem, every prompt, every run")
    cols_x = [7.45, 9.3, 11.15]
    hy = 1.55
    for lab, x, w_ in (("PROBLEM", 1.3, 2.5), ("WHAT MAKES IT HARD", 3.85, 2.3), ("ANSWER", 6.2, 1.1)):
        text(sl, x, hy, w_, 0.25, lab, 9, MUTED, bold=True, spacing=150)
    for i, c in enumerate(conds):
        text(sl, cols_x[i], hy, 1.75, 0.25, SHORT[c].upper(), 9, COND_COLOR[c], bold=True,
             spacing=100, align="c")
    rh = 0.322
    for i, p in enumerate(PROBLEMS):
        y = 1.86 + i * rh
        if i % 2 == 0:
            rect(sl, 0.6, y - 0.03, W - 1.2, rh, CARD)
        pill(sl, 0.7, y + 0.025, 0.5, 0.24, p["id"].split("_")[0], WHITE, NAVY, size=8)
        text(sl, 1.3, y + 0.04, 2.5, 0.25, p["title"], 11, INK, bold=True)
        text(sl, 3.85, y + 0.05, 2.3, 0.25, p["trap_type"], 9.5, MUTED)
        text(sl, 6.2, y + 0.04, 1.2, 0.25, format_value(p["id"], p["answer"]), 11, INK)
        for j, c in enumerate(conds):
            pp = C[c]["per_problem"][p["id"]]
            k, n = pp["correct"], pp["runs"]
            fg, bg = (GREEN, GREEN_BG) if k == n else (RED, RED_BG) if k == 0 else (AMBER, AMBER_BG)
            pill(sl, cols_x[j] + 0.25, y + 0.02, 1.25, 0.25, f"{k} / {n}", fg, bg, size=9.5)
    y = 1.86 + len(PROBLEMS) * rh + 0.02
    rect(sl, 0.6, y, W - 1.2, 0.015, BORDER)
    text(sl, 1.3, y + 0.06, 4, 0.3, "Accuracy, all runs", 11, INK, bold=True)
    for j, c in enumerate(conds):
        text(sl, cols_x[j], y + 0.06, 1.75, 0.3, pct(C[c]["accuracy"]), 12, COND_COLOR[c],
             bold=True, align="c")
    d.finish(sl)

    # ---- 7. robustness ---------------------------------------------------------
    sl = d.new(notes=(
        "The obvious challenge to v1 was: five problems, one run, could that be luck? Here every "
        "accuracy has a 95% confidence interval, and the McNemar test compares the two prompts on "
        "the same problem and run, which is the right test for paired yes/no outcomes."))
    d.header(sl, "Is it real?", "Confidence intervals and a paired significance test")
    text(sl, 0.6, 1.7, 6.6, 0.3, "ACCURACY WITH 95% CONFIDENCE INTERVAL", 10, NAVY_MID, bold=True, spacing=200)
    tx, tw = 2.75, 4.5
    for i, c in enumerate(conds):
        y = 2.25 + i * 1.05
        text(sl, 0.6, y + 0.02, 2.1, 0.3, SHORT[c], 13, INK, bold=True)
        text(sl, 0.6, y + 0.34, 2.1, 0.3, f"{C[c]['correct']}/{C[c]['trials']} answers", 10, MUTED)
        rect(sl, tx, y + 0.12, tw, 0.36, CARD2, shape=MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.5
        lo, hi = C[c]["ci95"]
        rect(sl, tx + lo * tw, y + 0.12, max(0.04, (hi - lo) * tw), 0.36, COND_BG[c], line=COND_COLOR[c])
        acc = C[c]["accuracy"]
        rect(sl, tx + acc * tw - 0.04, y + 0.06, 0.08, 0.48, COND_COLOR[c])
        text(sl, tx + tw + 0.15, y + 0.08, 1.4, 0.4, pct(acc), 18, COND_COLOR[c], bold=True, font=HEAD)
        text(sl, tx, y + 0.56, tw, 0.25, f"CI {pct(lo)} – {pct(hi)}", 9, MUTED)
    for k_, lab in ((0, "0%"), (0.5, "50%"), (1, "100%")):
        text(sl, tx + k_ * tw - 0.3, 2.25 + len(conds) * 1.05 - 0.1, 0.6, 0.25, lab, 9, FAINT, align="c")
    gy = 2.25 + len(conds) * 1.05 + 0.35
    card(sl, 0.6, gy, 7.7, 6.75 - gy, CARD)
    text(sl, 0.85, gy + 0.18, 7.2, 6.75 - gy - 0.3,
         [[("How to read it.  ", {"bold": True, "color": INK}),
           ("The thick mark is the measured accuracy; the box is the range the true accuracy "
            "plausibly lies in (95% Wilson interval). Boxes that don't overlap mean a real "
            "difference. McNemar compares the two prompts on the same problem and run, counting only "
            "the cases where they disagree.", {})]], 11, MUTED, line_spacing=1.1)
    stat_cards = [("STANDARD → CoT",
                   f"fixed {cmp_sc['b_right_a_wrong']}, broke {cmp_sc['a_right_b_wrong']}",
                   f"McNemar {report.pval(cmp_sc['p_value'])}")]
    if "cot_vs_structured" in s["comparisons"]:
        c2 = s["comparisons"]["cot_vs_structured"]
        stat_cards.append(("CoT → STRUCTURED FIX", f"fixed {c2['b_right_a_wrong']}, broke {c2['a_right_b_wrong']}",
                           f"McNemar {report.pval(c2['p_value'])}"))
    stat_cards.append(("CoT: ORIGINAL vs NEW PROBLEMS",
                       f"{pct(cot['v1_accuracy'])} vs {pct(cot['v2_accuracy'])}",
                       "the 10 new trap problems are harder"))
    if runs > 1:
        stat_cards.append(("RUN-TO-RUN STABILITY (CoT)",
                           f"{pct(cot['per_run_mean'])} ± {pct(cot['per_run_sd'])}",
                           f"mean ± SD across {runs} runs; majority vote {cot['majority_vote_correct']}/{s['n_problems']}"))
    for i, (k_, big, small) in enumerate(stat_cards):
        y = 1.7 + i * 1.3
        card(sl, 8.6, y, 4.13, 1.15)
        text(sl, 8.85, y + 0.15, 3.7, 0.25, k_, 9, NAVY_MID, bold=True, spacing=150)
        text(sl, 8.85, y + 0.42, 3.7, 0.4, big, 17, INK, bold=True, font=HEAD)
        text(sl, 8.85, y + 0.8, 3.7, 0.25, small, 10, MUTED)
    d.finish(sl)

    # ---- 8. error taxonomy -----------------------------------------------------
    counts = s["error_counts"]
    cats = [k for k in s["categories"] if any(counts.get(c, {}).get(k, 0) for c in conds)]
    cc = counts.get("cot", {})
    top = max(cc.items(), key=lambda kv: kv[1]) if cc else None
    sl = d.new(notes=(
        "Step 4. Every wrong answer is put in exactly one category by error_analysis.py. Known trap "
        "means the answer matched a wrong answer we predicted in advance, so we know which "
        "misreading happened even when no work was shown. Arithmetic slip means a written "
        "equation in the reasoning is wrong, and we can point to the line."))
    d.header(sl, "Step 4 · Root-cause analysis", "Why each wrong answer was wrong")
    if cats:
        cd = CategoryChartData()
        cd.categories = [s["categories"][k] for k in reversed(cats)]
        for c in conds:
            cd.add_series(SHORT[c], [counts.get(c, {}).get(k, 0) for k in reversed(cats)])
        gf = sl.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.6),
                                 Inches(8.1), Inches(5.3), cd)
        ch = gf.chart
        style_chart(ch, MUTED, BORDER)
        ch.legend.font.color.rgb = rgb(INK)
        style_axis_text(ch.category_axis, INK, 11)
        plot = ch.plots[0]
        plot.gap_width, plot.overlap = 50, 0
        plot.has_data_labels = True
        plot.data_labels.font.size = Pt(9)
        plot.data_labels.font.color.rgb = rgb(INK)
        plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
        for i, c in enumerate(conds):
            plot.series[i].format.fill.solid()
            plot.series[i].format.fill.fore_color.rgb = rgb(COND_COLOR[c])
    card(sl, 8.95, 1.7, 3.8, 5.1, CARD2)
    text(sl, 9.2, 1.9, 3.3, 0.3, "WHAT IT SHOWS", 10, NAVY_MID, bold=True, spacing=200)
    bullets = []
    sc_std = counts.get("standard", {})
    if sc_std:
        tot = sum(sc_std.values())
        trap_n = sc_std.get("trap", 0) + sc_std.get("stopped_early", 0)
        bullets.append(f"Standard prompting: {trap_n} of {tot} wrong answers match a predictable "
                       f"misreading; the other {tot - trap_n} match nothing, they are guesses.")
    if top:
        bullets.append(f"Zero-shot CoT: the biggest category is “{s['categories'][top[0]]}” "
                       f"({top[1]} of {sum(cc.values())}).")
    elif "cot" in counts:
        bullets.append("Zero-shot CoT made no errors.")
    sc_fix = counts.get("structured")
    if sc_fix is not None:
        bullets.append(f"Structured fix: {sum(sc_fix.values())} wrong answers in total, vs "
                       f"{sum(cc.values())} for plain CoT.")
    text(sl, 9.2, 2.35, 3.35, 2.4, [[("•  " + b, {})] for b in bullets], 11.5, INK,
         line_spacing=1.1)
    defs = {"trap": "answer equals a wrong answer predicted in advance",
            "stopped_early": "answer equals a correct intermediate value",
            "arithmetic_slip": "a written equation in the reasoning is wrong",
            "wrong_step": "first correct intermediate value that never appears",
            "answer_selection": "right value in the reasoning, another one reported",
            "no_answer": "no number could be extracted",
            "unexplained": "no work shown and matches nothing known"}
    shown = [k for k in cats if k in defs][:5]
    if shown:
        text(sl, 9.2, 4.75, 3.3, 0.3, "HOW A CATEGORY IS DECIDED", 9, NAVY_MID, bold=True, spacing=150)
        text(sl, 9.2, 5.05, 3.35, 1.7,
             [[(s["categories"][k] + ": ", {"bold": True, "color": INK}), (defs[k], {})] for k in shown],
             9.5, MUTED, line_spacing=1.05)
    d.finish(sl)

    # ---- 9. hardest case trace ---------------------------------------------
    sc = s["showcase"]
    if sc:
        f = sc["failure"]
        p = PROBLEMS_BY_ID[sc["problem_id"]]
        sl = d.new(notes=(
            f"This answers 'show me the exact step'. The hardest problem for CoT was {sc['title']}, "
            f"solved in {sc['cot_pass']} of {sc['runs']} runs. Middle column: the correct chain, "
            "with a tick where that value appears in the model's reasoning and a cross where it "
            f"doesn't. Right: the diagnosis and the line where it left the correct path. Open "
            f"{f['log_file']} to show the full transcript."))
        d.header(sl, "Step 4 · Hardest case, traced",
                 "Exactly where the reasoning went wrong",
                 sub=f"{sc['title']} ({p['trap_type'].lower()}): correct answer "
                     f"{format_value(p['id'], sc['answer'])}; CoT correct in {sc['cot_pass']}/{sc['runs']} runs; "
                     f"showing run {f['run']}")
        # left: standard
        ok = sc["standard_correct"]
        card(sl, 0.6, 2.0, 2.75, 4.8, GREEN_BG if ok else RED_BG)
        text(sl, 0.8, 2.2, 2.4, 0.3, "STANDARD PROMPTING", 9, GREEN if ok else RED, bold=True, spacing=150)
        text(sl, 0.8, 2.5, 2.4, 0.5, "No visible reasoning, straight to an answer", 10, MUTED)
        text(sl, 0.7, 3.35, 2.55, 1.0, format_value(p["id"], sc["standard_pred"]), 36,
             GREEN if ok else RED, font=HEAD, bold=True, align="c")
        text(sl, 0.8, 4.5, 2.4, 0.3, "correct" if ok else "wrong", 11, GREEN if ok else RED,
             bold=True, align="c")
        # middle: step trace
        trace = f.get("step_trace") or []
        card(sl, 3.55, 2.0, 5.15, 4.8, CARD)
        text(sl, 3.8, 2.2, 4.7, 0.3, f"ZERO-SHOT CoT · RUN {f['run']} · ANSWERED "
             f"{format_value(p['id'], f['predicted']).upper()}", 9, NAVY_MID, bold=True, spacing=100)
        n_steps = max(1, len(trace))
        rh = min(0.62, 4.05 / n_steps)
        bs = f.get("breakdown_step")
        for i, st in enumerate(trace):
            y = 2.6 + i * rh
            good = st["found"] and not (bs and i + 1 >= bs)
            circle_num(sl, 3.8, y + 0.04, 0.36, "✓" if good else "✗",
                       GREEN if good else RED, size=12)
            text(sl, 4.3, y + 0.02, 3.2, 0.3, st["label"].split("(")[0].strip().capitalize(), 11, INK, bold=True)
            if "(" in st["label"]:
                text(sl, 4.3, y + 0.27, 3.2, 0.25, "(" + st["label"].split("(", 1)[1], 9, MUTED)
            text(sl, 7.4, y + 0.04, 1.15, 0.3, f"{st['value']:g}", 12, INK, bold=True, align="r")
        text(sl, 3.8, 6.5, 4.7, 0.25, "✓ value appears in the model's reasoning   ✗ it never does",
             8.5, MUTED, italic=True)
        # right: diagnosis + fix
        card(sl, 8.9, 2.0, 3.83, 4.8, CARD2)
        text(sl, 9.15, 2.2, 3.4, 0.3, "DIAGNOSIS", 9, RED, bold=True, spacing=200)
        text(sl, 9.15, 2.5, 3.4, 0.35, s["categories"][f["category"]], 15, INK, bold=True, font=HEAD)
        text(sl, 9.15, 2.95, 3.4, 1.1, f["detail"][0].upper() + f["detail"][1:], 11, MUTED, line_spacing=1.1)
        if f.get("evidence_line"):
            text(sl, 9.15, 4.05, 3.4, 0.25, "FIRST LINE OFF THE CORRECT PATH", 8, NAVY_MID, bold=True, spacing=100)
            ev = f["evidence_line"]
            text(sl, 9.15, 4.32, 3.4, 0.9, "“" + (ev[:110] + "…" if len(ev) > 110 else ev) + "”",
                 10, INK, italic=True, font="Consolas")
        text(sl, 9.15, 5.35, 3.4, 0.4, "Transcript: " + f["log_file"].replace("\\", "/"), 8.5, MUTED,
             font="Consolas")
        if sc.get("fix_pred") is not None:
            fok = sc["fix_correct"]
            pill(sl, 9.15, 5.85, 3.35, 0.6,
                 f"Structured fix, same run: {format_value(p['id'], sc['fix_pred'])} "
                 f"{'✓' if fok else '✗'}", GREEN if fok else RED, GREEN_BG if fok else RED_BG, size=11)
        d.finish(sl)
    else:
        sl = d.new(notes="Plain CoT made no errors, so there is no CoT reasoning chain to trace.")
        d.header(sl, "Step 4 · Hardest case", "Zero-shot CoT made no errors")
        text(sl, 0.6, 2.0, 11, 1, "Every CoT answer was correct, so the per-failure diagnosis "
             "in error_analysis.md covers the standard-prompting errors only.", 16, MUTED)
        d.finish(sl)

    # ---- 10. the fix -------------------------------------------------------------
    sl = d.new(notes=(
        "Step 5. The fix is designed from the Step 4 categories: each line of the prompt targets one "
        "kind of error. It was run on every problem and run, not just on the failures, so it can be "
        "caught breaking answers that plain CoT got right."))
    d.header(sl, "Step 5 · Proposed fix, tested", "Structured CoT: what it fixed, and what it broke")
    if fix:
        boxes = [("FIXED", fix["fixed"], f"of {fix['cot_failures']} CoT failures", GREEN, GREEN_BG),
                 ("BROKE", fix["broken"], "CoT answers that were right", RED, RED_BG),
                 ("STILL WRONG", fix["still_wrong"], "wrong under both prompts", MUTED, CARD2)]
        for i, (lab, num, sub, fg, bg) in enumerate(boxes):
            x = 0.6 + i * 2.35
            card(sl, x, 1.75, 2.2, 2.2, bg)
            text(sl, x + 0.25, 1.95, 1.8, 0.3, lab, 10, fg, bold=True, spacing=200)
            text(sl, x + 0.25, 2.3, 1.8, 0.9, str(num), 48, fg, bold=True, font=HEAD)
            text(sl, x + 0.25, 3.3, 1.8, 0.5, sub, 10, MUTED)
        net = fix["fixed"] - fix["broken"]
        card(sl, 0.6, 4.2, 6.85, 2.6, CARD)
        text(sl, 0.9, 4.4, 6.3, 0.3, "NET EFFECT", 10, NAVY_MID, bold=True, spacing=200)
        text(sl, 0.9, 4.75, 6.3, 0.6,
             [[(pct(cot["accuracy"]), {"color": GREEN}), ("  →  ", {"color": MUTED}),
               (pct(stc["accuracy"]) if stc else "n/a", {"color": BLUE}),
               (f"   ({net:+d} answers)", {"size": 16, "color": MUTED, "bold": False})]],
             34, INK, bold=True, font=HEAD)
        verdict = ("significant" if fix["p_value"] < 0.05 else "not statistically significant")
        text(sl, 0.9, 5.6, 6.3, 1.1,
             f"Plain CoT vs structured CoT on the same {stc['trials'] if stc else 0} problem-runs. "
             f"McNemar {report.pval(fix['p_value'])}: {verdict}.", 12, MUTED, line_spacing=1.1)
    rows = [("Given numbers", "Wrong / missing step", "list every value before using it"),
            ("Rules", "Fell into a known trap", "state rounding, discounts, what's asked"),
            ("One operation per step", "Arithmetic slip", "small, checkable calculations"),
            ("Check", "Answered a sub-question", "re-verify + confirm the quantity asked")]
    card(sl, 7.7, 1.75, 5.03, 5.05, CARD2)
    text(sl, 7.95, 1.95, 4.6, 0.3, "EACH PROMPT LINE TARGETS ONE ERROR TYPE", 10, NAVY_MID, bold=True, spacing=150)
    for i, (line, target, how) in enumerate(rows):
        y = 2.45 + i * 1.05
        pill(sl, 7.95, y, 1.9, 0.38, line, WHITE, BLUE, size=10)
        text(sl, 10.0, y - 0.02, 2.6, 0.3, target, 12, INK, bold=True)
        text(sl, 10.0, y + 0.28, 2.6, 0.5, how, 10, MUTED)
    d.finish(sl)

    # ---- 11. cost --------------------------------------------------------------
    if std["mean_output_tokens"]:
        sl = d.new(notes=(
            "Reasoning isn't free. Output tokens and wall-clock time per answer, measured from "
            "Ollama on this machine. This is the trade-off a deployment would have to weigh."))
        d.header(sl, "Trade-off", "What the extra reasoning costs")
        cd = CategoryChartData()
        cd.categories = [SHORT[c] for c in conds]
        cd.add_series("Mean output tokens per answer", [round(C[c]["mean_output_tokens"] or 0) for c in conds])
        gf = sl.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.65),
                                 Inches(7.4), Inches(5.2), cd)
        ch = gf.chart
        style_chart(ch, MUTED, BORDER, legend=False)
        style_axis_text(ch.category_axis, INK, 12)
        ch.has_title = True
        ch.chart_title.text_frame.text = "Mean output tokens per answer"
        tr = ch.chart_title.text_frame.paragraphs[0].runs[0]
        tr.font.size, tr.font.bold, tr.font.name = Pt(12), True, BODY
        tr.font.color.rgb = rgb(INK)
        plot = ch.plots[0]
        plot.gap_width = 90
        plot.has_data_labels = True
        plot.data_labels.font.size = Pt(12)
        plot.data_labels.font.bold = True
        plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
        for i, c in enumerate(conds):
            pt = plot.series[0].points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(COND_COLOR[c])
        for i, c in enumerate(conds):
            y = 1.75 + i * 1.7
            card(sl, 8.3, y, 4.43, 1.5, COND_BG[c])
            text(sl, 8.55, y + 0.15, 4, 0.3, SHORT[c].upper(), 10, COND_COLOR[c], bold=True, spacing=150)
            text(sl, 8.55, y + 0.45, 4, 0.5,
                 [[(pct(C[c]["accuracy"]), {}), ("  accuracy", {"size": 12, "bold": False, "color": MUTED})]],
                 24, INK, bold=True, font=HEAD)
            text(sl, 8.55, y + 1.0, 4, 0.3,
                 f"{C[c]['mean_output_tokens']:.0f} tokens · {C[c]['mean_latency_s']:.1f} s per answer",
                 11, MUTED)
        d.finish(sl)

    # ---- 12. key findings (dark) --------------------------------------------
    fnd = s["findings"]
    sl = d.new(dark=True, notes="The findings are generated from the numbers, so none of them claims more than the data supports.")
    rect(sl, -1.5, -1.5, 3.6, 3.6, NAVY_DEEP, shape=MSO_SHAPE.OVAL)
    d.header(sl, "Key findings", "What the data says", dark=True)
    rh = min(1.1, 5.4 / max(1, len(fnd)))
    for i, (t, b) in enumerate(fnd):
        y = 1.75 + i * rh
        circle_num(sl, 0.7, y + 0.02, 0.42, str(i + 1), NAVY_MID, color=WHITE, size=12)
        text(sl, 1.35, y, 11.3, 0.35, t, 15, WHITE, bold=True, font=HEAD)
        text(sl, 1.35, y + 0.38, 11.3, rh - 0.35, b, 12, ICE, line_spacing=1.05)
    d.finish(sl, True)

    # ---- 13. limitations -----------------------------------------------------
    sl = d.new(notes="Being upfront about what this experiment cannot claim, and what I would do next.")
    d.header(sl, "Honest scope", "Limitations and next steps")
    for j, (lab, items, fg, bg) in enumerate((("LIMITATIONS", report.LIMITATIONS, RED, RED_BG),
                                              ("NEXT STEPS", report.NEXT_STEPS, GREEN, GREEN_BG))):
        x = 0.6 + j * 6.2
        card(sl, x, 1.75, 5.95, 5.0, CARD)
        text(sl, x + 0.3, 1.95, 5, 0.3, lab, 10, fg, bold=True, spacing=250)
        for i, it in enumerate(items):
            y = 2.45 + i * 1.05
            circle_num(sl, x + 0.3, y + 0.02, 0.36, str(i + 1), fg, size=11)
            text(sl, x + 0.85, y, 4.8, 0.95, it, 13, INK, line_spacing=1.1)
    d.finish(sl)

    # ---- 14. jury Q&A --------------------------------------------------------
    qas = report.qa(s)
    sl = d.new(notes="Prepared answers to the questions I expect. Every number here comes from outputs/summary.json.")
    d.header(sl, "Anticipated questions", "Jury Q&A")
    for i, (q, a) in enumerate(qas[:4]):
        r_, c_ = divmod(i, 2)
        x, y = 0.6 + c_ * 6.15, 1.65 + r_ * 2.65
        card(sl, x, y, 5.98, 2.5, CARD)
        text(sl, x + 0.25, y + 0.18, 0.6, 0.3, f"Q{i + 1}", 13, NAVY, bold=True, font=HEAD)
        text(sl, x + 0.8, y + 0.18, 4.95, 0.55, q, 11.5, INK, italic=True, font=HEAD)
        rect(sl, x + 0.25, y + 0.8, 5.48, 0.012, BORDER)
        text(sl, x + 0.25, y + 0.92, 5.5, 1.5, a, 11, MUTED, line_spacing=1.05)
    d.finish(sl)

    # ---- 15. closing (dark) ---------------------------------------------------
    sl = d.new(dark=True, notes="Close on the headline number and the honest caveat.")
    rect(sl, 10.2, 4.3, 4.6, 4.6, NAVY_DEEP, shape=MSO_SHAPE.OVAL)
    text(sl, 0.8, 2.4, 11.5, 1.6, ["Same model. Same problems.",
                                   "The instruction made the difference." if cot["accuracy"] > std["accuracy"]
                                   else "The instruction alone wasn't enough."],
         38, WHITE, font=HEAD, bold=True)
    line = f"{pct(std['accuracy'])}  →  {pct(cot['accuracy'])} with zero-shot CoT"
    if stc:
        line += f"  →  {pct(stc['accuracy'])} with the structured fix"
    text(sl, 0.8, 4.2, 11.5, 0.4, line, 16, ICE)
    text(sl, 0.8, 6.75, 11.5, 0.3,
         f"{model}  ·  Ollama  ·  {s['n_problems']} problems × {runs} runs × {len(conds)} prompts"
         "  ·  every transcript in outputs/logs/", 10, ICE)
    d.finish(sl, True)

    d.prs.save(out_path)
    return d.n


def main(argv=None):
    args = config.base_parser(__doc__).parse_args(argv)
    out_dir = config.output_dir(args.mock)
    path = os.path.join(out_dir, "summary.json")
    if not os.path.exists(path):
        raise SystemExit("summary.json not found. Run report.py first.")
    with open(path, encoding="utf-8") as f:
        summary = json.load(f)
    out_path = os.path.join(out_dir, DECK_NAME)
    n = build(summary, out_path)
    print(f"Saved {out_path} ({n} slides)" + ("  [MOCK DATA]" if summary["mock"] else ""))


if __name__ == "__main__":
    main()
