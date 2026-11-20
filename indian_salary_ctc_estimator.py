"""\
INDIAN SALARY / CTC ESTIMATOR (annual estimate; not an ITR filing utility)

FLOW
  CTC components entered by employee
        |
        +--> Cash salary: Basic + DA + HRA + allowances + bonus
        |       |
        |       +--> Taxable salary/perquisites - eligible exemptions
        |       |       - standard deduction - allowed deductions
        |       |       --> estimated income tax + cess
        |       |
        |       +--> Cash salary - income tax - employee PF/NPS - PT
        |               - other payroll deductions --> BANK IN-HAND
        |
        +--> Employee and employer PF/NPS --> EMPLOYEE RETIREMENT WEALTH
        +--> Gratuity / insurance / reimbursements / other employer costs
                --> EMPLOYER / CONDITIONAL / EXPENSE COSTS
        +--> Income tax + professional tax --> GOVERNMENT

  Reconciliation: bank + retirement wealth + government + employer costs
                  + other payroll deductions + unallocated CTC = CTC

Tax rules below are editable assumptions. Verify rates, limits and exemptions
for the relevant tax year and the taxpayer's facts before relying on the result.
Special-rate income (for example, capital gains), surcharge and its marginal relief,
foreign income, loss set-offs and ITR eligibility are outside this estimate.
"""

from dataclasses import dataclass, replace


# Defaults carried forward from the prior calculator's 2025 regime assumptions.
# Verify against the Finance Act and rules applicable to Tax Year 2026-27.
TAX_YEAR = "2026-27 (verify rates and limits)"
NEW_SLABS = [
    (400_000, 0.00),
    (800_000, 0.05),
    (1_200_000, 0.10),
    (1_600_000, 0.15),
    (2_000_000, 0.20),
    (2_400_000, 0.25),
    (float("inf"), 0.30),
]
OLD_STANDARD_DEDUCTION = 50_000
NEW_STANDARD_DEDUCTION = 75_000
CESS_RATE = 0.04


@dataclass
class SalaryInput:
    ctc: float
    basic: float
    da: float = 0.0
    da_counts_for_retirement: bool = False
    commission: float = 0.0
    hra_qualifying_commission: float = 0.0
    hra: float = 0.0
    other_taxable_allowances: float = 0.0
    bonus: float = 0.0
    taxable_perquisites: float = 0.0
    employer_nps: float = 0.0
    employer_nps_deduction: float = 0.0
    other_old_regime_exemptions: float = 0.0
    other_new_regime_exemptions: float = 0.0
    rent_paid: float = 0.0
    is_metro_for_hra: bool = False
    employee_pf: float = 0.0
    employee_nps: float = 0.0
    employer_pf: float = 0.0
    gratuity_ctc: float = 0.0
    insurance_ctc: float = 0.0
    reimbursements_ctc: float = 0.0
    other_employer_costs: float = 0.0
    professional_tax: float = 0.0
    other_payroll_deductions: float = 0.0
    other_80c: float = 0.0
    other_old_regime_deductions: float = 0.0
    resident_individual: bool = True
    age_group: str = "under60"


def slab_tax(income: float, slabs: list[tuple[float, float]]) -> float:
    tax = 0.0
    lower = 0.0
    for upper, rate in slabs:
        if income <= lower:
            break
        tax += (min(income, upper) - lower) * rate
        lower = upper
    return tax


def old_regime_slabs(age_group: str) -> list[tuple[float, float]]:
    first_limit = {"under60": 250_000, "60to79": 300_000, "80plus": 500_000}[age_group]
    return [
        (first_limit, 0.00),
        (500_000, 0.05),
        (1_000_000, 0.20),
        (float("inf"), 0.30),
    ]


def tax_for_regime(
    taxable_income: float, regime: str, resident: bool, age_group: str
) -> tuple[float, str]:
    if regime == "NEW":
        tax = slab_tax(taxable_income, NEW_SLABS)
        if resident and taxable_income <= 1_200_000:
            return 0.0, "New regime rebate (resident; income within configured limit)"
        if resident and taxable_income > 1_200_000:
            excess = taxable_income - 1_200_000
            if tax > excess:
                return excess, "New regime marginal relief applied"
            return tax, "New regime slabs"
        return tax, "New regime slabs (rebate not available to non-residents)"

    tax = slab_tax(taxable_income, old_regime_slabs(age_group))
    if resident and taxable_income <= 500_000:
        return max(0.0, tax - min(tax, 12_500)), "Old regime rebate (resident; income within limit)"
    return tax, "Old regime age-based slabs"


