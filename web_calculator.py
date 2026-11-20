"""JSON adapter used by the static Pyodide web page."""

import json

from indian_salary_ctc_estimator import SalaryInput, analyze, scale_compensation


def calculate(payload: dict) -> dict:
    data = SalaryInput(**payload)
    results = {regime: analyze(data, regime) for regime in ("NEW", "OLD")}
    sweep = {"NEW": [], "OLD": []}

    for regime in ("NEW", "OLD"):
        baseline = results[regime]
        for hike in (0, 5, 10, 15, 20, 25):
            scenario = scale_compensation(data, 1 + hike / 100)
            result = analyze(scenario, regime)
            sweep[regime].append(
                {
                    "hike": hike,
                    "ctc": scenario.ctc,
                    "income_tax": result["income_tax"],
                    "monthly_in_hand": result["monthly_in_hand"],
                    "monthly_gain": result["monthly_in_hand"] - baseline["monthly_in_hand"],
                    "employee_wealth": result["employee_wealth"],
                    "government": result["government"],
                    "employer_costs": result["employer_costs"],
                    "unallocated_ctc": result["unallocated_ctc"],
                }
            )

    return {
        "new": results["NEW"],
        "old": results["OLD"],
        "sweep": sweep,
    }


def calculate_json(payload_json: str) -> str:
    return json.dumps(calculate(json.loads(payload_json)))