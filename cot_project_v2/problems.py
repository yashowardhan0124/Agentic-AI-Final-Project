"""
Step 1 -- the problem set.

P1-P5 are the original v1 problems, unchanged, so the first run's result
is still reproducible. P6-P15 are new: each one is built around a specific
reasoning trap that small models are known to fall into (fence-post
counting, chained percentages, remainders, rate problems, tiered pricing,
algebra, averages with changing group size, unit conversion + distractors).

Each problem stores:
  question  : exact text shown to the model
  answer    : the correct final value
  tolerance : how close a numeric answer must be to count as correct
  steps     : ground-truth intermediate values, IN ORDER. error_analysis.py
              walks the model's reasoning against these to find the first
              step where it left the correct path.
  traps     : known WRONG answers and the specific mistake that produces
              each one. If a model's answer equals a trap value, we know
              exactly which misreading caused it -- even when the model
              showed no work at all (standard prompting).
  trap_type : one-line description of what makes the problem hard
"""

PROBLEMS = [
    # ------------------------------------------------------------------ v1
    {
        "id": "P1_cafe_cups",
        "title": "Café cups",
        "origin": "v1",
        "trap_type": "Must round boxes up",
        "question": (
            "A café buys cups in boxes of 24. Each box costs $18. "
            "The café needs enough cups for 3 events, needing 150, 90, and 75 "
            "cups respectively. The café already has 40 cups in stock. "
            "How many boxes must the café buy, and what is the total cost? "
            "Give the total cost in dollars as your final answer."
        ),
        "answer": 216,
        "tolerance": 0,
        "steps": [
            ("total cups needed (150+90+75)", 315),
            ("cups still needed after stock (315-40)", 275),
            ("boxes to buy (ceil 275/24)", 12),
            ("total cost (12*18)", 216),
        ],
        "traps": {
            198: "rounded 11.46 boxes DOWN to 11 instead of up",
            206.25: "used 11.46 boxes without rounding up",
            252: "forgot to subtract the 40 cups already in stock (14 boxes)",
            234: "rounded 13.1 boxes down after forgetting the stock",
            12: "reported the number of boxes instead of the cost",
        },
    },
    {
        "id": "P2_bookstore_discount",
        "title": "Bookstore discount",
        "origin": "v1",
        "trap_type": "Buy-4-get-1 + 10% off",
        "question": (
            "A bookstore sells novels for $15 each. They offer a promotion: "
            "buy 4 novels, get a 5th one free. Maria wants 13 novels. After "
            "applying the free-book promotion, she also gets an additional "
            "10% off the total amount she has to pay. How much does she pay "
            "in total, in dollars?"
        ),
        "answer": 148.50,
        "tolerance": 0.5,
        "steps": [
            ("free books earned (groups of 5 in 13)", 2),
            ("books actually paid for (13-2)", 11),
            ("price before discount (11*15)", 165),
            ("final price after 10% off", 148.50),
        ],
        "traps": {
            175.50: "ignored the free-book promotion (10% off all 13 books)",
            165: "forgot the extra 10% discount",
            135: "counted 3 free books (13/4 rounded) instead of 2",
        },
    },
    {
        "id": "P3_road_trip_fuel",
        "title": "Road-trip fuel",
        "origin": "v1",
        "trap_type": "2-step baseline",
        "question": (
            "A car gets 25 miles per gallon. Gas costs $4.00 per gallon. "
            "The driver starts with a full tank and drives a total of 650 "
            "miles over the trip. Based on the total fuel consumed for the "
            "whole 650-mile trip, how much does the driver spend on gas, "
            "in dollars?"
        ),
        "answer": 104,
        "tolerance": 0,
        "steps": [
            ("total gallons used (650/25)", 26),
            ("total cost (26*4.00)", 104),
        ],
        "traps": {
            26: "reported gallons instead of dollars",
        },
    },
    {
        "id": "P4_classroom_supplies",
        "title": "Classroom supplies",
        "origin": "v1",
        "trap_type": "Two pack-roundings",
        "question": (
            "A teacher orders pencils and pens for 28 students. Each student "
            "needs 3 pencils and 2 pens. Pencils come in packs of 12 for "
            "$2.40 per pack. Pens come in packs of 10 for $5.00 per pack. "
            "Packs cannot be split, so partial packs must still be bought in "
            "full. What is the total cost, in dollars?"
        ),
        "answer": 46.80,
        "tolerance": 0.1,
        "steps": [
            ("pencils needed (28*3)", 84),
            ("pencil packs (ceil 84/12)", 7),
            ("pencil cost (7*2.40)", 16.80),
            ("pens needed (28*2)", 56),
            ("pen packs (ceil 56/10)", 6),
            ("pen cost (6*5.00)", 30.00),
            ("total cost (16.80+30.00)", 46.80),
        ],
        "traps": {
            44.80: "used 5.6 pen packs instead of rounding up to 6",
            41.80: "rounded 5.6 pen packs DOWN to 5",
            31.80: "bought pens for 28 instead of 56 (forgot 2 per student)",
            37.20: "bought pencils for 28 instead of 84 (forgot 3 per student)",
        },
    },
    {
        "id": "P5_savings_goal",
        "title": "Savings goal",
        "origin": "v1",
        "trap_type": "Rate changes mid-way",
        "question": (
            "Aisha starts with $0 and saves $45 per week. After 6 weeks, she "
            "spends $80 on a gift. She then doubles her weekly savings rate "
            "for the next 4 weeks. How much money does she have saved after "
            "these 10 weeks total, in dollars?"
        ),
        "answer": 550,
        "tolerance": 0,
        "steps": [
            ("savings after 6 weeks (6*45)", 270),
            ("after buying the gift (270-80)", 190),
            ("new weekly rate (45*2)", 90),
            ("savings from next 4 weeks (4*90)", 360),
            ("final total (190+360)", 550),
        ],
        "traps": {
            630: "forgot to subtract the $80 gift",
            370: "did not double the rate (10 weeks at $45, minus $80)",
            450: "ignored the gift and the doubling (10 weeks at $45)",
            190: "stopped after the gift purchase",
        },
    },
    # ------------------------------------------------------------------ v2
    {
        "id": "P6_fence_posts",
        "title": "Fence posts",
        "origin": "v2",
        "trap_type": "Fence-post (off-by-one)",
        "question": (
            "A straight fence is 60 meters long. A post is placed at the very "
            "start, at the very end, and every 4 meters in between. Each post "
            "costs $12. How much do all the posts cost, in dollars?"
        ),
        "answer": 192,
        "tolerance": 0,
        "steps": [
            ("gaps between posts (60/4)", 15),
            ("posts needed (15+1)", 16),
            ("total cost (16*12)", 192),
        ],
        "traps": {
            180: "fence-post error: counted 15 posts instead of 16",
            204: "added both end posts on top of 15 (17 posts)",
        },
    },
    {
        "id": "P7_jacket_price",
        "title": "Jacket price",
        "origin": "v2",
        "trap_type": "Chained percentages",
        "question": (
            "A jacket costs $80. A shop marks the price up by 25%, then "
            "offers 30% off the marked-up price. A 5% sales tax is then "
            "added to the discounted price. What is the final price, in "
            "dollars?"
        ),
        "answer": 73.50,
        "tolerance": 0.01,
        "steps": [
            ("marked-up price (80*1.25)", 100),
            ("after 30% off (100*0.70)", 70),
            ("after 5% tax (70*1.05)", 73.50),
        ],
        "traps": {
            79.80: "netted +25% and -30% into a single -5% change",
            70: "forgot to add the sales tax",
            66.50: "subtracted the tax instead of adding it",
            58.80: "applied 30% off to the original $80, skipping the markup",
        },
    },
    {
        "id": "P8_print_job",
        "title": "Print job",
        "origin": "v2",
        "trap_type": "Pauses: count boundaries",
        "question": (
            "A printer prints 18 pages per minute. A school needs 45 copies "
            "of a 24-page booklet. The printer must pause for 5 minutes after "
            "every 300 pages it prints, to cool down; no pause is needed "
            "after the final page. How many minutes does the whole print job "
            "take?"
        ),
        "answer": 75,
        "tolerance": 0,
        "steps": [
            ("total pages (45*24)", 1080),
            ("printing time (1080/18)", 60),
            ("cool-down pauses (after 300, 600, 900)", 3),
            ("pause time (3*5)", 15),
            ("total time (60+15)", 75),
        ],
        "traps": {
            80: "counted 4 pauses (rounded 3.6 up) instead of 3",
            78: "used 3.6 pauses (1080/300) without whole-pause logic",
            60: "ignored the cool-down pauses",
        },
    },
    {
        "id": "P9_school_buses",
        "title": "School buses",
        "origin": "v2",
        "trap_type": "Remainder + who counts",
        "question": (
            "A school trip has 214 students and 17 teachers. Each bus holds "
            "45 people, and every person on the trip needs a seat. Renting "
            "one bus costs $350. What is the total bus rental cost, in "
            "dollars?"
        ),
        "answer": 2100,
        "tolerance": 0,
        "steps": [
            ("total people (214+17)", 231),
            ("buses needed (ceil 231/45)", 6),
            ("total cost (6*350)", 2100),
        ],
        "traps": {
            1750: "5 buses: forgot the teachers or rounded down",
            1796.67: "used 5.13 buses without rounding up",
            6: "reported number of buses instead of cost",
        },
    },
    {
        "id": "P10_reading_days",
        "title": "Reading schedule",
        "origin": "v2",
        "trap_type": "Two rates + already done",
        "question": (
            "Liam reads 35 pages per day on weekdays (Monday to Friday) and "
            "50 pages per day on Saturdays and Sundays. His book has 480 "
            "pages and he has already read 125 of them. He starts reading "
            "again on a Monday, which counts as day 1. On which day number "
            "does he finish the book?"
        ),
        "answer": 10,
        "tolerance": 0,
        "steps": [
            ("pages left (480-125)", 355),
            ("pages read in first full week (5*35 + 2*50)", 275),
            ("pages left after day 7 (355-275)", 80),
            ("weekdays needed in week 2 (ceil 80/35)", 3),
            ("finishing day (7+3)", 10),
        ],
        "traps": {
            11: "ignored the faster weekend rate (355/35 rounded up)",
            13: "forgot the 125 pages already read",
            9: "rounded 80/35 down instead of up",
        },
    },
    {
        "id": "P11_tank_fill",
        "title": "Filling a tank",
        "origin": "v2",
        "trap_type": "Combined rates w/ drain",
        "question": (
            "Pipe A fills a 600-litre tank in 30 minutes. Pipe B fills the "
            "same tank in 20 minutes. A drain empties a full tank in 60 "
            "minutes. The tank starts empty and all three are opened at the "
            "same time. How many minutes does it take to fill the tank?"
        ),
        "answer": 15,
        "tolerance": 0.01,
        "steps": [
            ("pipe A rate (600/30)", 20),
            ("pipe B rate (600/20)", 30),
            ("drain rate (600/60)", 10),
            ("net fill rate (20+30-10)", 40),
            ("time to fill (600/40)", 15),
        ],
        "traps": {
            12: "ignored the drain",
            10: "added the drain's rate instead of subtracting it",
            36.67: "averaged the three times",
        },
    },
    {
        "id": "P12_phone_bill",
        "title": "Phone bill",
        "origin": "v2",
        "trap_type": "Tiered pricing",
        "question": (
            "A phone plan costs $20 per month, which includes the first 5 GB "
            "of data. Each GB above 5 GB, up to and including 10 GB, costs "
            "$8. Each GB above 10 GB costs $5. Priya used 13 GB this month. "
            "What is her bill, in dollars?"
        ),
        "answer": 75,
        "tolerance": 0,
        "steps": [
            ("GB billed at $8 (10-5)", 5),
            ("cost of middle tier (5*8)", 40),
            ("GB billed at $5 (13-10)", 3),
            ("cost of top tier (3*5)", 15),
            ("total bill (20+40+15)", 75),
        ],
        "traps": {
            84: "charged every extra GB at $8",
            60: "charged every extra GB at $5",
            55: "forgot the $20 base fee",
        },
    },
    {
        "id": "P13_ages",
        "title": "Father and daughter",
        "origin": "v2",
        "trap_type": "Algebra, asks future age",
        "question": (
            "Today, Ravi is 3 times as old as his daughter. In 12 years, Ravi "
            "will be exactly twice as old as his daughter. How old will Ravi "
            "be 5 years from today?"
        ),
        "answer": 41,
        "tolerance": 0,
        "steps": [
            ("daughter's age today (3d+12 = 2(d+12))", 12),
            ("Ravi's age today (3*12)", 36),
            ("Ravi's age in 5 years (36+5)", 41),
        ],
        "traps": {
            36: "gave Ravi's age today, not in 5 years",
            48: "gave Ravi's age in 12 years",
            12: "gave the daughter's age",
        },
    },
    {
        "id": "P14_class_average",
        "title": "Class average",
        "origin": "v2",
        "trap_type": "Group size changes",
        "question": (
            "A class of 24 students has an average test score of 72. Four "
            "students, whose average score was 45, leave the class. Two new "
            "students join, scoring 90 and 78. What is the new class average?"
        ),
        "answer": 78,
        "tolerance": 0.01,
        "steps": [
            ("original total score (24*72)", 1728),
            ("total of students who left (4*45)", 180),
            ("total after they leave (1728-180)", 1548),
            ("total after new students (1548+90+78)", 1716),
            ("new class size (24-4+2)", 22),
            ("new average (1716/22)", 78),
        ],
        "traps": {
            71.5: "divided by the original 24 students",
            66: "used 26 students (forgot that 4 left)",
            85.8: "divided by 20 (forgot the 2 new students)",
        },
    },
    {
        "id": "P15_cookie_flour",
        "title": "Cookie flour",
        "origin": "v2",
        "trap_type": "Units + distractor",
        "question": (
            "A recipe uses 250 grams of flour to make 12 cookies. A baker "
            "wants to make 90 cookies for a sale. The oven bakes 18 cookies "
            "per batch. Flour is sold only in 1-kilogram bags costing $3.20 "
            "each. How much does the baker spend on flour, in dollars?"
        ),
        "answer": 6.40,
        "tolerance": 0.01,
        "steps": [
            ("flour needed in grams (250*90/12)", 1875),
            ("flour needed in kg (1875/1000)", 1.875),
            ("bags to buy (ceil 1.875)", 2),
            ("total cost (2*3.20)", 6.40),
        ],
        "traps": {
            6.00: "paid for 1.875 bags instead of rounding up to 2",
            3.20: "rounded 1.875 bags down to 1",
            16.00: "used the oven's 5 batches as the number of bags",
        },
    },
]

PROBLEMS_BY_ID = {p["id"]: p for p in PROBLEMS}

# How each answer is displayed on slides / in the report
UNITS = {
    "P1_cafe_cups": "$", "P2_bookstore_discount": "$", "P3_road_trip_fuel": "$",
    "P4_classroom_supplies": "$", "P5_savings_goal": "$", "P6_fence_posts": "$",
    "P7_jacket_price": "$", "P8_print_job": "min", "P9_school_buses": "$",
    "P10_reading_days": "day", "P11_tank_fill": "min", "P12_phone_bill": "$",
    "P13_ages": "years", "P14_class_average": "avg", "P15_cookie_flour": "$",
}


def format_value(problem_id: str, value) -> str:
    if value is None:
        return "—"
    unit = UNITS.get(problem_id, "")
    v = float(value)
    if unit == "$":
        return f"${v:,.0f}" if v.is_integer() else f"${v:,.2f}"
    num = f"{v:g}"
    if unit == "day":
        return f"Day {num}"
    return f"{num} {unit}".strip()