def hra_exemption(data: SalaryInput, regime: str) -> float:
    if regime != "OLD" or data.rent_paid <= 0 or data.hra <= 0:
        return 0.0
    qualifying_salary = (
        data.basic
        + (data.da if data.da_counts_for_retirement else 0.0)
        + data.hra_qualifying_commission
    )
    city_limit = (0.50 if data.is_metro_for_hra else 0.40) * qualifying_salary
    rent_less_ten_percent = max(0.0, data.rent_paid - 0.10 * qualifying_salary)
    return min(data.hra, city_limit, rent_less_ten_percent)


def analyze(data: SalaryInput, regime: str) -> dict:
    regime = regime.upper()
    if regime not in {"OLD", "NEW"}:
        raise ValueError("regime must be 'OLD' or 'NEW'")
    if data.age_group not in {"under60", "60to79", "80plus"}:
        raise ValueError("age_group must be under60, 60to79, or 80plus")

    cash_salary = (
        data.basic
        + data.da
        + data.commission
        + data.hra
        + data.other_taxable_allowances
        + data.bonus
    )
    salary_before_exemptions = cash_salary + data.employer_nps + data.taxable_perquisites
    hra_exempt = hra_exemption(data, regime)
    other_exemptions = (
        data.other_old_regime_exemptions
        if regime == "OLD"
        else data.other_new_regime_exemptions
    )
    salary_after_exemptions = max(
        0.0, salary_before_exemptions - hra_exempt - other_exemptions
    )
    standard_deduction = (
        OLD_STANDARD_DEDUCTION if regime == "OLD" else NEW_STANDARD_DEDUCTION
    )
    professional_tax_deduction = data.professional_tax if regime == "OLD" else 0.0
    if regime == "OLD":
        eligible_80c = min(150_000, data.employee_pf + data.other_80c)
        other_deductions = max(0.0, data.other_old_regime_deductions)
    else:
        eligible_80c = 0.0
        other_deductions = 0.0

    eligible_employer_nps = max(0.0, min(data.employer_nps, data.employer_nps_deduction))
    taxable_salary = max(
        0.0,
        salary_after_exemptions
        - standard_deduction
        - professional_tax_deduction
        - eligible_80c
        - other_deductions
        - eligible_employer_nps,
    )
    base_tax, tax_note = tax_for_regime(
        taxable_salary, regime, data.resident_individual, data.age_group
    )
    income_tax = round((base_tax * (1.0 + CESS_RATE)) / 10) * 10

    government = income_tax + data.professional_tax
    employee_wealth = (
        data.employee_pf + data.employee_nps + data.employer_pf + data.employer_nps
    )
    employer_costs = (
        data.gratuity_ctc
        + data.insurance_ctc
        + data.reimbursements_ctc
        + data.other_employer_costs
    )
    bank_in_hand = (
        cash_salary
        - income_tax
        - data.professional_tax
        - data.employee_pf
        - data.employee_nps
        - data.other_payroll_deductions
    )
    allocated_ctc = (
        cash_salary
        + data.employer_pf
        + data.employer_nps
        + employer_costs
    )
    unallocated_ctc = max(0.0, data.ctc - allocated_ctc)
    overallocated_ctc = max(0.0, allocated_ctc - data.ctc)
    ctc_flow_total = (
        bank_in_hand
        + employee_wealth
        + government
        + employer_costs
        + data.other_payroll_deductions
        + unallocated_ctc
    )

    return {
        "regime": regime,
        "cash_salary": cash_salary,
        "salary_before_exemptions": salary_before_exemptions,
        "hra_exemption": hra_exempt,
        "other_salary_exemptions": other_exemptions,
        "standard_deduction": standard_deduction,
        "professional_tax_deduction": professional_tax_deduction,
        "eligible_80c": eligible_80c,
        "other_old_regime_deductions": other_deductions,
        "employer_nps_deduction": eligible_employer_nps,
        "taxable_salary": round(taxable_salary),
        "tax_note": tax_note,
        "income_tax": income_tax,
        "bank_in_hand": round(bank_in_hand),
        "monthly_in_hand": round(bank_in_hand / 12),
        "employee_wealth": round(employee_wealth),
        "government": round(government),
        "employer_costs": round(employer_costs),
        "other_payroll_deductions": round(data.other_payroll_deductions),
        "unallocated_ctc": round(unallocated_ctc),
        "allocated_ctc": round(allocated_ctc),
        "overallocated_ctc": round(overallocated_ctc),
        "ctc_flow_total": round(ctc_flow_total),
    }


def ask_money(label: str) -> float:
    while True:
        raw = input(f"{label} [annual ₹, default 0]: ").strip().replace(",", "")
        if not raw:
            return 0.0
        try:
            amount = float(raw)
            if amount >= 0:
                return amount
        except ValueError:
            pass
        print("Enter a non-negative amount, for example 125000.")


