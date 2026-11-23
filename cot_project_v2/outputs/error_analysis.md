# Step 4 -- Root-cause analysis of every wrong answer

## Failure categories

| Category | Standard prompting | Zero-shot CoT |
|---|---|---|
| Fell into a known trap | 0 | 4 |
| Wrong / missing step | 0 | 3 |
| Right value, wrong one reported | 0 | 1 |
| Unexplained guess (no work shown) | 41 | 0 |
| **Total wrong** | 41 | 8 |

## Hardest problem under CoT: P10_reading_days (0/3 runs correct)

Run 0: model answered **15.0**, correct is **10**.

**Diagnosis (Wrong / missing step):** chain breaks at step 3/5: 'pages left after day 7 (355-275)' should be 80 but never appears

First line that leaves the correct path:

> So, he will have read 355 pages in 2 weeks and 1 day (since 550 - 355 = 195 pages, and 195 pages will take 1 day to read, as he reads 35 pages per day on weekdays and 50 pages per day on weekends).

| # | Ground-truth step | Value | In model's reasoning? |
|---|---|---|---|
| 1 | pages left (480-125) | 355 | yes |
| 2 | pages read in first full week (5*35 + 2*50) | 275 | yes |
| 3 | pages left after day 7 (355-275) | 80 | **NO** |
| 4 | weekdays needed in week 2 (ceil 80/35) | 3 | **NO** |
| 5 | finishing day (7+3) | 10 | **NO** |

Full transcript: `outputs\logs\P10_reading_days_cot_run0.txt`

## Every failure -- Standard prompting (41)

