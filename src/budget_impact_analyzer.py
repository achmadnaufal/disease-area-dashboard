"""
budget_impact_analyzer.py — Health Economic Budget Impact Model (BIM) for payer submissions.

Implements a population-based budget impact model aligned with ISPOR Task Force
recommendations (Sullivan et al. 2014). Models the financial impact on a payer's
budget when a new drug replaces existing treatments over a 1–5 year time horizon.

Supports:
  - Market uptake curve modelling (linear, logistic, custom)
  - Gross vs net price (after rebates and discounts)
  - Epidemiology-based eligible population sizing
  - Drug-specific treatment cost (annual cost per patient)
  - Offset savings from reduced hospitalisation and adverse event management
  - Scenario analysis: base case, optimistic, pessimistic

References:
    - Sullivan et al. (2014) ISPOR Good Practice Guidelines for BIM. Value in Health 17(1):5-14
    - NICE (2022) NICE Health Technology Evaluations: Methods Guide §6
    - WHO-CHOICE (2020) Cost-effectiveness thresholds and budget impact methodology
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DrugProfile:
    """Profile for a single drug in the budget impact model.

    Attributes:
        drug_name: Brand or generic name.
        annual_cost_per_patient_usd: Gross annual treatment cost (USD per patient).
        rebate_pct: Expected payer rebate as % of gross list price (0–60).
        administration_cost_usd: Annual per-patient administration/monitoring cost (USD).
        adherence_rate: Expected treatment adherence (0–1). Costs scaled by adherence.
        response_rate: Proportion of patients achieving clinical response (0–1).
        annual_hospitalisation_cost_avoided_usd: Average hospitalisation cost saved per
            responding patient per year (USD) — offset from better disease control.
        ae_management_cost_usd: Annual adverse event management cost per patient (USD).
        is_new_drug: True if this is the new drug entering the market.

    Raises:
        ValueError: If costs or rates are out of valid range.
    """

    drug_name: str
    annual_cost_per_patient_usd: float
    rebate_pct: float = 0.0
    administration_cost_usd: float = 0.0
    adherence_rate: float = 1.0
    response_rate: float = 0.5
    annual_hospitalisation_cost_avoided_usd: float = 0.0
    ae_management_cost_usd: float = 0.0
    is_new_drug: bool = False

    def __post_init__(self) -> None:
        if not self.drug_name.strip():
            raise ValueError("drug_name must not be empty.")
        if self.annual_cost_per_patient_usd < 0:
            raise ValueError("annual_cost_per_patient_usd must be non-negative.")
        if not (0.0 <= self.rebate_pct <= 60.0):
            raise ValueError("rebate_pct must be between 0 and 60%.")
        if self.administration_cost_usd < 0:
            raise ValueError("administration_cost_usd must be non-negative.")
        if not (0.0 <= self.adherence_rate <= 1.0):
            raise ValueError("adherence_rate must be between 0 and 1.")
        if not (0.0 <= self.response_rate <= 1.0):
            raise ValueError("response_rate must be between 0 and 1.")
        if self.annual_hospitalisation_cost_avoided_usd < 0:
            raise ValueError("annual_hospitalisation_cost_avoided_usd must be non-negative.")
        if self.ae_management_cost_usd < 0:
            raise ValueError("ae_management_cost_usd must be non-negative.")

    @property
    def net_annual_cost_per_patient_usd(self) -> float:
        """Net annual treatment cost after rebate (USD)."""
        return self.annual_cost_per_patient_usd * (1.0 - self.rebate_pct / 100.0)

    @property
    def total_annual_cost_per_patient_usd(self) -> float:
        """Total per-patient annual cost including administration and AE management,
        adjusted for adherence."""
        drug_cost = self.net_annual_cost_per_patient_usd * self.adherence_rate
        admin_cost = self.administration_cost_usd
        ae_cost = self.ae_management_cost_usd
        return drug_cost + admin_cost + ae_cost

    @property
    def net_cost_after_offsets_usd(self) -> float:
        """Net cost after subtracting hospitalisation savings for responders."""
        gross = self.total_annual_cost_per_patient_usd
        offset = self.annual_hospitalisation_cost_avoided_usd * self.response_rate
        return gross - offset


@dataclass
class EligiblePopulation:
    """Eligible patient population for the budget impact model.

    Attributes:
        total_population: Total population in the payer's geographic coverage.
        disease_prevalence_pct: Prevalence of the target disease (% of total population).
        diagnosed_rate: Proportion of prevalent cases that are diagnosed (0–1).
        treated_rate: Proportion of diagnosed patients receiving drug treatment (0–1).
        eligible_for_new_drug_rate: Proportion of treated patients eligible for the new
            drug (e.g., after prior therapy lines, specific biomarker) (0–1).
        annual_growth_rate_pct: Annual growth of the eligible patient pool (%, for
            modelling population drift over forecast horizon). Default 0.

    Raises:
        ValueError: If any value is outside valid range.
    """

    total_population: int
    disease_prevalence_pct: float
    diagnosed_rate: float
    treated_rate: float
    eligible_for_new_drug_rate: float = 1.0
    annual_growth_rate_pct: float = 0.0

    def __post_init__(self) -> None:
        if self.total_population <= 0:
            raise ValueError("total_population must be positive.")
        if not (0.0 < self.disease_prevalence_pct <= 100.0):
            raise ValueError("disease_prevalence_pct must be in (0, 100].")
        if not (0.0 < self.diagnosed_rate <= 1.0):
            raise ValueError("diagnosed_rate must be in (0, 1].")
        if not (0.0 < self.treated_rate <= 1.0):
            raise ValueError("treated_rate must be in (0, 1].")
        if not (0.0 < self.eligible_for_new_drug_rate <= 1.0):
            raise ValueError("eligible_for_new_drug_rate must be in (0, 1].")
        if not (-10.0 <= self.annual_growth_rate_pct <= 20.0):
            raise ValueError("annual_growth_rate_pct must be between -10 and 20%.")

    def eligible_patients(self, year: int = 0) -> float:
        """Compute eligible patient count for a given year offset.

        Args:
            year: Year index (0 = base year, 1 = year 1, etc.).

        Returns:
            Number of eligible patients (float, can be fractional for modelling).
        """
        base = (
            self.total_population
            * (self.disease_prevalence_pct / 100.0)
            * self.diagnosed_rate
            * self.treated_rate
            * self.eligible_for_new_drug_rate
        )
        growth_factor = (1.0 + self.annual_growth_rate_pct / 100.0) ** year
        return base * growth_factor


@dataclass
class MarketShare:
    """Market share trajectory for a drug over the forecast horizon.

    Attributes:
        drug_name: Must match a DrugProfile.drug_name.
        year_shares: Dict mapping year (1, 2, 3 ...) to market share (0–1).
            Values must sum to ≤ 1.0 across drugs at each year.

    Raises:
        ValueError: If any share is outside [0, 1].
    """

    drug_name: str
    year_shares: Dict[int, float]

    def __post_init__(self) -> None:
        for yr, share in self.year_shares.items():
            if not (0.0 <= share <= 1.0):
                raise ValueError(
                    f"Market share for {self.drug_name} year {yr} = {share} is outside [0, 1]."
                )

    def share_at(self, year: int) -> float:
        """Return market share at a given year. Returns 0 if year not found."""
        return self.year_shares.get(year, 0.0)


@dataclass
class BudgetImpactResult:
    """Annual budget impact result for one year.

    Attributes:
        year: Forecast year (1-indexed).
        eligible_patients: Total eligible patient count.
        scenario_name: Scenario label (e.g., 'base_case', 'optimistic').
        without_new_drug_cost_usd: Total payer cost without the new drug.
        with_new_drug_cost_usd: Total payer cost with the new drug.
        incremental_cost_usd: Difference (positive = more expensive with new drug).
        incremental_cost_per_patient_usd: Per-eligible-patient incremental cost.
        new_drug_patients: Number of patients on the new drug.
    """

    year: int
    eligible_patients: float
    scenario_name: str
    without_new_drug_cost_usd: float
    with_new_drug_cost_usd: float
    incremental_cost_usd: float
    incremental_cost_per_patient_usd: float
    new_drug_patients: float

    @property
    def is_cost_saving(self) -> bool:
        """True if the new drug reduces total payer costs."""
        return self.incremental_cost_usd < 0


# ---------------------------------------------------------------------------
# Core model
# ---------------------------------------------------------------------------


class BudgetImpactAnalyzer:
    """Payer-perspective budget impact model for new drug market entry.

    Models the financial impact on a payer budget when a new drug displaces
    existing treatments over a 1–5 year forecast horizon.

    Args:
        model_name: Name of the disease area / BIM.
        disease_area: Disease area label (e.g., 'NSCLC', 'Type 2 Diabetes').
        forecast_years: Number of years to forecast (1–5).
        currency: Currency label (default 'USD').

    Raises:
        ValueError: If forecast_years is outside [1, 5].

    Example:
        >>> analyzer = BudgetImpactAnalyzer(
        ...     model_name="Oncology BIM 2026",
        ...     disease_area="NSCLC",
        ...     forecast_years=3,
        ... )
        >>> results = analyzer.run(drugs, population, shares)
    """

    def __init__(
        self,
        model_name: str,
        disease_area: str,
        forecast_years: int = 3,
        currency: str = "USD",
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must not be empty.")
        if not (1 <= forecast_years <= 5):
            raise ValueError("forecast_years must be between 1 and 5.")
        self.model_name = model_name
        self.disease_area = disease_area
        self.forecast_years = forecast_years
        self.currency = currency

    def run(
        self,
        drug_profiles: List[DrugProfile],
        population: EligiblePopulation,
        market_shares: List[MarketShare],
        scenario_name: str = "base_case",
    ) -> List[BudgetImpactResult]:
        """Run the budget impact model.

        Args:
            drug_profiles: List of DrugProfile instances (must include exactly
                one with is_new_drug=True).
            population: EligiblePopulation instance.
            market_shares: List of MarketShare instances, one per drug.
            scenario_name: Label for this scenario run.

        Returns:
            List of BudgetImpactResult, one per forecast year.

        Raises:
            ValueError: If no new drug is found, or share dicts are inconsistent.
        """
        self._validate_inputs(drug_profiles, market_shares)

        drug_map: Dict[str, DrugProfile] = {d.drug_name: d for d in drug_profiles}
        share_map: Dict[str, MarketShare] = {s.drug_name: s for s in market_shares}
        new_drug_name = next(d.drug_name for d in drug_profiles if d.is_new_drug)

        results: List[BudgetImpactResult] = []

        for yr in range(1, self.forecast_years + 1):
            eligible = population.eligible_patients(year=yr)

            # WITHOUT new drug scenario: distribute patients across existing drugs
            # (assume new drug share goes to the comparator pro-rata)
            cost_without = self._compute_total_cost(
                yr, eligible, drug_map, share_map, new_drug_name, include_new_drug=False
            )

            # WITH new drug scenario
            cost_with = self._compute_total_cost(
                yr, eligible, drug_map, share_map, new_drug_name, include_new_drug=True
            )

            incremental = cost_with - cost_without
            new_drug_patients = eligible * share_map[new_drug_name].share_at(yr)
            per_patient = (
                incremental / eligible if eligible > 0 else 0.0
            )

            results.append(BudgetImpactResult(
                year=yr,
                eligible_patients=round(eligible, 1),
                scenario_name=scenario_name,
                without_new_drug_cost_usd=round(cost_without, 2),
                with_new_drug_cost_usd=round(cost_with, 2),
                incremental_cost_usd=round(incremental, 2),
                incremental_cost_per_patient_usd=round(per_patient, 2),
                new_drug_patients=round(new_drug_patients, 1),
            ))

        return results

    def _compute_total_cost(
        self,
        year: int,
        eligible: float,
        drug_map: Dict[str, DrugProfile],
        share_map: Dict[str, MarketShare],
        new_drug_name: str,
        include_new_drug: bool,
    ) -> float:
        """Compute total payer cost for a given year.

        In the WITHOUT scenario, the new drug's share is redistributed to
        comparators proportionally.
        """
        total = 0.0
        new_drug_share = share_map[new_drug_name].share_at(year)

        if include_new_drug:
            for drug_name, profile in drug_map.items():
                share = share_map[drug_name].share_at(year)
                patients = eligible * share
                total += patients * profile.net_cost_after_offsets_usd
        else:
            # Redistribute new drug share proportionally to comparators
            comparators = {k: v for k, v in drug_map.items() if k != new_drug_name}
            comparator_share_total = sum(
                share_map[k].share_at(year) for k in comparators
            )
            for drug_name, profile in comparators.items():
                base_share = share_map[drug_name].share_at(year)
                if comparator_share_total > 0:
                    redistributed = base_share + (
                        new_drug_share * base_share / comparator_share_total
                    )
                else:
                    redistributed = base_share
                patients = eligible * redistributed
                total += patients * profile.net_cost_after_offsets_usd

        return total

    def _validate_inputs(
        self,
        drug_profiles: List[DrugProfile],
        market_shares: List[MarketShare],
    ) -> None:
        """Validate inputs before running the model."""
        if not drug_profiles:
            raise ValueError("drug_profiles must not be empty.")
        new_drugs = [d for d in drug_profiles if d.is_new_drug]
        if len(new_drugs) != 1:
            raise ValueError(
                f"Exactly one drug must have is_new_drug=True; found {len(new_drugs)}."
            )
        drug_names = {d.drug_name for d in drug_profiles}
        share_names = {s.drug_name for s in market_shares}
        missing_shares = drug_names - share_names
        if missing_shares:
            raise ValueError(
                f"Market shares missing for drugs: {missing_shares}. "
                "Provide a MarketShare for every DrugProfile."
            )

    def cumulative_impact(self, results: List[BudgetImpactResult]) -> Dict:
        """Compute cumulative budget impact over the full forecast horizon.

        Args:
            results: Output from run().

        Returns:
            Dict with total_incremental_cost, total_new_drug_patients,
            is_cost_saving, avg_annual_incremental_cost.
        """
        if not results:
            return {}
        total_inc = sum(r.incremental_cost_usd for r in results)
        total_patients = sum(r.new_drug_patients for r in results)
        return {
            "scenario": results[0].scenario_name,
            "forecast_years": len(results),
            "total_incremental_cost_usd": round(total_inc, 2),
            "total_new_drug_patients_treated": round(total_patients, 1),
            "is_cost_saving": total_inc < 0,
            "avg_annual_incremental_cost_usd": round(total_inc / len(results), 2),
            "cost_per_patient_treated_usd": round(
                total_inc / total_patients if total_patients > 0 else 0.0, 2
            ),
        }

    def sensitivity_analysis(
        self,
        drug_profiles: List[DrugProfile],
        population: EligiblePopulation,
        market_shares: List[MarketShare],
        price_variations_pct: Optional[List[float]] = None,
    ) -> List[Dict]:
        """One-way sensitivity on new drug price (±% of list price).

        Args:
            drug_profiles: Base drug profiles.
            population: Eligible population.
            market_shares: Market share trajectories.
            price_variations_pct: List of price variation percentages (e.g. [-20, -10, 0, 10, 20]).

        Returns:
            List of dicts: price_variation_pct, cumulative_incremental_cost_usd.
        """
        if price_variations_pct is None:
            price_variations_pct = [-20.0, -10.0, 0.0, 10.0, 20.0]

        results = []
        new_drug_orig = next(d for d in drug_profiles if d.is_new_drug)

        for var_pct in price_variations_pct:
            # Create modified profiles with adjusted new drug price
            import copy
            mod_profiles = []
            for dp in drug_profiles:
                dp_copy = copy.copy(dp)
                if dp.is_new_drug:
                    dp_copy.annual_cost_per_patient_usd = dp.annual_cost_per_patient_usd * (
                        1.0 + var_pct / 100.0
                    )
                mod_profiles.append(dp_copy)

            scenario_results = self.run(
                mod_profiles, population, market_shares,
                scenario_name=f"price_var_{var_pct:+.0f}pct"
            )
            cum = self.cumulative_impact(scenario_results)
            results.append({
                "price_variation_pct": var_pct,
                "cumulative_incremental_cost_usd": cum.get("total_incremental_cost_usd", 0.0),
            })

        return results