def ask_yes_no(label: str, default: bool = False) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{label} [{default_text}]: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Enter yes or no.")


def get_salary_input() -> SalaryInput:
    print(f"\nINDIAN SALARY / CTC ESTIMATE - Tax Year {TAX_YEAR}")
    print("Enter actual annual amounts from your salary structure or Form 16 / payroll.")
    ctc = ask_money("Total annual CTC")
    basic = ask_money("Basic salary")
    da = ask_money("Dearness allowance (DA)")
    da_retirement = ask_yes_no("Is DA included for retirement-benefit salary calculations?")
    hra = ask_money("House rent allowance (HRA)")
    other_allowances = ask_money("Other cash allowances (taxable unless exempted below)")
    bonus = ask_money("Expected annual bonus / incentive (taxable salary)")
    commission = ask_money("Annual commission (taxable salary)")
    hra_commission = ask_money(
        "HRA-qualifying part of commission (fixed % of turnover; subset of commission above)"
    )
    taxable_perks = ask_money(
        "Other taxable non-cash perquisites per payroll/Form 16, excluding employer NPS"
    )

    print("\nEmployer-side CTC items (these are not monthly bank salary):")
    employee_pf = ask_money("Employee PF contribution")
    employee_nps = ask_money("Employee NPS contribution through payroll")
    employer_pf = ask_money("Employer PF contribution")
    employer_nps = ask_money("Employer NPS contribution")
    employer_nps_deduction = ask_money(
        "Eligible employer NPS deduction confirmed by payroll (cannot exceed contribution)"
    )
    gratuity = ask_money("Gratuity provision included in CTC")
    insurance = ask_money("Employer insurance / benefits cost included in CTC")
    reimbursements = ask_money(
        "Verified official-duty reimbursements included in CTC (per payroll treatment)"
    )
    other_employer_costs = ask_money("Other employer-side CTC costs")

    print("\nTax details (enter only amounts you are eligible to claim):")
    rent = ask_money("Annual rent paid (for old-regime HRA calculation)")
    metro = ask_yes_no("Was the rented home in Delhi, Mumbai, Kolkata or Chennai?")
    old_exemptions = ask_money(
        "Eligible old-regime salary exemptions confirmed by payroll/Form 16, excluding HRA"
    )
    new_exemptions = ask_money(
        "Eligible new-regime salary exemptions confirmed by payroll/Form 16 (excluding HRA)"
    )
    other_80c = ask_money("Other eligible 80C amount, excluding employee PF")
    other_old_deductions = ask_money(
        "Other eligible old-regime deductions after limits, excluding 80C and employer NPS"
    )
    professional_tax = ask_money("Annual professional tax actually deducted")
    other_payroll_deductions = ask_money("Other employee payroll deductions")
    resident = ask_yes_no("Are you a resident individual for income-tax purposes?", True)
    while True:
        age_group = input("Age for old-regime slabs [under60/60to79/80plus]: ").strip().lower()
        if not age_group:
            age_group = "under60"
        if age_group in {"under60", "60to79", "80plus"}:
            break
        print("Enter under60, 60to79, or 80plus.")

    return SalaryInput(
        ctc=ctc,
        basic=basic,
        da=da,
        da_counts_for_retirement=da_retirement,
        commission=commission,
        hra_qualifying_commission=hra_commission,
        hra=hra,
        other_taxable_allowances=other_allowances,
        bonus=bonus,
        taxable_perquisites=taxable_perks,
        employer_nps=employer_nps,
        employer_nps_deduction=employer_nps_deduction,
        other_old_regime_exemptions=old_exemptions,
        other_new_regime_exemptions=new_exemptions,
        rent_paid=rent,
        is_metro_for_hra=metro,
        employee_pf=employee_pf,
        employee_nps=employee_nps,
        employer_pf=employer_pf,
        gratuity_ctc=gratuity,
        insurance_ctc=insurance,
        reimbursements_ctc=reimbursements,
        other_employer_costs=other_employer_costs,
        professional_tax=professional_tax,
        other_payroll_deductions=other_payroll_deductions,
        other_80c=other_80c,
        other_old_regime_deductions=other_old_deductions,
        resident_individual=resident,
        age_group=age_group,
    )


