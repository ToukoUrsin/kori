# Finnish population benchmarks

Open data for comparing one bank customer's monthly spending with typical Finnish households.
Retrieved **13 Nov 2026**. Every number was fetched live; nothing is from memory. A value the source
suppresses is `null` or absent.

| File | Content |
|---|---|
| `statfin.json` | Consumption by app category (Household Budget Survey 2022), income by age, saving rate, housing cost burden, reference budgets 2025 |
| `paavo_income.json` | Income, inhabitants, average age and households for all 3,018 postal code areas (Paavo 2026, statistical year 2024), plus all 308 municipalities as fallback |

Re-run (about 90 s; needs `pdftotext` from poppler-utils for the reference budget PDF):

```bash
uv run --with requests python scripts/fetch_benchmarks.py
```

## Sources

API base: `https://pxdata.stat.fi/PxWeb/api/v1/en/` + table path. Web UI:
`https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/StatFin__<subject>/<table>.px/`. Licence CC BY 4.0, Statistics Finland.
The exact URL and the source's "updated" timestamp of every table are in `meta.sources`.

| JSON section | Table | What | Year | Source updated |
|---|---|---|---|---|
| `all_households`, `by_age_group` | `StatFin/ktutk/14q4.px` | Consumption expenditure by age of reference person | 2022 | 11 Apr 2024 |
| `by_household_type` | `StatFin/ktutk/14ph.px` | by type of household (life stage) | 2022 | 11 Apr 2024 |
| `by_income_quintile` | `StatFin/ktutk/14pg.px` | by income quintile | 2022 | 11 Apr 2024 |
| `by_region` | `StatFin/ktutk/14q8.px` | by major region (Helsinki-Uusimaa etc.) | 2022 | 11 Apr 2024 |
| `by_municipality_type` | `StatFin/ktutk/14q7.px` | urban / semi-urban / rural | 2022 | 11 Apr 2024 |
| `by_household_structure` | `StatFin/ktutk/14q5.px` | by adults + children (2-digit COICOP only) | 2022 | 11 Apr 2024 |
| `*.background` | `ktutk/14q9, 14lv, 14qa, 14qd, 14qc, 14qb` | sample size, households, household size, consumption units, disposable income | 2022 | 11 Apr 2024 |
| `meta.cpi` | `StatFin/khi/15b5.px` | Consumer Price Index 2025=100, monthly, by COICOP 2018 | to Oct 2026 | 13 Nov 2026 |
| `median_income_by_age` | `StatFin/tjt/11py.px` | Disposable monetary income by person's age | 2024 | 16 Dec 2025 |
| `household_income_by_age_of_reference_person` | `StatFin/tjt/12eb.px` | Household income by age of reference person | 2024 | 26 Feb 2026 |
| `housing_cost_burden` | `StatFin/tjt/12g9.px` | Housing costs as share of income by tenure and life stage | 2024 | 26 Feb 2026 |
| `saving_rate.quarterly` | `StatFin/ntp/15a8.px` | Household saving rate, quarterly sector accounts | to 2026Q2 | 18 Sep 2026 |
| `saving_rate.annual` | `StatFin/ntp/15ac.px` | Household sector income, consumption, net saving | to 2025* | 18 Sep 2026 |
| `paavo_income.json` | `Postinumeroalueittainen_avoin_tieto/2026/12f7_ja2026.px` (areas), `12f8_ja2026.px` (municipalities) | Paavo open data by postal code area | 2024 | 15 Sep 2026 |
| `reference_budgets` | Report PDF, tables 19 and 20 | Decent-minimum reference budgets | 2025 prices | published 2026 |

The Household Budget Survey 2022 is the newest: all `ktutk` tables cover 2012, 2016 and 2022 only.

Reference budgets: Pöyry, Pekuri, Seppänen, Savolainen & Lehtinen, *Kohtuullinen ja kestävä kulutus: kohtuullisen
minimin viitebudjettien päivitys vuodelle 2025*, Valtiotieteellisen tiedekunnan julkaisuja 2026:265, University of
Helsinki (Centre for Consumer Society Research), ISBN 978-952-84-0057-8.
Landing page: https://helda.helsinki.fi/items/9dcd00a2-ca32-4871-8787-e176aa7e31e8 ·
PDF: https://helda.helsinki.fi/server/api/core/bitstreams/3790704c-2d4a-42e2-807b-c5c5bc5c9498/content