| Problem | Run | Answer | Correct | Category | Diagnosis |
|---|---|---|---|---|---|
| P10_reading_days | 0 | 18.0 | 10 | Unexplained guess (no work shown) | answered 18 with no work shown; matches no known mistake |
| P10_reading_days | 1 | 53.0 | 10 | Unexplained guess (no work shown) | answered 53 with no work shown; matches no known mistake |
| P11_tank_fill | 0 | 1500.0 | 15 | Unexplained guess (no work shown) | answered 1500 with no work shown; matches no known mistake |
| P11_tank_fill | 1 | 1500.0 | 15 | Unexplained guess (no work shown) | answered 1500 with no work shown; matches no known mistake |
| P11_tank_fill | 2 | 1500.0 | 15 | Unexplained guess (no work shown) | answered 1500 with no work shown; matches no known mistake |
| P12_phone_bill | 0 | 41.0 | 75 | Unexplained guess (no work shown) | answered 41 with no work shown; matches no known mistake |
| P12_phone_bill | 1 | 41.0 | 75 | Unexplained guess (no work shown) | answered 41 with no work shown; matches no known mistake |
| P12_phone_bill | 2 | 41.0 | 75 | Unexplained guess (no work shown) | answered 41 with no work shown; matches no known mistake |
| P13_ages | 0 | 40.0 | 41 | Unexplained guess (no work shown) | answered 40 with no work shown; matches no known mistake |
| P13_ages | 1 | 40.0 | 41 | Unexplained guess (no work shown) | answered 40 with no work shown; matches no known mistake |
| P14_class_average | 0 | 74.0 | 78 | Unexplained guess (no work shown) | answered 74 with no work shown; matches no known mistake |
| P14_class_average | 1 | 74.0 | 78 | Unexplained guess (no work shown) | answered 74 with no work shown; matches no known mistake |
| P14_class_average | 2 | 74.0 | 78 | Unexplained guess (no work shown) | answered 74 with no work shown; matches no known mistake |
| P15_cookie_flour | 0 | 12.0 | 6.4 | Unexplained guess (no work shown) | answered 12 with no work shown; matches no known mistake |
| P15_cookie_flour | 1 | 12.0 | 6.4 | Unexplained guess (no work shown) | answered 12 with no work shown; matches no known mistake |
| P15_cookie_flour | 2 | 12.0 | 6.4 | Unexplained guess (no work shown) | answered 12 with no work shown; matches no known mistake |
| P1_cafe_cups | 0 | 5.0 | 216 | Unexplained guess (no work shown) | answered 5 with no work shown; matches no known mistake |
| P1_cafe_cups | 1 | 5.0 | 216 | Unexplained guess (no work shown) | answered 5 with no work shown; matches no known mistake |
| P1_cafe_cups | 2 | 5.0 | 216 | Unexplained guess (no work shown) | answered 5 with no work shown; matches no known mistake |
| P2_bookstore_discount | 0 | 143.05 | 148.5 | Unexplained guess (no work shown) | answered 143.05 with no work shown; matches no known mistake |
| P2_bookstore_discount | 1 | 143.08 | 148.5 | Unexplained guess (no work shown) | answered 143.08 with no work shown; matches no known mistake |
| P2_bookstore_discount | 2 | 144.0 | 148.5 | Unexplained guess (no work shown) | answered 144 with no work shown; matches no known mistake |
| P3_road_trip_fuel | 2 | 100.0 | 104 | Unexplained guess (no work shown) | answered 100 with no work shown; matches no known mistake |
| P4_classroom_supplies | 0 | 56.8 | 46.8 | Unexplained guess (no work shown) | answered 56.8 with no work shown; matches no known mistake |
| P4_classroom_supplies | 1 | 54.0 | 46.8 | Unexplained guess (no work shown) | answered 54 with no work shown; matches no known mistake |
| P4_classroom_supplies | 2 | 56.8 | 46.8 | Unexplained guess (no work shown) | answered 56.8 with no work shown; matches no known mistake |
| P5_savings_goal | 0 | 260.0 | 550 | Unexplained guess (no work shown) | answered 260 with no work shown; matches no known mistake |
| P5_savings_goal | 1 | 240.0 | 550 | Unexplained guess (no work shown) | answered 240 with no work shown; matches no known mistake |
| P5_savings_goal | 2 | 260.0 | 550 | Unexplained guess (no work shown) | answered 260 with no work shown; matches no known mistake |
| P6_fence_posts | 0 | 150.0 | 192 | Unexplained guess (no work shown) | answered 150 with no work shown; matches no known mistake |
| P6_fence_posts | 1 | 150.0 | 192 | Unexplained guess (no work shown) | answered 150 with no work shown; matches no known mistake |
| P6_fence_posts | 2 | 150.0 | 192 | Unexplained guess (no work shown) | answered 150 with no work shown; matches no known mistake |
| P7_jacket_price | 0 | 86.75 | 73.5 | Unexplained guess (no work shown) | answered 86.75 with no work shown; matches no known mistake |
| P7_jacket_price | 1 | 86.67 | 73.5 | Unexplained guess (no work shown) | answered 86.67 with no work shown; matches no known mistake |
| P7_jacket_price | 2 | 86.75 | 73.5 | Unexplained guess (no work shown) | answered 86.75 with no work shown; matches no known mistake |
| P8_print_job | 0 | 105.0 | 75 | Unexplained guess (no work shown) | answered 105 with no work shown; matches no known mistake |
| P8_print_job | 1 | 105.0 | 75 | Unexplained guess (no work shown) | answered 105 with no work shown; matches no known mistake |
| P8_print_job | 2 | 105.0 | 75 | Unexplained guess (no work shown) | answered 105 with no work shown; matches no known mistake |
| P9_school_buses | 0 | 1500.0 | 2100 | Unexplained guess (no work shown) | answered 1500 with no work shown; matches no known mistake |
| P9_school_buses | 1 | 1400.0 | 2100 | Unexplained guess (no work shown) | answered 1400 with no work shown; matches no known mistake |
| P9_school_buses | 2 | 1400.0 | 2100 | Unexplained guess (no work shown) | answered 1400 with no work shown; matches no known mistake |

## Every failure -- Zero-shot CoT (8)

| Problem | Run | Answer | Correct | Category | Diagnosis |
|---|---|---|---|---|---|
| P10_reading_days | 0 | 15.0 | 10 | Wrong / missing step | chain breaks at step 3/5: 'pages left after day 7 (355-275)' should be 80 but never appears |
| P10_reading_days | 1 | 9.0 | 10 | Fell into a known trap | rounded 80/35 down instead of up |
| P10_reading_days | 2 | 12.0 | 10 | Wrong / missing step | chain breaks at step 3/5: 'pages left after day 7 (355-275)' should be 80 but never appears |
| P12_phone_bill | 1 | 55.0 | 75 | Fell into a known trap | forgot the $20 base fee |
| P12_phone_bill | 2 | 23.0 | 75 | Wrong / missing step | chain breaks at step 2/5: 'cost of middle tier (5*8)' should be 40 but never appears |
| P14_class_average | 1 | 77.91 | 78 | Right value, wrong one reported | the correct value 78 appears in the reasoning, but 77.91 was reported |
| P15_cookie_flour | 1 | 6.0 | 6.4 | Fell into a known trap | paid for 1.875 bags instead of rounding up to 2 |
| P6_fence_posts | 0 | 204.0 | 192 | Fell into a known trap | added both end posts on top of 15 (17 posts) |