def print_result(result: dict, ctc: float) -> None:
    def share(amount: float) -> str:
        return f" ({amount / ctc:.1%} of CTC)" if ctc > 0 else ""

    print(f"\n--- {result['regime']} REGIME ---")
    print(f"Cash salary before deductions:          ₹{result['cash_salary']:,.0f}/yr")
    print(f"Taxable salary after deductions:        ₹{result['taxable_salary']:,.0f}/yr")
    print(f"Estimated income tax incl. 4% cess:     ₹{result['income_tax']:,.0f}/yr")
    print(f"Tax rule applied: {result['tax_note']}")
    print(
        f"BANK IN-HAND:                            ₹{result['bank_in_hand']:,.0f}/yr"
        f"{share(result['bank_in_hand'])}"
    )
    print(f"Monthly average in-hand:                 ₹{result['monthly_in_hand']:,.0f}/mo")
    print(
        f"Employee retirement wealth (PF/NPS):    ₹{result['employee_wealth']:,.0f}/yr"
        f"{share(result['employee_wealth'])}"
    )
    print(
        f"Government (income + professional tax):  ₹{result['government']:,.0f}/yr"
        f"{share(result['government'])}"
    )
    print(
        f"Employer / expense / conditional costs:  ₹{result['employer_costs']:,.0f}/yr"
        f"{share(result['employer_costs'])}"
    )
    print(f"Other employee payroll deductions:      ₹{result['other_payroll_deductions']:,.0f}/yr")
    print(f"Unallocated CTC:                         ₹{result['unallocated_ctc']:,.0f}/yr")
    if result["overallocated_ctc"]:
        print(f"WARNING: Entered components exceed CTC by ₹{result['overallocated_ctc']:,.0f}.")
    else:
        print(f"CTC flow check:                          ₹{result['ctc_flow_total']:,.0f} of ₹{ctc:,.0f}")


def scale_compensation(data: SalaryInput, factor: float) -> SalaryInput:
    ctc_fields = (
        "ctc",
        "basic",
        "da",
        "commission",
        "hra_qualifying_commission",
        "hra",
        "other_taxable_allowances",
        "bonus",
        "taxable_perquisites",
        "employer_nps",
        "employer_nps_deduction",
        "employee_pf",
        "employee_nps",
        "employer_pf",
        "gratuity_ctc",
        "insurance_ctc",
        "reimbursements_ctc",
        "other_employer_costs",
    )
    return replace(data, **{name: getattr(data, name) * factor for name in ctc_fields})


def run_increment_sweep(data: SalaryInput) -> None:
    print("\nINCREMENT SWEEP: same CTC structure scaled by each increase")
    print("Rent, PT, personal deductions and other exemption claims remain unchanged.")
    print("Actual employer increments may use a different structure or PF cap.")

    for regime in ("NEW", "OLD"):
        baseline = analyze(data, regime)
        print(f"\n--- {regime} REGIME ---")
        print("Income and take-home")
        print(f"{'Hike':>5} | {'CTC/yr':>12} | {'Taxable':>12} | {'Tax/yr':>10} | {'In-hand/mo':>12} | {'Gain/mo':>10}")
        print("-" * 76)
        for hike in (0, 5, 10, 15, 20, 25):
            scenario = scale_compensation(data, 1 + hike / 100)
            result = analyze(scenario, regime)
            gain = result["monthly_in_hand"] - baseline["monthly_in_hand"]
            print(
                f"{hike:>4}% | ₹{scenario.ctc:>10,.0f} | ₹{result['taxable_salary']:>10,.0f} | "
                f"₹{result['income_tax']:>8,.0f} | ₹{result['monthly_in_hand']:>10,.0f} | "
                f"₹{gain:>+8,.0f}"
            )

        print("CTC destinations")
        print(f"{'Hike':>5} | {'Retirement':>12} | {'Government':>12} | {'Employer costs':>14} | {'Unallocated':>12}")
        print("-" * 66)
        for hike in (0, 5, 10, 15, 20, 25):
            scenario = scale_compensation(data, 1 + hike / 100)
            result = analyze(scenario, regime)
            print(
                f"{hike:>4}% | ₹{result['employee_wealth']:>10,.0f} | "
                f"₹{result['government']:>10,.0f} | ₹{result['employer_costs']:>12,.0f} | "
                f"₹{result['unallocated_ctc']:>10,.0f}"
            )


def main() -> None:
    print("Tax estimates are approximate. Verify the configured limits for your tax year.")
    data = get_salary_input()
    print_result(analyze(data, "NEW"), data.ctc)
    print_result(analyze(data, "OLD"), data.ctc)
    if ask_yes_no("Run the 0%-25% CTC increment sweep?", True):
        run_increment_sweep(data)
    print("\nMonthly average spreads annual bonus across 12 months; actual payslips vary.")
    print("Capital gains and other special-rate income are not calculated.")


if __name__ == "__main__":
    main()