## How the consumption numbers are built

Each group (`all_households`, an age group, a household type, ...) has two blocks:

- `per_household`: mean per household of that group, all household sizes mixed.
- `per_consumption_unit`: mean per OECD-modified consumption unit (first adult 1.0, each other person aged 14+ 0.5,
  each child under 14 0.3). **Use this one for a single customer**; multiply by the household's consumption units
  to get a household figure (a couple = 1.5, couple with two small children = 2.1).

Each block holds `app_categories`, `app_category_variants`, `not_mapped`, `coicop_divisions` (the 13 official
divisions plus 77 "consumption abroad") and `total_consumption`. Every value has three figures:

| Field | Meaning |
|---|---|
| `eur_month_survey_year` | published EUR/year at 2022 prices, divided by 12 |
| `eur_month_2026` | the same × headline CPI factor **1.10205** |
| `eur_month_2026_category_cpi` | each COICOP component × its own CPI sub-index, then summed. Better for categories whose prices moved differently from the average |

`components_missing` lists COICOP components that the source suppressed for that group; they count as 0 in the
sum. `low_sample: true` marks groups with fewer than 100 sampled households (age 17-24, age 85+, single parents).

### CPI values used

Table `15b5` (2025=100). Factor = average of Jan-Oct 2026 / average of Jan-Dec 2022. 2026 is a partial year
(`meta.cpi.target_year_is_partial`).

| Index | Avg 2022 | Avg Jan-Oct 2026 | Factor |
|---|---|---|---|
| Total (headline) | 92.344 | 101.768 | 1.10205 |
| 01 Food and non-alcoholic beverages | 89.82 | 101.37 | 1.12859 |
| 04.1 Actual rents | 94.63 | 100.08 | 1.05760 |
| 04.5 Electricity, gas, other fuels | 108.23 | 105.76 | 0.97723 |
| 07.2.2 Fuels | 125.55 | 119.09 | 0.94855 |
| 11.1 Restaurants and cafes | 88.08 | 102.06 | 1.15875 |
| 04.6.3 Interest on housing loans | 33.57 | 92.89 | 2.76734 |

All 70 sub-indices and which one each component uses are in `meta.cpi.by_coicop` and
`meta.cpi.index_used_for_component`. Components with no own index use the parent (04.2 → 04, 07.3.5/07.3.6 → 07.3,
08.2 → 08, 09.1.1 → 09.1, 09.4.1-09.4.4 → 09.4, 77 → total). Cross-check: the 2015=100 series (`11xt`, `11xs`) gives
113.4 for 2022 and 124.9 for Jan-Oct 2026, a factor of 1.1016.

Income figures are **not** inflated: they are 2024 euros.

## Category mapping (COICOP 2018 → app categories)

The mapping is in `meta.category_mapping`. App categories plus `not_mapped` add up exactly to total consumption
expenditure (within rounding; see checks).

| App category | COICOP codes | All households, per consumption unit, EUR/month 2026 |
|---|---|---|
| Groceries | 01 food and drinks, 02 alcohol and tobacco, 05.6.1 non-durable household goods, 13.1.2 personal care products | 458 |
| Restaurants | 11.1 restaurants, cafes, canteens | 88 |
| Transportation | 07.2.1-07.2.3 parts, fuel, service; 07.2.4.1-3 parking, tolls, inspections and licences; 07.3.1, 07.3.2, 07.3.5, 07.3.6 rail, bus, taxi, combined tickets | 178 |
| Utilities | 04.4.1-04.4.3 water, refuse, sewage; 04.4.4.9 other dwelling services; 04.5 electricity and heating fuels; 08.3 phone, internet, streaming | 194 |
| Entertainment | 09.4 recreational and sporting services, games of chance, hire (without 09.4.5 vets); 09.6 cinema, theatre, museums | 47 |
| Health | 06 medicines, medical products, doctor, dentist, hospital | 95 |
| Home & Tech | 05.1-05.5 furniture, textiles, appliances, tableware, tools; 04.3.1 DIY materials; 08.1 phones, computers, TV; 08.2 software; 09.1.1 cameras; 13.1.1 personal-care appliances | 142 |
| Housing | 04.1 actual rents; 04.4.4.1 housing-company maintenance charges; 04.6.3 interest on housing loans | 314 |
| Lifestyle | 03 clothing and footwear; 09.2 games, toys, sports gear; 09.5 instruments and media; 09.7 books, papers, stationery; 13.2 jewellery, watches, bags | 165 |
| Travel | 07.3.3 flights; 07.3.4 ferries; 07.2.4.4 car hire; 09.8 package holidays; 11.2 accommodation | 53 |

