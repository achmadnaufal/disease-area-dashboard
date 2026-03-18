"""
Patient journey funnel analysis for pharmaceutical disease area intelligence.

Models the patient treatment pathway from diagnosis through therapy initiation,
maintenance, switch, and discontinuation. Used for:
  - Identifying conversion bottlenecks (e.g., diagnosed but untreated patients)
  - Quantifying therapy switch patterns and brand loyalty
  - Calculating patient lifetime value by therapy line
  - Supporting commercial teams with targeting prioritisation

References:
    - IQVIA Institute (2022) Global Medicine Spending and Usage Trends
    - Veeva CRM Patient Journey Analytics framework
    - ISPOR Good Practices for Outcomes Research — patient flow models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

JOURNEY_STAGES = [
    "diagnosed",
    "treatment_eligible",
    "treatment_initiated",
    "on_brand",          # on the tracked brand
    "maintained_6m",     # still on brand at 6 months
    "maintained_12m",    # still on brand at 12 months
]

# Typical industry conversion benchmarks (illustrative; varies by disease area)
BENCHMARK_CONVERSION_RATES: Dict[str, float] = {
    "diagnosed_to_eligible":       0.72,  # 72% of diagnosed are eligible for treatment
    "eligible_to_initiated":       0.68,  # 68% of eligible actually start therapy
    "initiated_to_on_brand":       0.35,  # 35% start on the tracked brand
    "initiated_to_maintained_6m":  0.71,  # 71% persistence at 6m (all brands)
    "initiated_to_maintained_12m": 0.52,  # 52% persistence at 12m
}


@dataclass
class FunnelStage:
    """
    A single stage in the patient journey funnel.

    Attributes:
        name (str): Stage identifier
        patient_count (int): Estimated number of patients at this stage
        conversion_rate_to_next (float): Fraction converting to the next stage (0–1)
        drop_reason (str): Primary reason for drop-off at this stage
    """

    name: str
    patient_count: int
    conversion_rate_to_next: float = 1.0
    drop_reason: str = ""

    def __post_init__(self):
        if self.patient_count < 0:
            raise ValueError(f"patient_count cannot be negative at stage '{self.name}'")
        if not 0.0 <= self.conversion_rate_to_next <= 1.0:
            raise ValueError(
                f"conversion_rate_to_next must be 0–1, got {self.conversion_rate_to_next}"
            )

    @property
    def drop_count(self) -> int:
        """Number of patients dropping off at this stage."""
        return round(self.patient_count * (1 - self.conversion_rate_to_next))

    @property
    def pass_through_count(self) -> int:
        """Number of patients proceeding to the next stage."""
        return self.patient_count - self.drop_count


@dataclass
class PatientJourneyFunnel:
    """
    Full patient journey funnel for a disease area and brand.

    Built by PatientJourneyAnalyzer.build_funnel() or manually constructed.

    Attributes:
        disease_area (str): Therapy area name (e.g., 'Type 2 Diabetes')
        brand_name (str): Target brand (e.g., 'BrandX')
        stages (List[FunnelStage]): Ordered list of funnel stages
        market_size_patients (int): Total diagnosed patients in the market
    """

    disease_area: str
    brand_name: str
    stages: List[FunnelStage]
    market_size_patients: int

    def overall_conversion_rate(self) -> float:
        """
        End-to-end funnel conversion rate (first to last stage).

        Returns:
            Fraction of patients in the first stage who reach the last stage
        """
        if not self.stages or self.stages[0].patient_count == 0:
            return 0.0
        return self.stages[-1].patient_count / self.stages[0].patient_count

    def biggest_drop_stage(self) -> Optional[FunnelStage]:
        """
        Stage with the largest absolute patient drop-off.

        Returns:
            FunnelStage with maximum drop count, or None if empty
        """
        if not self.stages:
            return None
        return max(self.stages[:-1], key=lambda s: s.drop_count, default=None)

    def funnel_summary(self) -> List[Dict]:
        """
        Generate a stage-by-stage summary for reporting.

        Returns:
            List of dicts with:
                - stage (str): Stage name
                - patients (int): Patient count
                - conversion_to_next_pct (float): % converting to next stage
                - drop_count (int): Patients lost at this stage
                - cumulative_conversion_pct (float): % of initial cohort remaining
        """
        if not self.stages:
            return []
        first_count = self.stages[0].patient_count
        summary = []
        for stage in self.stages:
            cum_conv = (stage.patient_count / first_count * 100) if first_count > 0 else 0
            summary.append(
                {
                    "stage": stage.name,
                    "patients": stage.patient_count,
                    "conversion_to_next_pct": round(stage.conversion_rate_to_next * 100, 1),
                    "drop_count": stage.drop_count,
                    "cumulative_conversion_pct": round(cum_conv, 1),
                    "drop_reason": stage.drop_reason,
                }
            )
        return summary


class PatientJourneyAnalyzer:
    """
    Analyse and compare patient journey funnels across brands and time periods.

    Args:
        disease_area (str): Therapy area label (e.g., 'Cardiovascular - HFrEF')
        total_diagnosed_patients (int): Estimated total diagnosed patients in market

    Example:
        >>> analyzer = PatientJourneyAnalyzer(
        ...     disease_area="Type 2 Diabetes",
        ...     total_diagnosed_patients=500_000,
        ... )
        >>> funnel = analyzer.build_funnel(
        ...     brand_name="BrandX",
        ...     brand_initiation_share=0.28,
        ...     persistence_6m=0.74,
        ...     persistence_12m=0.55,
        ... )
        >>> print(analyzer.opportunity_score(funnel))
    """

    def __init__(self, disease_area: str, total_diagnosed_patients: int):
        if not disease_area.strip():
            raise ValueError("disease_area cannot be empty")
        if total_diagnosed_patients <= 0:
            raise ValueError("total_diagnosed_patients must be positive")

        self.disease_area = disease_area
        self.total_diagnosed_patients = total_diagnosed_patients

    def build_funnel(
        self,
        brand_name: str,
        treatment_eligible_rate: float = BENCHMARK_CONVERSION_RATES["diagnosed_to_eligible"],
        treatment_initiation_rate: float = BENCHMARK_CONVERSION_RATES["eligible_to_initiated"],
        brand_initiation_share: float = BENCHMARK_CONVERSION_RATES["initiated_to_on_brand"],
        persistence_6m: float = BENCHMARK_CONVERSION_RATES["initiated_to_maintained_6m"],
        persistence_12m: float = BENCHMARK_CONVERSION_RATES["initiated_to_maintained_12m"],
    ) -> PatientJourneyFunnel:
        """
        Build a patient journey funnel for a specific brand.

        Args:
            brand_name: Name of the tracked pharmaceutical brand
            treatment_eligible_rate: Fraction of diagnosed patients eligible for treatment
            treatment_initiation_rate: Fraction of eligible patients who start treatment
            brand_initiation_share: Fraction of initiating patients who start on this brand
            persistence_6m: Fraction of brand patients still on therapy at 6 months
            persistence_12m: Fraction of brand patients still on therapy at 12 months

        Returns:
            PatientJourneyFunnel with all stages populated

        Raises:
            ValueError: If any rate is outside [0, 1] or brand_name is empty
        """
        if not brand_name.strip():
            raise ValueError("brand_name cannot be empty")
        for param_name, value in [
            ("treatment_eligible_rate", treatment_eligible_rate),
            ("treatment_initiation_rate", treatment_initiation_rate),
            ("brand_initiation_share", brand_initiation_share),
            ("persistence_6m", persistence_6m),
            ("persistence_12m", persistence_12m),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{param_name} must be between 0 and 1, got {value}")

        diagnosed = self.total_diagnosed_patients
        eligible = round(diagnosed * treatment_eligible_rate)
        initiated = round(eligible * treatment_initiation_rate)
        on_brand = round(initiated * brand_initiation_share)
        maintained_6m = round(on_brand * persistence_6m)
        maintained_12m = round(on_brand * persistence_12m)

        stages = [
            FunnelStage(
                name="diagnosed",
                patient_count=diagnosed,
                conversion_rate_to_next=treatment_eligible_rate,
                drop_reason="Not eligible (comorbidities, contraindications)",
            ),
            FunnelStage(
                name="treatment_eligible",
                patient_count=eligible,
                conversion_rate_to_next=treatment_initiation_rate,
                drop_reason="Watchful waiting / patient refusal / no access",
            ),
            FunnelStage(
                name="treatment_initiated",
                patient_count=initiated,
                conversion_rate_to_next=brand_initiation_share,
                drop_reason="Initiated on competitor brand",
            ),
            FunnelStage(
                name="on_brand",
                patient_count=on_brand,
                conversion_rate_to_next=persistence_6m,
                drop_reason="Switched / discontinued within 6 months",
            ),
            FunnelStage(
                name="maintained_6m",
                patient_count=maintained_6m,
                conversion_rate_to_next=(
                    maintained_12m / maintained_6m if maintained_6m > 0 else 0.0
                ),
                drop_reason="Switch or discontinuation between 6–12 months",
            ),
            FunnelStage(
                name="maintained_12m",
                patient_count=maintained_12m,
                conversion_rate_to_next=1.0,  # end of tracked journey
                drop_reason="",
            ),
        ]

        return PatientJourneyFunnel(
            disease_area=self.disease_area,
            brand_name=brand_name,
            stages=stages,
            market_size_patients=diagnosed,
        )

    def opportunity_score(self, funnel: PatientJourneyFunnel) -> Dict:
        """
        Quantify commercial opportunity gaps in the patient funnel.

        Calculates the additional patients that could be reached if each
        conversion rate improved to benchmark level. Useful for targeting
        commercial investment (e.g., which stage is most impactful to improve).

        Args:
            funnel: PatientJourneyFunnel to analyse

        Returns:
            Dict with:
                - biggest_gap_stage (str): Stage with largest absolute opportunity
                - untreated_patients (int): Eligible but untreated patients
                - competitor_share_patients (int): Initiating on competitor
                - persistence_gap_6m (int): Patients lost before 6 months
                - persistence_gap_12m (int): Patients lost between 6–12 months
                - total_opportunity_patients (int): Sum of all gaps
                - brand_penetration_pct (float): % of diagnosed currently on brand

        Example:
            >>> score = analyzer.opportunity_score(funnel)
            >>> print(f"Untreated opportunity: {score['untreated_patients']:,} patients")
        """
        if len(funnel.stages) < 6:
            raise ValueError("Funnel must have at least 6 stages for opportunity analysis")

        eligible = funnel.stages[1].patient_count
        initiated = funnel.stages[2].patient_count
        on_brand = funnel.stages[3].patient_count
        maintained_6m = funnel.stages[4].patient_count
        maintained_12m = funnel.stages[5].patient_count

        untreated = eligible - initiated
        competitor = initiated - on_brand
        pers_gap_6m = on_brand - maintained_6m
        pers_gap_12m = maintained_6m - maintained_12m
        total_opp = untreated + competitor + pers_gap_6m + pers_gap_12m

        gaps = {
            "untreated_patients": untreated,
            "competitor_share_patients": competitor,
            "persistence_gap_6m": pers_gap_6m,
            "persistence_gap_12m": pers_gap_12m,
        }
        biggest_gap = max(gaps, key=lambda k: gaps[k])

        brand_penetration = (
            on_brand / funnel.market_size_patients * 100
            if funnel.market_size_patients > 0 else 0.0
        )

        return {
            "biggest_gap_stage": biggest_gap,
            "untreated_patients": untreated,
            "competitor_share_patients": competitor,
            "persistence_gap_6m": pers_gap_6m,
            "persistence_gap_12m": pers_gap_12m,
            "total_opportunity_patients": total_opp,
            "brand_penetration_pct": round(brand_penetration, 2),
        }

    def compare_brands(
        self, funnels: List[PatientJourneyFunnel]
    ) -> List[Dict]:
        """
        Compare patient journey metrics across multiple brands.

        Args:
            funnels: List of PatientJourneyFunnel objects (one per brand)

        Returns:
            List of dicts sorted by 12-month maintained patients (desc):
                - brand (str)
                - on_brand_patients (int)
                - maintained_12m (int)
                - overall_conversion_pct (float)
                - persistence_12m_pct (float)

        Raises:
            ValueError: If funnels list is empty
        """
        if not funnels:
            raise ValueError("funnels list cannot be empty")

        results = []
        for f in funnels:
            on_brand = f.stages[3].patient_count if len(f.stages) > 3 else 0
            maintained_12m = f.stages[5].patient_count if len(f.stages) > 5 else 0
            pers_12m = (maintained_12m / on_brand * 100) if on_brand > 0 else 0.0
            results.append(
                {
                    "brand": f.brand_name,
                    "on_brand_patients": on_brand,
                    "maintained_12m": maintained_12m,
                    "overall_conversion_pct": round(f.overall_conversion_rate() * 100, 2),
                    "persistence_12m_pct": round(pers_12m, 1),
                }
            )
        return sorted(results, key=lambda x: x["maintained_12m"], reverse=True)
