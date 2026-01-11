"""
Market Penetration Estimator for pharmaceutical disease area analytics.

Estimates the gap between diagnosed patient population and treated patient
population across disease areas. Quantifies market opportunity through:
  - Diagnosis rate (% of incident cases that get diagnosed)
  - Treatment rate (% of diagnosed patients who receive any treatment)
  - Brand penetration (% of treated patients on a specific brand)
  - Untapped patient opportunity at each funnel stage

This module supports disease area strategy, go-to-market planning, and
KPI target-setting for pharma commercial teams.

Reference: Adapted from IQVIA Disease Burden Framework and IMS Health
Market Opportunity Model, applied to specialty disease areas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DiseaseAreaData:
    """
    Population and treatment data for a disease area in a market.

    Parameters
    ----------
    disease_id : str
        Unique disease or indication identifier (e.g., "RA", "T2DM").
    disease_name : str
        Full disease name.
    country : str
        Market/country for this estimate.
    total_population : int
        Total adult population in the market.
    incidence_rate_per_100k : float
        Annual new cases per 100,000 population.
    prevalence_rate_per_100k : float
        Total existing cases per 100,000 population (use prevalence for chronic diseases).
    diagnosis_rate_pct : float
        Estimated % of prevalent/incident cases that have been diagnosed (0–100).
    treatment_rate_pct : float
        Estimated % of diagnosed patients currently on any treatment (0–100).
    brand_market_share_pct : float
        Current brand market share among treated patients (0–100).
    brand_name : str, optional
        Brand name for penetration analysis.
    competitor_share_pct : float, optional
        Aggregate competitor market share (used to cross-check brand + competitor ≤ 100).
    """
    disease_id: str
    disease_name: str
    country: str
    total_population: int
    incidence_rate_per_100k: float
    prevalence_rate_per_100k: float
    diagnosis_rate_pct: float
    treatment_rate_pct: float
    brand_market_share_pct: float
    brand_name: str = "Brand"
    competitor_share_pct: Optional[float] = None

    def __post_init__(self):
        if self.total_population <= 0:
            raise ValueError(f"total_population must be positive ({self.disease_id})")
        for attr in ["incidence_rate_per_100k", "prevalence_rate_per_100k"]:
            if getattr(self, attr) < 0:
                raise ValueError(f"{attr} must be non-negative ({self.disease_id})")
        for attr in ["diagnosis_rate_pct", "treatment_rate_pct", "brand_market_share_pct"]:
            val = getattr(self, attr)
            if not 0 <= val <= 100:
                raise ValueError(f"{attr} must be 0–100% ({self.disease_id}), got {val}")
        if self.competitor_share_pct is not None:
            if not 0 <= self.competitor_share_pct <= 100:
                raise ValueError(f"competitor_share_pct must be 0–100% ({self.disease_id})")
            if self.brand_market_share_pct + self.competitor_share_pct > 100:
                raise ValueError(
                    f"brand + competitor share exceeds 100% ({self.disease_id}): "
                    f"{self.brand_market_share_pct} + {self.competitor_share_pct}"
                )


@dataclass
class PenetrationEstimate:
    """Market penetration estimates and opportunity sizing for a disease area."""
    disease_id: str
    disease_name: str
    country: str
    brand_name: str

    # Patient funnel (absolute patient counts)
    prevalent_patients: int
    diagnosed_patients: int
    treated_patients: int
    brand_patients: int

    # Penetration rates (%)
    diagnosis_rate_pct: float
    treatment_rate_pct: float
    brand_penetration_of_treated_pct: float
    brand_penetration_of_diagnosed_pct: float
    brand_penetration_of_prevalent_pct: float

    # Opportunity gaps (untapped patients)
    undiagnosed_gap: int
    untreated_diagnosed_gap: int        # Diagnosed but not treated
    untreated_by_brand_gap: int         # Treated but on competitor

    # Opportunity scores (0–100, higher = more headroom)
    diagnosis_opportunity_score: float
    treatment_opportunity_score: float
    brand_opportunity_score: float

    # Strategic signals
    primary_opportunity: str            # Where the biggest gap lies
    recommendations: List[str]

    def to_dict(self) -> dict:
        return {
            "disease_id": self.disease_id,
            "disease_name": self.disease_name,
            "country": self.country,
            "brand_name": self.brand_name,
            "funnel": {
                "prevalent_patients": self.prevalent_patients,
                "diagnosed_patients": self.diagnosed_patients,
                "treated_patients": self.treated_patients,
                "brand_patients": self.brand_patients,
            },
            "penetration_rates": {
                "diagnosis_pct": round(self.diagnosis_rate_pct, 2),
                "treatment_of_diagnosed_pct": round(self.treatment_rate_pct, 2),
                "brand_of_treated_pct": round(self.brand_penetration_of_treated_pct, 2),
                "brand_of_prevalent_pct": round(self.brand_penetration_of_prevalent_pct, 2),
            },
            "gaps": {
                "undiagnosed_patients": self.undiagnosed_gap,
                "untreated_diagnosed_patients": self.untreated_diagnosed_gap,
                "on_competitor_therapy": self.untreated_by_brand_gap,
            },
            "opportunity_scores": {
                "diagnosis": round(self.diagnosis_opportunity_score, 1),
                "treatment": round(self.treatment_opportunity_score, 1),
                "brand_switch": round(self.brand_opportunity_score, 1),
            },
            "primary_opportunity": self.primary_opportunity,
            "recommendations": self.recommendations,
        }


class MarketPenetrationEstimator:
    """
    Estimate pharmaceutical market penetration and patient opportunity gaps.

    For each disease area, the estimator constructs a patient funnel:
      Prevalent patients → Diagnosed → Treated → On Brand

    Gap analysis identifies where the largest unmet opportunity lies
    and generates strategic recommendations.

    Parameters
    ----------
    use_prevalence : bool
        If True (default), use prevalence rate for funnel base (appropriate for
        chronic diseases). If False, use incidence rate (appropriate for acute).

    Examples
    --------
    >>> estimator = MarketPenetrationEstimator()
    >>> data = DiseaseAreaData(
    ...     disease_id="T2DM",
    ...     disease_name="Type 2 Diabetes",
    ...     country="Indonesia",
    ...     total_population=220_000_000,
    ...     incidence_rate_per_100k=450,
    ...     prevalence_rate_per_100k=8_500,
    ...     diagnosis_rate_pct=60.0,
    ...     treatment_rate_pct=70.0,
    ...     brand_market_share_pct=15.0,
    ...     brand_name="GlucoPrime",
    ... )
    >>> result = estimator.estimate(data)
    >>> print(f"Brand patients: {result.brand_patients:,}")
    """

    def __init__(self, use_prevalence: bool = True) -> None:
        self.use_prevalence = use_prevalence

    def _opportunity_score(self, current_pct: float, max_pct: float = 100.0) -> float:
        """Compute opportunity score as % of remaining headroom."""
        headroom = max_pct - current_pct
        return min(max(headroom, 0.0), 100.0)

    def _primary_opportunity(
        self,
        diag_opp: float,
        treat_opp: float,
        brand_opp: float,
    ) -> str:
        scores = {
            "Expand diagnosis and disease awareness": diag_opp,
            "Convert diagnosed patients to treatment": treat_opp,
            "Convert competitor-treated patients to brand": brand_opp,
        }
        return max(scores, key=scores.get)

    def _build_recommendations(
        self,
        diagnosis_rate: float,
        treatment_rate: float,
        brand_share: float,
        undiagnosed: int,
        untreated: int,
        brand_gap: int,
    ) -> List[str]:
        recs = []
        if diagnosis_rate < 50:
            recs.append(
                f"DIAGNOSIS GAP: {undiagnosed:,} undiagnosed patients. "
                "Invest in disease awareness campaigns and screening programs."
            )
        if treatment_rate < 60:
            recs.append(
                f"TREATMENT GAP: {untreated:,} diagnosed but untreated patients. "
                "Target treating physicians with HCP education on therapy initiation."
            )
        if brand_share < 20:
            recs.append(
                f"BRAND PENETRATION LOW ({brand_share:.1f}%): {brand_gap:,} patients on competitor. "
                "Focus KAM on switching discussions and HEOR differentiation."
            )
        if not recs:
            recs.append("Market is relatively well-penetrated. Focus on retention and adherence programs.")
        return recs

    def estimate(self, data: DiseaseAreaData) -> PenetrationEstimate:
        """
        Estimate market penetration and patient opportunity for a disease area.

        Parameters
        ----------
        data : DiseaseAreaData

        Returns
        -------
        PenetrationEstimate
        """
        # Funnel base (absolute patient count)
        rate_per_100k = (
            data.prevalence_rate_per_100k
            if self.use_prevalence
            else data.incidence_rate_per_100k
        )
        prevalent = int(data.total_population * rate_per_100k / 100_000)
        diagnosed = int(prevalent * data.diagnosis_rate_pct / 100)
        treated = int(diagnosed * data.treatment_rate_pct / 100)
        on_brand = int(treated * data.brand_market_share_pct / 100)

        # Gaps
        undiagnosed_gap = prevalent - diagnosed
        untreated_gap = diagnosed - treated
        brand_gap = treated - on_brand

        # Penetration rates from base population
        brand_of_treated = data.brand_market_share_pct
        brand_of_diagnosed = (on_brand / diagnosed * 100) if diagnosed > 0 else 0.0
        brand_of_prevalent = (on_brand / prevalent * 100) if prevalent > 0 else 0.0

        # Opportunity scores
        diag_opp = self._opportunity_score(data.diagnosis_rate_pct)
        treat_opp = self._opportunity_score(data.treatment_rate_pct)
        brand_opp = self._opportunity_score(data.brand_market_share_pct)

        primary = self._primary_opportunity(diag_opp, treat_opp, brand_opp)

        recs = self._build_recommendations(
            data.diagnosis_rate_pct,
            data.treatment_rate_pct,
            data.brand_market_share_pct,
            undiagnosed_gap,
            untreated_gap,
            brand_gap,
        )

        return PenetrationEstimate(
            disease_id=data.disease_id,
            disease_name=data.disease_name,
            country=data.country,
            brand_name=data.brand_name,
            prevalent_patients=prevalent,
            diagnosed_patients=diagnosed,
            treated_patients=treated,
            brand_patients=on_brand,
            diagnosis_rate_pct=data.diagnosis_rate_pct,
            treatment_rate_pct=data.treatment_rate_pct,
            brand_penetration_of_treated_pct=brand_of_treated,
            brand_penetration_of_diagnosed_pct=brand_of_diagnosed,
            brand_penetration_of_prevalent_pct=brand_of_prevalent,
            undiagnosed_gap=undiagnosed_gap,
            untreated_diagnosed_gap=untreated_gap,
            untreated_by_brand_gap=brand_gap,
            diagnosis_opportunity_score=diag_opp,
            treatment_opportunity_score=treat_opp,
            brand_opportunity_score=brand_opp,
            primary_opportunity=primary,
            recommendations=recs,
        )

    def compare_markets(self, datasets: List[DiseaseAreaData]) -> List[PenetrationEstimate]:
        """Estimate penetration across multiple markets, sorted by brand opportunity score."""
        results = [self.estimate(d) for d in datasets]
        return sorted(results, key=lambda r: r.brand_opportunity_score, reverse=True)