Not mapped (reported separately under `not_mapped`): imputed rent of owner-occupiers (04.2), dwelling repair
services (04.3.2), domestic services (05.6.2), vehicle purchase (07.1), postal services (07.4), boats and caravans
(09.1.2), garden and pets (09.3, 09.4.5), education (10), insurance (12.1), financial services (12.2), hairdresser
(13.1.3), social protection (13.3), other services (13.9), consumption abroad (77).

Variants for different assumptions: `Groceries_food_only` (01), `Groceries_food_alcohol_tobacco` (01+02),
`Housing_incl_imputed_rent`, `Travel_incl_consumption_abroad`,
`Transportation_incl_vehicle_purchase_and_motor_insurance`, `Utilities_incl_insurance`.

### Limits of the mapping

- **Bank categories follow the merchant, COICOP follows the product.** A supermarket receipt is all "Groceries"
  in the app, so Groceries includes alcohol, tobacco, detergents and shampoo. Clothes or electronics bought in a
  hypermarket still land in Groceries in the bank data but in Lifestyle / Home & Tech here.
- **Housing is the weakest comparison.** The survey mixes tenants, owners with a loan and owners without one, so
  the average (314 EUR per consumption unit) is far below what a tenant pays. Loan principal is not consumption and
  is not in the survey; a customer's mortgage payment will look high against it. For tenants prefer the reference
  budget rents, `Housing_incl_imputed_rent`, or the shares in `housing_cost_burden`.
- **Utilities**: the app's bill payments may include insurance; the main category does not
  (`Utilities_incl_insurance` does). Streaming subscriptions are here (COICOP 08.3), not in Entertainment.
- **Transportation** excludes buying a car and motor insurance. It includes inspection and licence fees (07.2.4.3)
  and tolls (07.2.4.2) as classified by the survey.
- **Travel** excludes spending abroad (77), which the survey does not split by product: restaurant and shop
  purchases abroad cannot be separated from hotels. Treat Travel as a lower bound.
- **Means, not medians.** The survey publishes averages only; a few big spenders pull them up, and many
  households spend 0 in a category such as Travel in a given month.
- **Rounding.** Source values are whole euros per year. Mapped sums differ from the published total by at most
  79 EUR/year (under 7 EUR/month) in groups with 100+ sampled households, and by up to 356 EUR/year (30 EUR/month)
  in the 85+ group, where many components are suppressed.
- The survey covers about 85 % of national-accounts household consumption (Statistics Finland release, 2023).
- Household type "aged 65+ households" and age groups refer to the household's reference person.

## Other sections

- `median_income_by_age` (table 11py, 2024): for all persons of that age, median and mean personal disposable
  monetary income and disposable monetary income per consumption unit, EUR/year and /12. Age groups 18-24, 25-34,
  35-49, 50-64, 65-74, 75+.
- `household_income_by_age_of_reference_person` (12eb, 2024): median and mean per household, median per
  consumption unit. Weighted by households, so the medians differ from the person-weighted ones above.
- `saving_rate`: quarterly household saving rate as published (seasonally adjusted and original), last 12 quarters,
  latest 2026Q2. `annual.*.saving_rate_pct_derived` is computed here as B8N / (B6N + D8R) from the published
  aggregates; 2024 and 2025 are preliminary. The average of the four seasonally adjusted quarters of 2025 (5.9)
  matches the derived 5.92.
- `housing_cost_burden` (12g9, 2024): housing costs as % of net income (median, mean) by tenure
  (`all_tenures`, `owner_occupied`, `rented`, `other`) and 13 life stages, with median income per consumption unit
  before and after housing costs.
