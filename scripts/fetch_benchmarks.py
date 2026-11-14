#!/usr/bin/env python3
"""Fetch Finnish open population benchmarks for the personal-finance coach.

Run from the project root:
    uv run --with requests python scripts/fetch_benchmarks.py

Writes:
    data/benchmarks/statfin.json        consumption, income, saving rate, reference budgets
    data/benchmarks/paavo_income.json   income etc. per postal code area (Paavo)

Every number comes from a live request (Statistics Finland PxWeb API, or the
reference-budget report PDF). Nothing is filled in from memory: a value that
is missing or suppressed at the source is absent or null in the output.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

API = "https://pxdata.stat.fi/PxWeb/api/v1/en/"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "benchmarks"
UA = {"User-Agent": "benchmark-fetch/1.0 (python-requests)"}
SESSION = requests.Session()
SESSION.headers.update(UA)

# --------------------------------------------------------------------------
# PxWeb helpers
# --------------------------------------------------------------------------


def _request(method: str, url: str, **kw):
    for attempt in range(6):
        r = SESSION.request(method, url, timeout=120, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(3 + 3 * attempt)
            continue
        r.raise_for_status()
        time.sleep(0.4)  # stay well below the PxWeb rate limit
        return r
    r.raise_for_status()
    raise RuntimeError(f"gave up on {url}")


def px_meta(table: str) -> dict:
    """Table metadata: {var_code: {"text":..., "values": {code: label}}}."""
    m = _request("GET", API + table).json()
    return {
        "title": m["title"],
        "vars": {
            v["code"]: {"text": v["text"], "values": dict(zip(v["values"], v["valueTexts"]))}
            for v in m["variables"]
        },
    }


class PxResult:
    def __init__(self, js: dict):
        self.ids = js["id"]
        self.size = js["size"]
        self.index = []
        self.labels = {}
        for d in self.ids:
            cat = js["dimension"][d]["category"]
            idx = cat["index"]
            codes = sorted(idx, key=idx.get) if isinstance(idx, dict) else list(idx)
            self.index.append({c: i for i, c in enumerate(codes)})
            self.labels[d] = cat.get("label", {})
        self.values = js["value"]
        self.updated = js.get("updated")
        self.label = js.get("label")

    def get(self, **sel):
        """Value for one cell; keyword names are the dimension codes."""
        pos = 0
        for d, n, idx in zip(self.ids, self.size, self.index):
            pos = pos * n + idx[sel[d]]
        return self.values[pos]


def px_query(table: str, selection: dict[str, list[str]]) -> PxResult:
    body = {
        "query": [
            {"code": k, "selection": {"filter": "item", "values": list(v)}}
            for k, v in selection.items()
        ],
        "response": {"format": "json-stat2"},
    }
    return PxResult(_request("POST", API + table, json=body).json())


# --------------------------------------------------------------------------
# COICOP 2018 -> app transaction categories
# --------------------------------------------------------------------------

APP_MAP = {
    "Groceries": ["01", "02", "0561", "1312"],
    "Restaurants": ["111"],
    "Transportation": ["0721", "0722", "0723", "07241", "07242", "07243",
                       "0731", "0732", "0735", "0736"],
    "Utilities": ["0441", "0442", "0443", "04449", "045", "083"],
    "Entertainment": ["0941", "0942", "0943", "0944", "0946", "0947", "096"],
    "Health": ["06"],
    "Home & Tech": ["0431", "051", "052", "053", "054", "055", "081", "082", "0911", "1311"],
    "Housing": ["041", "04441", "0463"],
    "Lifestyle": ["03", "092", "095", "097", "132"],
    "Travel": ["0733", "0734", "07244", "098", "112"],
}
NOT_MAPPED = {
    "imputed_rent_owner_occupiers": ["042"],
    "dwelling_repair_services": ["0432"],
    "domestic_services": ["0562"],
    "vehicle_purchase": ["071"],
    "postal_and_goods_transport": ["074"],
    "major_recreational_durables": ["0912"],
    "garden_and_pets": ["093", "0945"],
    "education": ["10"],
    "insurance": ["121"],
    "financial_services": ["122"],
    "hairdressing_and_grooming": ["1313"],
    "social_protection": ["133"],
    "other_services": ["139"],
    "consumption_abroad": ["77"],
}
VARIANTS = {
    "Groceries_food_only": ["01"],
    "Groceries_food_alcohol_tobacco": ["01", "02"],
    "Housing_incl_imputed_rent": APP_MAP["Housing"] + ["042"],
    "Travel_incl_consumption_abroad": APP_MAP["Travel"] + ["77"],
    "Transportation_incl_vehicle_purchase_and_motor_insurance":
        APP_MAP["Transportation"] + ["071", "1214"],
    "Utilities_incl_insurance": APP_MAP["Utilities"] + ["121"],
}
MAPPING_NOTES = {
    "Groceries": "Supermarket basket: food and non-alcoholic drinks (01), alcohol and tobacco (02), "
                 "non-durable household goods such as detergents (05.6.1), personal care products (13.1.2).",
    "Restaurants": "Restaurants, cafes, canteens (11.1). Accommodation (11.2) is under Travel.",
    "Transportation": "Running a vehicle (fuel, parts, service, parking, tolls, inspections/licences) and "
                      "local/long-distance rail, bus, taxi, combined tickets. Excludes buying a vehicle (07.1), "
                      "motor insurance (12.1.4), flights and ferries (Travel).",
    "Utilities": "Water, refuse, sewage, other dwelling services n.e.c., electricity/gas/heating fuels (04.5), "
                 "phone/internet/streaming subscriptions (08.3). Insurance is NOT included.",
    "Entertainment": "Recreational and sporting services, games of chance, cinemas/theatres/museums and other "
                     "cultural services, hire of recreational gear (09.4 excl. vets, 09.6).",
    "Health": "All of division 06: medicines, medical products, doctor, dentist, hospital fees.",
    "Home & Tech": "Furniture, household textiles, appliances, tableware, tools (05.1-05.5), DIY materials for the "
                   "dwelling (04.3.1), phones/computers/TV/audio equipment (08.1), software (08.2), cameras (09.1.1), "
                   "electric personal-care appliances (13.1.1).",
    "Housing": "Cash housing payments: actual rents (04.1), maintenance charges of housing companies / hoitovastike "
               "(04.4.4.1), interest on housing loans (04.6.3). Excludes imputed rent (04.2) and loan principal "
               "(not consumption, not in the survey).",
    "Lifestyle": "Clothing and footwear (03), games/toys/hobby and sports goods (09.2), musical instruments and media "
                 "(09.5), books/newspapers/stationery (09.7), jewellery, watches, bags and other personal effects (13.2).",
    "Travel": "Flights (07.3.3), ferries (07.3.4), car hire (07.2.4.4), package holidays (09.8), accommodation (11.2). "
              "Spending abroad (77) is not allocated to categories by the survey and is excluded here.",
}

CONS_TABLES = {
    # key: (table, group variable, total code)
    "by_age_group": ("StatFin/ktutk/14q4.px", "ikaryhma_10_20180101", "SSS"),
    "by_household_type": ("StatFin/ktutk/14ph.px", "elinvaihe_13_20160101", "SSS"),
    "by_income_quintile": ("StatFin/ktutk/14pg.px", "tuloviidennes_2_20140501", "SS"),
    "by_region": ("StatFin/ktutk/14q8.px", "alue_23_20240101", "SSS"),
    "by_municipality_type": ("StatFin/ktutk/14q7.px", "alue_23_20240101", "SSS"),
}
BACKGROUND_TABLES = {
    "by_age_group": "StatFin/ktutk/14q9.px",
    "by_household_type": "StatFin/ktutk/14lv.px",
    "by_income_quintile": "StatFin/ktutk/14qa.px",
    "by_region": "StatFin/ktutk/14qd.px",
    "by_municipality_type": "StatFin/ktutk/14qc.px",
    "by_household_structure": "StatFin/ktutk/14qb.px",
}
STRUCTURE_TABLE = ("StatFin/ktutk/14q5.px", "kotital_koko_3_20160101", "SSS")
COICOP_VAR = "coicop_46_20231201"
C_HH_YEAR = "kulu_kt_hk_1_1"     # household, current prices, EUR/year
C_CU_YEAR = "kulu_kt_hk_2_1"     # per consumption unit, current prices, EUR/year
C_HH_MONTH = "kulukk_kt_hk_1_1"  # household, EUR/month as published (integer)
C_CU_MONTH = "kulukk_kt_hk_2_1"
DIVISIONS = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "77"]

GROUP_KEYS = {  # friendlier keys for the JSON; source code kept in "source_code"
    "by_income_quintile": {"1": "q1_lowest", "2": "q2", "3": "q3", "4": "q4", "5": "q5_highest"},
    "by_household_type": {
        "1": "one_person_under_65", "2": "couple_no_children_under_65", "3": "single_parent",
        "4": "two_parents_with_children", "5": "aged_65_plus_households", "6": "other_households",
    },
    "by_region": {"SA1": "helsinki_uusimaa", "SA2": "southern_finland", "SA3": "western_finland",
                  "SA4": "northern_and_eastern_finland", "SA5": "aland"},
    "by_municipality_type": {"TK1": "urban", "TK2": "semi_urban", "TK3": "rural"},
    "by_household_structure": {
        "1": "1_adult", "2": "1_adult_1_2_children", "3": "2_adults", "4": "2_adults_1_child",
        "5": "2_adults_2_children", "6": "2_adults_3_children", "7": "3_adults",
        "8": "3_adults_1_child", "9": "others",
    },
}


def all_used_codes() -> list[str]:
    used = {"0", "99"} | set(DIVISIONS)
    for d in (APP_MAP, NOT_MAPPED, VARIANTS):
        for codes in d.values():
            used.update(codes)
    return sorted(used)


# --------------------------------------------------------------------------
# CPI
# --------------------------------------------------------------------------

CPI_TABLE = "StatFin/khi/15b5.px"


def fetch_cpi(survey_year: int, codes: list[str]) -> dict:
    meta = px_meta(CPI_TABLE)
    months = list(meta["vars"]["timeperiod_m"]["values"])
    latest = months[-1]
    target_year = int(latest[:4])
    base_months = [m for m in months if m.startswith(str(survey_year))]
    target_months = [m for m in months if m.startswith(str(target_year))]
    cpi_codes = set(meta["vars"][COICOP_VAR]["values"])
    want = {"SSS"}
    for c in codes:
        for n in range(len(c), 1, -1):
            if c[:n] in cpi_codes:
                want.add(c[:n])
    want = sorted(want)
    res = px_query(CPI_TABLE, {"timeperiod_m": base_months + target_months,
                               COICOP_VAR: want, "contentscode": ["ip_khi"]})

    def avg(code, ms):
        vals = [res.get(timeperiod_m=m, **{COICOP_VAR: code}, contentscode="ip_khi") for m in ms]
        if any(v is None for v in vals):
            return None
        return sum(vals) / len(vals)

    index = {}
    for c in want:
        a, b = avg(c, base_months), avg(c, target_months)
        if a and b:
            index[c] = {"avg_survey_year": round(a, 3), "avg_target_year": round(b, 3),
                        "factor": round(b / a, 5)}

    def resolve(code: str) -> str:
        for n in range(len(code), 1, -1):
            if code[:n] in index:
                return code[:n]
        return "SSS"

    return {
        "table": CPI_TABLE, "updated": res.updated, "base": "2025=100",
        "survey_year": survey_year, "target_year": target_year,
        "survey_year_months": [base_months[0], base_months[-1]],
        "target_year_months": [target_months[0], target_months[-1]],
        "n_target_months": len(target_months),
        "index": index, "resolve": resolve,
        "labels": {c: meta["vars"][COICOP_VAR]["values"][c] for c in want},
    }


# --------------------------------------------------------------------------
# Household Budget Survey
# --------------------------------------------------------------------------


def money(v):
    return None if v is None else round(v, 2)


def build_cell(yearly_by_code: dict, codes: list[str], cpi: dict, ty: int) -> dict:
    """Sum COICOP components (EUR/year) into one monthly benchmark value."""
    present = [c for c in codes if yearly_by_code.get(c) is not None]
    missing = [c for c in codes if yearly_by_code.get(c) is None]
    if not present:
        return {"eur_month_survey_year": None, "components_missing": missing}
    year_sum = sum(yearly_by_code[c] for c in present)
    headline = cpi["index"]["SSS"]["factor"]
    cat = sum(yearly_by_code[c] * cpi["index"][cpi["resolve"](c)]["factor"] for c in present)
    out = {
        "eur_month_survey_year": money(year_sum / 12),
        f"eur_month_{ty}": money(year_sum / 12 * headline),
        f"eur_month_{ty}_category_cpi": money(cat / 12),
    }
    if missing:
        out["components_missing"] = missing
    return out


def build_unit_block(yearly: dict, cpi: dict, ty: int, with_app: bool = True) -> dict:
    blk = {"total_consumption": build_cell(yearly, ["0"], cpi, ty)}
    # category-CPI total = sum of divisions each inflated by its own index
    div_present = [d for d in DIVISIONS if yearly.get(d) is not None]
    if div_present and yearly.get("0") is not None:
        blk["total_consumption"][f"eur_month_{ty}_category_cpi"] = money(
            sum(yearly[d] * cpi["index"][cpi["resolve"](d)]["factor"] for d in div_present) / 12)
    if with_app:
        blk["app_categories"] = {k: build_cell(yearly, v, cpi, ty) for k, v in APP_MAP.items()}
        blk["app_category_variants"] = {k: build_cell(yearly, v, cpi, ty) for k, v in VARIANTS.items()}
        blk["not_mapped"] = {k: build_cell(yearly, v, cpi, ty) for k, v in NOT_MAPPED.items()}
    blk["coicop_divisions"] = {d: build_cell(yearly, [d], cpi, ty) for d in DIVISIONS}
    if yearly.get("99") is not None:
        blk["items_outside_consumption_expenditure"] = build_cell(yearly, ["99"], cpi, ty)
    return blk


def fetch_background(table: str, year: str) -> dict:
    meta = px_meta(table)
    gvar = [v for v in meta["vars"] if v not in ("timeperiod_y", "contentscode")][0]
    groups = list(meta["vars"][gvar]["values"])
    contents = list(meta["vars"]["contentscode"]["values"])
    res = px_query(table, {"timeperiod_y": [year], gvar: groups, "contentscode": contents})
    names = {"oklkm_sum": "households_in_sample", "pklkm_sum": "households_in_population",
             "jlkm_mean": "avg_household_size_persons", "oecdmod_mean": "avg_consumption_units",
             "kaytetmk_1_mean": "disposable_income_per_household_eur_year"}
    out = {}
    for g in groups:
        row = {}
        for c in contents:
            n = names.get(c.lower())
            if n:
                row[n] = res.get(timeperiod_y=year, **{gvar: g}, contentscode=c)
        out[g] = row
    return {"rows": out, "updated": res.updated}


def fetch_consumption(cpi_holder: dict) -> tuple[dict, dict]:
    """Returns (sections, meta_bits). cpi_holder is filled once the survey year is known."""
    sections, tables_meta = {}, {}
    checks = {"max_abs_diff_total_vs_mapped_eur_year": 0, "max_abs_diff_total_vs_mapped_group": None,
              "max_abs_diff_total_vs_mapped_eur_year_groups_with_100plus_sample": 0,
              "max_abs_diff_published_month_vs_year_div_12": 0.0}
    used = all_used_codes()
    survey_year = None
    for key, (table, gvar, total_code) in CONS_TABLES.items():
        meta = px_meta(table)
        years = list(meta["vars"]["timeperiod_y"]["values"])
        year = years[-1]
        if survey_year is None:
            survey_year = int(year)
            cpi_holder.update(fetch_cpi(survey_year, used))
        ty = cpi_holder["target_year"]
        codes = [c for c in used if c in meta["vars"][COICOP_VAR]["values"]]
        groups = list(meta["vars"][gvar]["values"])
        res = px_query(table, {"timeperiod_y": [year], COICOP_VAR: codes, gvar: groups,
                               "contentscode": [C_HH_YEAR, C_CU_YEAR, C_HH_MONTH, C_CU_MONTH]})
        bg = fetch_background(BACKGROUND_TABLES[key], year)
        tables_meta[key] = {"table": table, "title": meta["title"], "year": year, "updated": res.updated,
                            "background_table": BACKGROUND_TABLES[key]}
        section = {}
        for g in groups:
            def col(content):
                return {c: res.get(timeperiod_y=year, **{COICOP_VAR: c, gvar: g}, contentscode=content)
                        for c in codes}
            hh, cu = col(C_HH_YEAR), col(C_CU_YEAR)
            entry = {
                "label": meta["vars"][gvar]["values"][g].strip(),
                "source_code": g,
                "background": bg["rows"].get(g, {}),
                "per_household": build_unit_block(hh, cpi_holder, ty),
                "per_consumption_unit": build_unit_block(cu, cpi_holder, ty),
            }
            n = entry["background"].get("households_in_sample")
            entry["low_sample"] = bool(n is not None and n < 100)
            # self-checks
            for unit, ycol, mcontent in (("hh", hh, C_HH_MONTH), ("cu", cu, C_CU_MONTH)):
                if ycol.get("0") is not None:
                    mapped = sum(ycol[c] for cs in list(APP_MAP.values()) + list(NOT_MAPPED.values())
                                 for c in cs if ycol.get(c) is not None)
                    diff = abs(ycol["0"] - mapped)
                    if diff > checks["max_abs_diff_total_vs_mapped_eur_year"]:
                        checks["max_abs_diff_total_vs_mapped_eur_year"] = diff
                        checks["max_abs_diff_total_vs_mapped_group"] = f"{key}/{g}/{unit}"
                    if (entry["background"].get("households_in_sample") or 0) >= 100:
                        checks["max_abs_diff_total_vs_mapped_eur_year_groups_with_100plus_sample"] = max(
                            checks["max_abs_diff_total_vs_mapped_eur_year_groups_with_100plus_sample"], diff)
                for c in ["0"] + DIVISIONS:
                    pub = res.get(timeperiod_y=year, **{COICOP_VAR: c, gvar: g}, contentscode=mcontent)
                    if pub is not None and ycol.get(c) is not None:
                        checks["max_abs_diff_published_month_vs_year_div_12"] = max(
                            checks["max_abs_diff_published_month_vs_year_div_12"],
                            round(abs(pub - ycol[c] / 12), 3))
            if g == total_code:
                if key == "by_age_group":
                    sections["all_households"] = entry
                continue
            if key == "by_age_group":
                lo, _, hi = g.partition("-")
                entry["age_min"], entry["age_max"] = int(lo), (int(hi) if hi else None)
            section[GROUP_KEYS.get(key, {}).get(g, g)] = entry
        sections[key] = section

    # household size/structure: only COICOP divisions are published
    table, gvar, total_code = STRUCTURE_TABLE
    meta = px_meta(table)
    year = list(meta["vars"]["timeperiod_y"]["values"])[-1]
    codes = [c for c in ["0", "99"] + DIVISIONS if c in meta["vars"][COICOP_VAR]["values"]]
    groups = list(meta["vars"][gvar]["values"])
    res = px_query(table, {"timeperiod_y": [year], COICOP_VAR: codes, gvar: groups,
                           "contentscode": [C_HH_YEAR, C_CU_YEAR]})
    bg = fetch_background(BACKGROUND_TABLES["by_household_structure"], year)
    ty = cpi_holder["target_year"]
    section = {}
    for g in groups:
        if g == total_code:
            continue
        hh = {c: res.get(timeperiod_y=year, **{COICOP_VAR: c, gvar: g}, contentscode=C_HH_YEAR) for c in codes}
        cu = {c: res.get(timeperiod_y=year, **{COICOP_VAR: c, gvar: g}, contentscode=C_CU_YEAR) for c in codes}
        section[GROUP_KEYS["by_household_structure"].get(g, g)] = {
            "label": meta["vars"][gvar]["values"][g].strip(), "source_code": g,
            "background": bg["rows"].get(g, {}),
            "per_household": build_unit_block(hh, cpi_holder, ty, with_app=False),
            "per_consumption_unit": build_unit_block(cu, cpi_holder, ty, with_app=False),
        }
    sections["by_household_structure"] = section
    tables_meta["by_household_structure"] = {
        "table": table, "title": meta["title"], "year": year, "updated": res.updated,
        "background_table": BACKGROUND_TABLES["by_household_structure"],
        "note": "Only 2-digit COICOP divisions are published for this breakdown, so no app categories."}

    coicop_labels = px_meta(CONS_TABLES["by_age_group"][0])["vars"][COICOP_VAR]["values"]
    return sections, {"survey_year": survey_year, "tables": tables_meta, "self_checks": checks,
                      "coicop_labels": {c: coicop_labels[c].strip() for c in used if c in coicop_labels}}


# --------------------------------------------------------------------------
# Income distribution, saving rate, housing cost burden
# --------------------------------------------------------------------------


def fetch_income() -> tuple[dict, dict, dict]:
    t1 = "StatFin/tjt/11py.px"
    m = px_meta(t1)
    year = list(m["vars"]["timeperiod_y"]["values"])[-1]
    ages = [a for a in ["SSS", "18-", "18-24", "25-34", "35-49", "50-64", "65-74", "75-", "18-64", "65-"]
            if a in m["vars"]["ikaryhma_22_20191201"]["values"]]
    cont = {"tjt-henkiloita": "persons",
            "hkturaha_med": "personal_disposable_monetary_income_median_eur_year",
            "hkturaha_mean": "personal_disposable_monetary_income_mean_eur_year",
            "tjt-ekvikturaha_med": "disposable_monetary_income_per_consumption_unit_median_eur_year",
            "tjt-ekvikturaha_mean": "disposable_monetary_income_per_consumption_unit_mean_eur_year"}
    r = px_query(t1, {"ikaryhma_22_20191201": ages, "contentscode": list(cont),
                      "timeperiod_y": [year], "sukupuoli_9_20180101": ["SSS"]})
    by_person = {}
    for a in ages:
        row = {"label": m["vars"]["ikaryhma_22_20191201"]["values"][a]}
        for c, name in cont.items():
            v = r.get(ikaryhma_22_20191201=a, contentscode=c, timeperiod_y=year, sukupuoli_9_20180101="SSS")
            row[name] = v
            if name.endswith("_eur_year") and v is not None:
                row[name.replace("_eur_year", "_eur_month")] = money(v / 12)
        by_person["all" if a == "SSS" else a.replace("-", "_") if a.endswith("-") is False else a[:-1] + "_plus"] = row
    src1 = {"table": t1, "title": m["title"], "year": year, "updated": r.updated}

    t2 = "StatFin/tjt/12eb.px"
    m = px_meta(t2)
    year2 = list(m["vars"]["timeperiod_y"]["values"])[-1]
    ages2 = list(m["vars"]["ikaryhma_10_20180101"]["values"])
    cont2 = {"tjt-kotital": "households",
             "KOKONUM_Mean": "avg_household_size_persons",
             "kvkturaha_med": "disposable_monetary_income_per_household_median_eur_year",
             "kvkturaha_mean": "disposable_monetary_income_per_household_mean_eur_year",
             "ekvikvkturaha_med": "disposable_monetary_income_per_consumption_unit_median_eur_year"}
    r2 = px_query(t2, {"ikaryhma_10_20180101": ages2, "contentscode": list(cont2), "timeperiod_y": [year2]})
    by_hh = {}
    for a in ages2:
        row = {"label": m["vars"]["ikaryhma_10_20180101"]["values"][a].strip()}
        for c, name in cont2.items():
            v = r2.get(ikaryhma_10_20180101=a, contentscode=c, timeperiod_y=year2)
            row[name] = v
            if name.endswith("_eur_year") and v is not None:
                row[name.replace("_eur_year", "_eur_month")] = money(v / 12)
        key = "all" if a == "SSS" else (a[:-1] + "_plus" if a.endswith("-") else a.replace("-", "_"))
        by_hh[key] = row
    src2 = {"table": t2, "title": m["title"], "year": year2, "updated": r2.updated}
    return by_person, by_hh, {"median_income_by_age": src1,
                              "household_income_by_age_of_reference_person": src2}


def fetch_saving_rate() -> tuple[dict, dict]:
    tq = "StatFin/ntp/15a8.px"
    m = px_meta(tq)
    quarters = list(m["vars"]["timeperiod_q"]["values"])[-12:]
    cont = {"ntp-kausit_b8n": "saving_rate_pct_seasonally_adjusted",
            "ntp-tasm_b8n": "saving_rate_pct_original",
            "ntp-tasm_f4": "indebtedness_rate_pct_original"}
    r = px_query(tq, {"timeperiod_q": quarters, "sektoriluokitus_7_20230101": ["S14"],
                      "contentscode": list(cont)})
    quarterly = {q: {name: r.get(timeperiod_q=q, sektoriluokitus_7_20230101="S14", contentscode=c)
                     for c, name in cont.items()} for q in quarters}

    ta = "StatFin/ntp/15ac.px"
    ma = px_meta(ta)
    ylabels = ma["vars"]["timeperiod_y"]["values"]
    years = list(ylabels)[-6:]
    tx = ["B6N", "D8R", "B8N", "P31K"]
    ra = px_query(ta, {"sektoriluokitus_7_20230101": ["S14"], "taloustoimi_1_20180101": tx,
                       "timeperiod_y": years, "contentscode": ["ntp-cp"]})
    annual = {}
    for y in years:
        v = {t: ra.get(sektoriluokitus_7_20230101="S14", taloustoimi_1_20180101=t,
                       timeperiod_y=y, contentscode="ntp-cp") for t in tx}
        row = {"net_disposable_income_B6N_meur": v["B6N"],
               "pension_entitlement_adjustment_D8R_meur": v["D8R"],
               "net_saving_B8N_meur": v["B8N"],
               "consumption_expenditure_P31K_meur": v["P31K"],
               "preliminary": ylabels[y].endswith("*")}
        if None not in (v["B6N"], v["D8R"], v["B8N"]):
            row["saving_rate_pct_derived"] = round(100 * v["B8N"] / (v["B6N"] + v["D8R"]), 2)
        annual[y] = row
    out = {
        "sector": "S14 Households",
        "definition": "Net saving (B8N) as % of net disposable income (B6N) plus the adjustment for the "
                      "change in pension entitlements (D8R).",
        "latest_quarter": quarters[-1],
        "quarterly": quarterly,
        "annual": annual,
        "annual_note": "saving_rate_pct_derived is computed here from the published sector-account "
                       "aggregates (B8N / (B6N + D8R)); the published rate itself is the quarterly series.",
    }
    return out, {"saving_rate_quarterly": {"table": tq, "title": m["title"], "updated": r.updated},
                 "saving_rate_annual": {"table": ta, "title": ma["title"], "updated": ra.updated}}


def fetch_housing_burden() -> tuple[dict, dict]:
    t = "StatFin/tjt/12g9.px"
    m = px_meta(t)
    year = list(m["vars"]["timeperiod_y"]["values"])[-1]
    tenures = list(m["vars"]["hallintasuhde_3_20120501"]["values"])
    stages = list(m["vars"]["elinvaihe_5_20200201"]["values"])
    cont = {"tjt-kotital": "households",
            "askpros2": "housing_costs_share_of_net_income_pct_median",
            "askpros2m": "housing_costs_share_of_net_income_pct_mean",
            "kvkturahamod": "disposable_monetary_income_per_consumption_unit_median_eur_year",
            "akkturahamod": "income_after_housing_costs_per_consumption_unit_median_eur_year"}
    r = px_query(t, {"timeperiod_y": [year], "hallintasuhde_3_20120501": tenures,
                     "elinvaihe_5_20200201": stages, "contentscode": list(cont)})
    tkey = {"SS": "all_tenures", "1": "owner_occupied", "2": "rented", "3": "other"}
    out = {}
    for tn in tenures:
        blk = {}
        for s in stages:
            row = {"label": m["vars"]["elinvaihe_5_20200201"]["values"][s].strip()}
            for c, name in cont.items():
                row[name] = r.get(timeperiod_y=year, hallintasuhde_3_20120501=tn,
                                  elinvaihe_5_20200201=s, contentscode=c)
            blk["all_households" if s == "SS" else "stage_" + s] = row
        out[tkey.get(tn, tn)] = blk
    return out, {"housing_cost_burden": {"table": t, "title": m["title"], "year": year, "updated": r.updated}}


# --------------------------------------------------------------------------
# Reference budgets (University of Helsinki, Centre for Consumer Society Research)
# --------------------------------------------------------------------------

RB_PDF = "https://helda.helsinki.fi/server/api/core/bitstreams/3790704c-2d4a-42e2-807b-c5c5bc5c9498/content"
RB_LANDING = "https://helda.helsinki.fi/items/9dcd00a2-ca32-4871-8787-e176aa7e31e8"
RB_ROWS = [
    ("items", "food"), ("items", "clothing"), ("items", "telecom_and_consumer_electronics"),
    ("items", "household_durables"), ("items", "household_nondurables"),
    ("items", "hygiene_and_beauty"), ("items", "health_care"), ("items", "leisure_and_hobbies"),
    ("items", "electricity_and_insurance"),
    ("subtotals", "excl_food_transport_rent"), ("subtotals", "excl_transport_rent"),
    ("transport", "helsinki_metropolitan_area"), ("transport", "rest_of_finland"),
    ("housing_rent", "helsinki"), ("housing_rent", "helsinki_metropolitan_area"),
    ("housing_rent", "other_cities_over_100k"), ("housing_rent", "rest_of_finland"),
    ("total", "helsinki"), ("total", "helsinki_metropolitan_area"),
    ("total", "other_cities_over_100k"), ("total", "rest_of_finland"),
    ("total", "whole_country_average"),
]
RB_TABLES = {
    "Taulukko 19.": [
        ("single_man_under_45", "Yksin asuva mies alle 45 v. (M 45v)"),
        ("single_woman_under_45", "Yksin asuva nainen alle 45 v. (N 45v)"),
        ("single_man_over_65", "Yksin asuva mies yli 65 v. (M 65v)"),
        ("single_woman_over_65", "Yksin asuva nainen yli 65 v. (N 65v)"),
        ("couple_50", "Pari 50 v."),
        ("couple_woman_50_man_65", "Pari, nainen 50 v. ja mies 65 v."),
        ("couple_over_65", "Pari yli 65 v."),
    ],
    "Taulukko 20.": [
        ("single_parent_1_child_girl_3", "Yksinhuoltajaperhe (tytto 3 v.)"),
        ("single_parent_1_child_girl_14", "Yksinhuoltajaperhe (tytto 14 v.)"),
        ("single_parent_2_children_boy_10_girl_13", "Yksinhuoltajaperhe (poika 10 v., tytto 13 v.)"),
        ("two_parents_2_children_boy_2_girl_6", "Pikkulapsiperhe (poika 2 v., tytto 6 v.)"),
        ("two_parents_2_children_boy_4_girl_10", "Lapsiperhe (poika 4 v., tytto 10 v.)"),
        ("two_parents_2_teens_girl_14_boy_16", "Teiniperhe (tytto 14 v., poika 16 v.)"),
        ("two_parents_3_children_boy_10_boy_15_girl_17", "Teiniperhe (poika 10 v., poika 15 v., tytto 17 v.)"),
    ],
}
RB_ITEM_HINT = {
    "food": "Groceries", "clothing": "Lifestyle",
    "telecom_and_consumer_electronics": "Utilities (subscriptions) + Home & Tech (devices)",
    "household_durables": "Home & Tech", "household_nondurables": "Groceries",
    "hygiene_and_beauty": "Groceries (products); hairdresser not in any app category",
    "health_care": "Health", "leisure_and_hobbies": "Entertainment + Lifestyle",
    "electricity_and_insurance": "Utilities (electricity); insurance not in any app category",
    "transport": "Transportation", "housing_rent": "Housing",
}


def parse_rb_table(lines: list[str], start: str, stops: tuple[str, ...]) -> list[list[int]]:
    i0 = next(i for i, l in enumerate(lines) if l.startswith(start) and "e/kk" in l)
    rows = []
    pat = re.compile(r"^(.*?)\s+((?:\d+\s+){6}\d+)\s*$")
    for l in lines[i0 + 1:]:
        if l.startswith(stops):
            break
        mt = pat.match(l)
        if mt:
            rows.append([int(x) for x in mt.group(2).split()])
    return rows


def fetch_reference_budgets() -> tuple[dict, dict]:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext (poppler-utils) is needed to read the reference budget report")
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "viitebudjetit.pdf"
        pdf.write_bytes(_request("GET", RB_PDF).content)
        txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True,
                             capture_output=True, text=True).stdout
    lines = txt.splitlines()
    if not any("VIITEBUDJETTIEN" in l for l in lines[:40]):
        raise RuntimeError("unexpected PDF content for reference budgets")
    households, problems = {}, []
    stops = ("Taulukko 20.", "Taulukko 21.", "5.2 ")
    for tname, cols in RB_TABLES.items():
        rows = parse_rb_table(lines, tname, tuple(s for s in stops if s != tname))
        if len(rows) != len(RB_ROWS):
            raise RuntimeError(f"{tname}: expected {len(RB_ROWS)} numeric rows, got {len(rows)}")
        for ci, (key, label) in enumerate(cols):
            hh = {"label_fi": label, "source_table": tname.rstrip(".").replace("Taulukko", "Table")}
            for (grp, name), row in zip(RB_ROWS, rows):
                hh.setdefault(grp, {})[name] = row[ci]
            it, st, tr, rent, tot = (hh[k] for k in ("items", "subtotals", "transport", "housing_rent", "total"))
            if sum(it.values()) != st["excl_transport_rent"]:
                problems.append(f"{key}: items do not sum to subtotal")
            if st["excl_transport_rent"] - it["food"] != st["excl_food_transport_rent"]:
                problems.append(f"{key}: subtotal excl. food mismatch")
            for region, tkey in (("helsinki", "helsinki_metropolitan_area"),
                                 ("helsinki_metropolitan_area", "helsinki_metropolitan_area"),
                                 ("other_cities_over_100k", "rest_of_finland"),
                                 ("rest_of_finland", "rest_of_finland")):
                calc = st["excl_transport_rent"] + tr[tkey] + rent[region]
                if calc != tot[region]:
                    problems.append(f"{key}: printed total for {region} is {tot[region]}, "
                                    f"components sum to {calc} (value kept as printed)")
            households[key] = hh
    out = {
        "edition": "Kohtuullinen ja kestava kulutus: kohtuullisen minimin viitebudjettien paivitys vuodelle 2025",
        "price_year": 2025, "unit": "EUR per month",
        "what_it_is": "Decent-minimum reference budgets: the cost of a basket that covers needs and social "
                      "participation, NOT average spending. Rent is for a rented flat; transport is local public "
                      "transport (a car only in households of more than 3 persons outside the capital region).",
        "households": households,
        "item_to_app_category_hint": RB_ITEM_HINT,
        "arithmetic_check": "items sum to subtotals, and subtotals + transport + rent sum to totals, in every "
                            "column" + ("" if not problems else " except those listed in source_inconsistencies"),
        "source_inconsistencies": problems,
        "note_on_press_figures": "The tables in the 19 Nov 2025 press material differ slightly from this final "
                                 "report (leisure for families +7 to +14 EUR, health of the 65+ couple 72 vs 76); "
                                 "the final report is used here.",
    }
    src = {"reference_budgets": {
        "publisher": "University of Helsinki, Faculty of Social Sciences (Centre for Consumer Society Research)",
        "authors": "Poyry, Pekuri, Seppanen, Savolainen, Lehtinen",
        "series": "Valtiotieteellisen tiedekunnan julkaisuja 2026:265, ISBN 978-952-84-0057-8",
        "url": RB_LANDING, "pdf_url": RB_PDF, "tables": "Taulukko 19 and Taulukko 20 (pp. 68-69)"}}
    return out, src


# --------------------------------------------------------------------------
# Paavo (postal code areas)
# --------------------------------------------------------------------------


def latest_paavo_folder() -> str:
    dbs = _request("GET", API + "Postinumeroalueittainen_avoin_tieto/").json()
    years = sorted(d["id"] for d in dbs if d["id"].isdigit())
    return years[-1]


def fetch_paavo() -> dict:
    folder = latest_paavo_folder()
    base = f"Postinumeroalueittainen_avoin_tieto/{folder}/"
    listing = _request("GET", API + base).json()
    t_area = next(t["id"] for t in listing if t["id"].startswith("12f7"))
    t_muni = next(t["id"] for t in listing if t["id"].startswith("12f8"))
    cont = {"he_vakiy": "inhabitants", "he_kika": "avg_age",
            "hr_tuy": "adults_18_plus", "hr_mtu": "median_income_eur_year",
            "hr_ktu": "avg_income_eur_year",
            "te_taly": "households", "te_takk": "avg_household_size",
            "tr_mtu": "household_median_income_eur_year", "tr_ktu": "household_avg_income_eur_year",
            "te_omis_as": "households_owner_occupied", "te_vuok_as": "households_rented"}

    def table(tid: str):
        m = px_meta(base + tid)
        avar = [v for v in m["vars"] if v not in ("timeperiod_y", "contentscode")][0]
        year = list(m["vars"]["timeperiod_y"]["values"])[-1]
        codes = list(m["vars"][avar]["values"])
        r = px_query(base + tid, {avar: codes, "timeperiod_y": [year], "contentscode": list(cont)})
        rows = {}
        for c in codes:
            row = {}
            for k, name in cont.items():
                v = r.get(**{avar: c}, timeperiod_y=year, contentscode=k)
                if v is not None:
                    row[name] = v
            for name in ("median_income_eur_year", "avg_income_eur_year"):
                if name in row:
                    row[name.replace("_eur_year", "_eur_month")] = money(row[name] / 12)
            rows[c] = (m["vars"][avar]["values"][c], row)
        return rows, year, r.updated, m["title"]

    area_rows, year, updated, title = table(t_area)
    muni_rows, myear, mupdated, mtitle = table(t_muni)

    areas, country = {}, None
    for code, (label, row) in area_rows.items():
        if code == "SSS":
            country = row
            continue
        mt = re.match(r"^\d{5}\s+(.*?)\s*\(([^()]*)\)\s*$", label)
        row = {"name": mt.group(1) if mt else label, "municipality": mt.group(2) if mt else None, **row}
        areas[code] = row

    municipalities = {}
    for code, (label, row) in muni_rows.items():
        if code.startswith("KU"):
            municipalities[label.strip()] = {"code": code, **row}

    # prefix -> dominant municipality (by inhabitants) for postal codes that are not Paavo areas
    def prefix_map(n: int) -> dict:
        acc: dict[str, dict[str, int]] = {}
        for code, row in areas.items():
            if row.get("municipality"):
                acc.setdefault(code[:n], {}).setdefault(row["municipality"], 0)
                acc[code[:n]][row["municipality"]] += row.get("inhabitants") or 0
        out = {}
        for p, d in sorted(acc.items()):
            best = max(d, key=d.get)
            tot = sum(d.values())
            out[p] = {"municipality": best,
                      "share_of_prefix_inhabitants": round(d[best] / tot, 3) if tot else None}
        return out

    return {
        "meta": {
            "source": "Statistics Finland, Paavo - Open data by postal code area",
            "edition": f"Paavo {folder}", "statistical_year": year,
            "tables": {
                "areas": {"table": base + t_area, "title": title, "updated": updated,
                          "api_url": API + base + t_area,
                          "web_ui_url": f"https://pxdata.stat.fi/PxWeb/pxweb/en/Postinumeroalueittainen_avoin_tieto/"
                                        f"Postinumeroalueittainen_avoin_tieto__{folder}/{t_area}/"},
                "municipalities": {"table": base + t_muni, "title": mtitle, "updated": mupdated,
                                   "api_url": API + base + t_muni},
            },
            "retrieved": dt.date.today().isoformat(),
            "licence": "CC BY 4.0, Statistics Finland",
            "fields": {
                "inhabitants": "he_vakiy: inhabitants at 31 Dec of the statistical year",
                "avg_age": "he_kika: average age of inhabitants, years",
                "adults_18_plus": "hr_tuy: inhabitants aged 18+ (population of the income figures)",
                "median_income_eur_year": "hr_mtu: median disposable monetary income of inhabitants aged 18+, EUR/year",
                "avg_income_eur_year": "hr_ktu: average disposable monetary income of inhabitants aged 18+, EUR/year",
                "*_eur_month": "the yearly value divided by 12",
                "households": "te_taly: household-dwelling units",
                "avg_household_size": "te_takk: persons",
                "household_median_income_eur_year": "tr_mtu: median disposable monetary income of households, EUR/year",
                "household_avg_income_eur_year": "tr_ktu: average disposable monetary income of households, EUR/year",
                "households_owner_occupied": "te_omis_as", "households_rented": "te_vuok_as",
            },
            "lookup_order": "areas[postal_code] -> municipalities[prefix3_to_municipality[code[:3]]] -> "
                            "municipalities[prefix2_to_municipality[code[:2]]] -> whole_country. Postal codes that "
                            "are PO boxes or company codes are not Paavo areas. A key is absent where the source "
                            "value is suppressed (fewer than 30 adults or households).",
            "n_areas": len(areas), "n_municipalities": len(municipalities),
        },
        "whole_country": country,
        "areas": areas,
        "municipalities": municipalities,
        "prefix3_to_municipality": prefix_map(3),
        "prefix2_to_municipality": prefix_map(2),
    }


# --------------------------------------------------------------------------


def dump_one_row_per_line(obj: dict) -> str:
    """Pretty top level, one line per postal code / municipality / prefix."""
    parts = []
    for k, v in obj.items():
        if k in ("areas", "municipalities", "prefix3_to_municipality", "prefix2_to_municipality"):
            rows = ",\n".join(f"  {json.dumps(a, ensure_ascii=False)}: {json.dumps(r, ensure_ascii=False)}"
                              for a, r in v.items())
            parts.append(f" {json.dumps(k)}: {{\n{rows}\n }}")
        else:
            parts.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, indent=1)}")
    return "{\n" + ",\n".join(parts) + "\n}\n"


def ui_url(table: str) -> str:
    db, subject, tid = table.split("/")
    return f"https://pxdata.stat.fi/PxWeb/pxweb/en/{db}/{db}__{subject}/{tid}/"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()

    cpi: dict = {}
    sections, cons_meta = fetch_consumption(cpi)
    by_person, by_hh, income_src = fetch_income()
    saving, saving_src = fetch_saving_rate()
    burden, burden_src = fetch_housing_burden()
    refb, refb_src = fetch_reference_budgets()

    ty = cpi["target_year"]
    used_idx = sorted({cpi["resolve"](c) for c in all_used_codes()} | {"SSS"})
    sources = {}
    for k, v in cons_meta["tables"].items():
        sources[f"consumption_{k}"] = {**v, "api_url": API + v["table"], "web_ui_url": ui_url(v["table"]),
                                       "background_api_url": API + v["background_table"]}
    for group in (income_src, saving_src, burden_src):
        for k, v in group.items():
            sources[k] = {**v, "api_url": API + v["table"], "web_ui_url": ui_url(v["table"])}
    sources["cpi"] = {"table": cpi["table"], "title": "Consumer Price Index (2025=100), monthly",
                      "updated": cpi["updated"], "api_url": API + cpi["table"], "web_ui_url": ui_url(cpi["table"])}
    sources.update(refb_src)

    meta = {
        "retrieved": today,
        "publisher": "Statistics Finland (StatFin PxWeb API), licence CC BY 4.0; reference budgets: University of Helsinki",
        "survey": "Household Budget Survey (Kotitalouksien kulutus)",
        "survey_year": cons_meta["survey_year"],
        "units": {
            "eur_month_survey_year": f"EUR per month at {cons_meta['survey_year']} prices = published EUR/year / 12",
            f"eur_month_{ty}": f"the same inflated with the headline CPI factor ({cpi['index']['SSS']['factor']})",
            f"eur_month_{ty}_category_cpi": "each COICOP component inflated with its own CPI sub-index "
                                            "(nearest parent index if the component has none), then summed",
            "per_household": "mean per household in the group (all household sizes mixed)",
            "per_consumption_unit": "mean per OECD-modified consumption unit (1.0 first adult, 0.5 each other "
                                    "person aged 14+, 0.3 each child under 14); use this for one adult",
        },
        "cpi": {
            "table": cpi["table"], "base": cpi["base"],
            "survey_year_average_months": cpi["survey_year_months"],
            "target_year": ty, "target_year_average_months": cpi["target_year_months"],
            "target_year_is_partial": cpi["n_target_months"] < 12,
            "headline": cpi["index"]["SSS"],
            "by_coicop": {c: {"label": cpi["labels"][c].strip(), **cpi["index"][c]} for c in used_idx},
            "index_used_for_component": {c: cpi["resolve"](c) for c in all_used_codes() if c not in ("0", "99")},
        },
        "category_mapping": {
            "classification": "COICOP 2018 as used in the Household Budget Survey 2022",
            "app_categories": {k: {"coicop": v, "note": MAPPING_NOTES[k]} for k, v in APP_MAP.items()},
            "variants": VARIANTS,
            "not_mapped": NOT_MAPPED,
            "coicop_labels": cons_meta["coicop_labels"],
            "rule": "app_categories + not_mapped partition total consumption expenditure (code 0) exactly; "
                    "code 99 is outside consumption expenditure.",
        },
        "self_checks": cons_meta["self_checks"],
        "missing_values": "null = suppressed or not available at the source. components_missing lists COICOP "
                          "components that were null and therefore counted as 0 in a sum.",
        "sources": sources,
    }

    out = {
        "meta": meta,
        "all_households": sections["all_households"],
        "by_age_group": sections["by_age_group"],
        "by_household_type": sections["by_household_type"],
        "by_income_quintile": sections["by_income_quintile"],
        "by_region": sections["by_region"],
        "by_municipality_type": sections["by_municipality_type"],
        "by_household_structure": sections["by_household_structure"],
        "median_income_by_age": by_person,
        "household_income_by_age_of_reference_person": by_hh,
        "saving_rate": saving,
        "housing_cost_burden": burden,
        "reference_budgets": refb,
    }
    (OUT_DIR / "statfin.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", OUT_DIR / "statfin.json")

    paavo = fetch_paavo()
    (OUT_DIR / "paavo_income.json").write_text(dump_one_row_per_line(paavo), encoding="utf-8")
    print("wrote", OUT_DIR / "paavo_income.json", "areas:", paavo["meta"]["n_areas"])
    print("self checks:", cons_meta["self_checks"], "| reference budgets:", refb["arithmetic_check"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
