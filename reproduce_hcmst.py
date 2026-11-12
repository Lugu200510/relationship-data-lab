"""Summarize the public HCMST 2017–2022 Stata file without exporting respondent rows."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import warnings

import pandas as pd


EXPECTED_SHA256 = "a76c1ef8e14a69951db3d71142dfb3866063c7af8d0da67942b744e2727aeb56"
BASELINE_EARLIEST = (2017 - 1960) * 12 + 6  # July 2017
BASELINE_LATEST = BASELINE_EARLIEST + 1  # Fieldwork ended on August 1.
HORIZONS = (12, 24, 36)
WEIGHT = "w1_weight_combo"
COLUMNS = [
    "w1_either_internet_adjusted", "w1_how_met_online", WEIGHT,
    "w1_partnership_status", "w1_max_relation_status",
    "w1_q21b_year", "w1_q21b_month", "w1_q21b_month_flag", "w1_q21d_year", "w1_q21d_month",
    "w2_section", "w2_partner_type", "w2_month_of_survey",
    "w3_section", "w3_partner_source", "w3_breakup_source",
    "w3_partner_type", "w3_month_interview", "w3_when_married_yr", "w3_when_married_month",
]


def integer(value):
    return int(value) if pd.notna(value) else None


def month_range(year, month, last_month):
    if year is None or not 1900 <= year <= 2022:
        return None
    january = (year - 1960) * 12
    if month is not None and 1 <= month <= 12:
        earliest = latest = january + month - 1
    else:
        earliest, latest = january, january + 11
    return (earliest, min(latest, last_month)) if earliest <= last_month else None


def marriage_outcome(start, marriage, horizon):
    if start is None or marriage is None or marriage[1] < start[0]:
        return "dateUnknown"
    if marriage[1] - start[0] <= horizon:
        return "yes"
    if marriage[0] - start[1] > horizon:
        return "no"
    return "dateUnknown"


def classify(row, horizon):
    year = integer(row.w1_q21b_year)
    month = None if row.w1_q21b_month_flag == 1 else integer(row.w1_q21b_month)
    start = month_range(year, month, BASELINE_LATEST)
    status = row.w1_partnership_status
    if status == 1 or row.w1_max_relation_status == 2:
        wedding = month_range(integer(row.w1_q21d_year), integer(row.w1_q21d_month), BASELINE_LATEST)
        return marriage_outcome(start, wedding, horizon), "baseline"
    if status == 3:
        return "no", "baseline"
    if start is not None and BASELINE_EARLIEST >= start[1] + horizon:
        return "no", "baseline"

    # Section C continues the same formerly unmarried relationship. Section D
    # reports its end. Q21D in 2020 belongs to a new partner, not the baseline one.
    if row.w2_section == 3 and row.w2_partner_type == 1:
        last = integer(row.w2_month_of_survey)
        wedding = (BASELINE_EARLIEST, last) if last is not None else None
        return marriage_outcome(start, wedding, horizon), "wave2"
    if row.w2_section == 4:
        return "no", "wave2"
    if row.w2_section == 3 and row.w2_partner_type == 2:
        last = integer(row.w2_month_of_survey)
        if start is not None and last is not None and last >= start[1] + horizon:
            return "no", "wave2"

    if row.w3_section == 4 and row.w3_breakup_source == 1:
        return "no", "wave3"
    if row.w3_section == 3 and row.w3_partner_source == 1:
        last = integer(row.w3_month_interview)
        if row.w3_partner_type == 1:
            wedding = month_range(integer(row.w3_when_married_yr), integer(row.w3_when_married_month), last)
            return marriage_outcome(start, wedding, horizon), "wave3"
        if row.w3_partner_type == 2 and start is not None and last is not None and last >= start[1] + horizon:
            return "no", "wave3"

    return ("dateUnknown" if start is None else "followupUnknown"), "unresolved"


def summarize(relationships, horizon):
    cases = [(classify(row, horizon), getattr(row, WEIGHT)) for row in relationships.itertuples(index=False)]
    counts = Counter(outcome for (outcome, _), _ in cases)
    origins = Counter(source for (outcome, source), _ in cases if outcome in {"yes", "no"})
    weights = {key: sum(weight for (outcome, _), weight in cases if outcome == key) for key in counts}
    yes, no = counts["yes"], counts["no"]
    weighted_yes, weighted_no = weights.get("yes", 0), weights.get("no", 0)
    return {
        "months": horizon,
        "yes": yes,
        "no": no,
        "dateUnknown": counts["dateUnknown"],
        "followupUnknown": counts["followupUnknown"],
        "baseline": origins["baseline"],
        "wave2": origins["wave2"],
        "wave3": origins["wave3"],
        "weightedRate": weighted_yes / (weighted_yes + weighted_no),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="Original Stanford HCMST Stata v2.2 file")
    parser.add_argument("--output", type=Path, default=Path("dist/hcmst-summary.js"))
    args = parser.parse_args()
    fingerprint = sha256(args.data.read_bytes()).hexdigest()
    if fingerprint != EXPECTED_SHA256:
        parser.error("The file does not match Stanford's public HCMST Stata v2.2 release used for this analysis.")

    # Stata's original label encoding varies. Only numeric variables are read.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnicodeWarning)
        data = pd.read_stata(args.data, columns=COLUMNS, convert_categoricals=False, convert_dates=False)
    online = data.loc[data.w1_either_internet_adjusted.eq(1)]
    relationships = online.loc[online.w1_how_met_online.eq(3)]
    assert len(data) == 3510 and len(online) == 475 and len(relationships) == 385
    assert relationships.w1_partnership_status.isin([1, 2, 3]).all()
    assert relationships[WEIGHT].gt(0).all()
    assert relationships.w2_month_of_survey.dropna().between(728, 729).all()
    assert relationships.w3_month_interview.dropna().between(746, 748).all()
    results = [summarize(relationships, horizon) for horizon in HORIZONS]
    for result in results:
        assert sum(result[key] for key in ("yes", "no", "dateUnknown", "followupUnknown")) == len(relationships)
        assert result["baseline"] + result["wave2"] + result["wave3"] == result["yes"] + result["no"]

    summary = {"version": "2.2", "surveySize": len(data), "onlineFlag": len(online),
               "sampleSize": len(relationships), "sha256": fingerprint, "results": results}
    args.output.write_text("// Generated by reproduce_hcmst.py. Aggregate counts only.\n"
                           "const HCMST = " + json.dumps(summary, indent=2, ensure_ascii=False) + ";\n",
                           encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