- `reference_budgets`: 14 example households (4 single, 3 couples, 3 single-parent, 4 two-parent), EUR/month at
  2025 prices: 9 budget items, 2 subtotals, transport (capital region / rest of Finland), rent (Helsinki, capital
  region, other cities over 100,000, rest of Finland) and totals. These are a **decent minimum**, not an average:
  use them as a floor ("what a modest but adequate life costs"), not as typical spending. Rent is a rented flat;
  transport is public transport, with a car only for households of more than 3 persons outside the capital region.
  `item_to_app_category_hint` suggests the closest app category per item.
- `paavo_income.json`: `areas[postal_code]` → `median_income_eur_year` and `avg_income_eur_year` (disposable
  monetary income of inhabitants aged 18+), the same /12, `inhabitants`, `avg_age`, `adults_18_plus`, household
  median and average income, households, household size, owner-occupied and rented households, area name and
  municipality. Of the 290 distinct postal codes in the customer file, 195 are Paavo areas (5,005 of 5,100
  customers); the other 95 are PO-box or company codes (one customer each). For those use
  `prefix3_to_municipality` → `municipalities`, which resolves all 95 (Helsinki 30, Espoo 27, Vantaa 21,
  Kirkkonummi 6, Sipoo 5, Siuntio 3, Nurmijärvi 3), then `whole_country`.

## Spot checks (13 Nov 2026)

Against Statistics Finland release texts of 11 Apr 2024
([quintiles](https://stat.fi/julkaisu/clmyi6vct7jjp0cutgh4ngdsb),
[age groups](https://stat.fi/fi/julkaisu/cln0fihydojsm0cut4vyr99xo)), all per consumption unit, 2022:

| Value | Release text | This file (EUR/year = month × 12) |
|---|---|---|
| Food, lowest income quintile | "noin 2 850 euroa", just under 240 EUR/month | 2,848 (237.33/month) |
| Food, highest quintile | 5,030 EUR/year, about 420/month | 5,034 (419.50) |
| Housing and energy, lowest quintile | about 6,670 EUR/year, about 560/month | 6,668 (555.67) |
| Housing and energy, highest quintile | about 13,340 EUR/year | 13,344 (1,112.00) |
| Transport, highest quintile | about 7,360 EUR/year, about 610/month | 7,361 (613.42) |
| Clothing and footwear, age 17-24 | about 1,320 EUR | 1,320 |
| Transport, age 25-34 | 3,610 EUR | 3,614 |
| Food, all households | 3,950 EUR | 3,946 |
| Restaurants and accommodation, all households | 1,090 EUR | 1,089 |
| Housing share, lowest / highest quintile | 39 % / 30 % | 38.6 % / 30.0 % |

Other checks:

- Published monthly columns of the same tables (`kulukk_*`, whole euros) agree with year / 12 within 0.5 EUR for
  every group and division.
- Reference budgets: in every column the items sum to the subtotals and subtotals + transport + rent sum to the
  totals, except one printed total in the report (single parent with two children, Helsinki: printed 3,053,
  components sum to 3,055; kept as printed, listed in `reference_budgets.source_inconsistencies`). The single-person
  range 1,251-1,761 EUR/month matches the
  [University of Helsinki news item](https://www.helsinki.fi/fi/uutiset/yhteiskunta-ja-oppiminen/tuoreet-laskelmat-kertovat-milla-rahamaaralla-kotitaloudet-voivat-tulla-toimeen)
  of 19 Nov 2025. That news item and its press tables give slightly lower family totals (3,001-4,567) than the
  final report (3,015-4,580); the final report is used.
- Paavo whole-country median income of adults (26,351 EUR) is close to table 11py's median for ages 18+ (26,605 EUR),
  as expected for two slightly different populations.

## What was not found

- No income statistics release text with euro medians to check against (the 16 Dec 2025 release page states only
  percentages), so the income figures are checked only between tables.
- Statistics Finland does not publish housing costs in euros by tenure in StatFin `tjt`; only shares of income
  (table 12g9). No number was derived from them.
- No consumption table by postal code or municipality exists; region is major region and municipality type only.
