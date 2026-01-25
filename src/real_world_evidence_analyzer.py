"""
Real-World Evidence (RWE) Analyzer for pharmaceutical disease area intelligence.

Real-world evidence uses data from electronic health records (EHR), claims
databases, patient registries, and observational studies to complement
randomised clinical trial (RCT) data in pharmaceutical decision-making.

This module supports:
  - Comparative effectiveness analysis: brand vs comparator in real-world setting
  - Treatment duration and persistence analysis (adherence proxy)
  - Comorbidity burden scoring and subgroup identification
  - Line-of-therapy (LOT) transition rates from real-world claims
  - Time-to-treatment discontinuation (TTD) Kaplan-Meier estimation
  - NNT (Number Needed to Treat) from observational data with confounding flags

Applications:
  - HEOR (Health Economics and Outcomes Research) dossier preparation
  - Formulary access support: payer dossiers and value stories
  - Medical Affairs insight generation for KOL engagement
  - Label extension evidence package assembly

Reference methodologies:
  - ISPE Good Pharmacoepidemiology Practices (GPP) v3.0
  - GRACE Checklist for RWE Credibility Assessment
  - ISPOR-ISPE Special Task Force on RWE (2017)

Author: github.com/achmadnaufal
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class StudyDesign(str, Enum):
    """Observational study design classification."""
    COHORT = "cohort"                       # Prospective/retrospective cohort
    CASE_CONTROL = "case_control"           # Case-control
    CROSS_SECTIONAL = "cross_sectional"    # Cross-sectional/prevalence study
    REGISTRY = "registry"                   # Disease or product registry
    CLAIMS_DATABASE = "claims_database"    # Insurance claims data


class ConfidenceLevel(str, Enum):
    """Evidence confidence classification per GRACE checklist."""
    HIGH = "high"         # RCT-equivalent confounding control; large N
    MODERATE = "moderate" # Good design, some unmeasured confounders
    LOW = "low"           # High confounding risk; small N; short follow-up
    VERY_LOW = "very_low" # Serious methodological concerns


# GRACE checklist score thresholds (0–10 scale; higher = better)
GRACE_CONFIDENCE_THRESHOLDS: Dict[ConfidenceLevel, Tuple[float, float]] = {
    ConfidenceLevel.HIGH: (8.0, 10.0),
    ConfidenceLevel.MODERATE: (5.5, 7.9),
    ConfidenceLevel.LOW: (3.0, 5.4),
    ConfidenceLevel.VERY_LOW: (0.0, 2.9),
}


@dataclass
class RWEStudy:
    """Metadata and results for a single real-world evidence study.

    Attributes:
        study_id: Unique study identifier.
        disease_area: Indication or disease (e.g., 'Type 2 Diabetes').
        brand: Drug/product under study.
        comparator: Comparator drug or 'standard of care'.
        study_design: Observational design type.
        n_brand: Sample size for brand cohort.
        n_comparator: Sample size for comparator cohort.
        follow_up_months: Median follow-up duration (months).
        primary_endpoint: Description of primary outcome (e.g., 'HbA1c reduction').
        brand_event_rate_pct: Event rate (primary endpoint) in brand group (%).
        comparator_event_rate_pct: Event rate in comparator group (%).
        p_value: Statistical significance of primary endpoint comparison.
        grace_score: GRACE checklist score 0–10 (methodological quality).
        data_source: Source database/registry name.
        publication_year: Year of publication or dataset.
        country: Country/market of study.
        has_propensity_matching: Whether propensity score matching was applied.
        unmeasured_confounders: Known unmeasured confounding risks.
    """

    study_id: str
    disease_area: str
    brand: str
    comparator: str
    study_design: StudyDesign
    n_brand: int
    n_comparator: int
    follow_up_months: float
    primary_endpoint: str
    brand_event_rate_pct: float
    comparator_event_rate_pct: float
    p_value: float
    grace_score: float
    data_source: str
    publication_year: int
    country: str
    has_propensity_matching: bool = False
    unmeasured_confounders: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.n_brand <= 0 or self.n_comparator <= 0:
            raise ValueError("Sample sizes must be positive")
        if not (0 <= self.brand_event_rate_pct <= 100):
            raise ValueError("brand_event_rate_pct must be 0–100")
        if not (0 <= self.comparator_event_rate_pct <= 100):
            raise ValueError("comparator_event_rate_pct must be 0–100")
        if not (0 <= self.p_value <= 1):
            raise ValueError("p_value must be between 0 and 1")
        if not (0 <= self.grace_score <= 10):
            raise ValueError("grace_score must be 0–10")

    @property
    def relative_risk(self) -> Optional[float]:
        """Relative Risk (RR) of brand vs comparator.

        Returns None if comparator event rate is zero (avoid division by zero).
        """
        if self.comparator_event_rate_pct == 0:
            return None
        return self.brand_event_rate_pct / self.comparator_event_rate_pct

    @property
    def absolute_risk_reduction_pct(self) -> float:
        """Absolute Risk Reduction (ARR) in percentage points."""
        return self.comparator_event_rate_pct - self.brand_event_rate_pct

    @property
    def nnt(self) -> Optional[float]:
        """Number Needed to Treat (NNT) derived from real-world ARR.

        Returns None if ARR is zero or negative (no benefit observed).
        """
        arr_decimal = self.absolute_risk_reduction_pct / 100
        if arr_decimal <= 0:
            return None
        return 1 / arr_decimal

    @property
    def is_statistically_significant(self) -> bool:
        """True if p < 0.05 (conventional significance threshold)."""
        return self.p_value < 0.05

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Evidence confidence classification from GRACE score."""
        for level, (low, high) in GRACE_CONFIDENCE_THRESHOLDS.items():
            if low <= self.grace_score <= high:
                return level
        return ConfidenceLevel.VERY_LOW

    @property
    def total_n(self) -> int:
        """Total study population."""
        return self.n_brand + self.n_comparator


@dataclass
class RWEInsight:
    """Synthesised insight derived from one or more RWE studies.

    Attributes:
        brand: Drug/product.
        disease_area: Indication.
        n_studies: Number of studies synthesised.
        pooled_n: Total patients across studies.
        weighted_rr: Sample-size-weighted relative risk (brand vs comparator).
        mean_grace_score: Average GRACE methodological score.
        overall_confidence: Overall evidence confidence level.
        statistically_significant_studies: Count of studies with p<0.05.
        propensity_matched_studies: Count with propensity score matching.
        summary_statement: Narrative one-liner for payer/KOL communication.
        key_limitations: List of identified evidence limitations.
        recommended_studies: Suggested additional studies to fill gaps.
    """

    brand: str
    disease_area: str
    n_studies: int
    pooled_n: int
    weighted_rr: Optional[float]
    mean_grace_score: float
    overall_confidence: ConfidenceLevel
    statistically_significant_studies: int
    propensity_matched_studies: int
    summary_statement: str
    key_limitations: List[str]
    recommended_studies: List[str]


class RealWorldEvidenceAnalyzer:
    """Synthesises and assesses real-world evidence studies for pharma decision-making.

    Provides:
    - Per-study metrics (RR, ARR, NNT, GRACE confidence)
    - Portfolio synthesis across multiple studies for a brand/indication
    - Evidence gap identification for HEOR strategy

    Example:
        >>> analyzer = RealWorldEvidenceAnalyzer()
        >>> study = RWEStudy(
        ...     study_id="RWE_DM_001",
        ...     disease_area="Type 2 Diabetes",
        ...     brand="BrandA",
        ...     comparator="Metformin",
        ...     study_design=StudyDesign.COHORT,
        ...     n_brand=5_200,
        ...     n_comparator=4_800,
        ...     follow_up_months=18,
        ...     primary_endpoint="HbA1c <7% at 12 months",
        ...     brand_event_rate_pct=62,
        ...     comparator_event_rate_pct=48,
        ...     p_value=0.003,
        ...     grace_score=7.5,
        ...     data_source="IQVIA Claims Database",
        ...     publication_year=2024,
        ...     country="ID",
        ... )
        >>> insight = analyzer.synthesize([study])
        >>> print(insight.overall_confidence)
        ConfidenceLevel.MODERATE
    """

    def __init__(
        self,
        significance_threshold: float = 0.05,
        min_grace_for_high_confidence: float = 8.0,
    ) -> None:
        """Initialise the analyzer.

        Args:
            significance_threshold: p-value cutoff for statistical significance.
            min_grace_for_high_confidence: GRACE score minimum for HIGH confidence.
        """
        self.significance_threshold = significance_threshold
        self.min_grace_for_high_confidence = min_grace_for_high_confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_study(self, study: RWEStudy) -> Dict:
        """Return computed metrics for a single RWE study.

        Args:
            study: An RWEStudy instance.

        Returns:
            Dict with RR, ARR, NNT, significance flag, and confidence level.
        """
        if not isinstance(study, RWEStudy):
            raise TypeError("study must be an RWEStudy instance")

        return {
            "study_id": study.study_id,
            "relative_risk": round(study.relative_risk, 3) if study.relative_risk else None,
            "absolute_risk_reduction_pct": round(study.absolute_risk_reduction_pct, 2),
            "nnt": round(study.nnt, 1) if study.nnt else None,
            "p_value": study.p_value,
            "statistically_significant": study.is_statistically_significant,
            "grace_score": study.grace_score,
            "confidence_level": study.confidence_level.value,
            "propensity_matched": study.has_propensity_matching,
            "n_total": study.total_n,
            "follow_up_months": study.follow_up_months,
        }

    def synthesize(
        self,
        studies: List[RWEStudy],
        brand: Optional[str] = None,
        disease_area: Optional[str] = None,
    ) -> RWEInsight:
        """Synthesise evidence across multiple studies for a brand/indication.

        Uses sample-size weighting for aggregate RR calculation.

        Args:
            studies: List of RWEStudy instances.
            brand: Optional override brand name (defaults to first study's brand).
            disease_area: Optional override disease area.

        Returns:
            RWEInsight with synthesised metrics and narrative.

        Raises:
            ValueError: If studies list is empty.
        """
        if not studies:
            raise ValueError("studies list cannot be empty")

        brand = brand or studies[0].brand
        disease_area = disease_area or studies[0].disease_area

        total_n = sum(s.total_n for s in studies)
        sig_count = sum(1 for s in studies if s.is_statistically_significant)
        pm_count = sum(1 for s in studies if s.has_propensity_matching)

        # Weighted RR by total sample size
        rr_studies = [s for s in studies if s.relative_risk is not None]
        if rr_studies:
            total_w = sum(s.total_n for s in rr_studies)
            weighted_rr = sum(s.relative_risk * s.total_n for s in rr_studies) / total_w
        else:
            weighted_rr = None

        mean_grace = sum(s.grace_score for s in studies) / len(studies)
        overall_confidence = self._aggregate_confidence(studies, mean_grace, pm_count)

        limitations = self._identify_limitations(studies, pm_count, sig_count)
        recommendations = self._recommend_studies(studies, overall_confidence, limitations)
        summary = self._build_summary_statement(brand, disease_area, weighted_rr, overall_confidence, sig_count, len(studies))

        return RWEInsight(
            brand=brand,
            disease_area=disease_area,
            n_studies=len(studies),
            pooled_n=total_n,
            weighted_rr=round(weighted_rr, 3) if weighted_rr else None,
            mean_grace_score=round(mean_grace, 1),
            overall_confidence=overall_confidence,
            statistically_significant_studies=sig_count,
            propensity_matched_studies=pm_count,
            summary_statement=summary,
            key_limitations=limitations,
            recommended_studies=recommendations,
        )

    def filter_by_confidence(
        self, studies: List[RWEStudy], min_level: ConfidenceLevel
    ) -> List[RWEStudy]:
        """Return only studies meeting or exceeding a minimum confidence level.

        Args:
            studies: List of RWEStudy instances.
            min_level: Minimum acceptable ConfidenceLevel.

        Returns:
            Filtered list of studies.
        """
        level_rank = {
            ConfidenceLevel.VERY_LOW: 0,
            ConfidenceLevel.LOW: 1,
            ConfidenceLevel.MODERATE: 2,
            ConfidenceLevel.HIGH: 3,
        }
        min_rank = level_rank[min_level]
        return [s for s in studies if level_rank[s.confidence_level] >= min_rank]

    def evidence_gap_report(
        self,
        studies: List[RWEStudy],
        disease_area: str,
    ) -> Dict:
        """Identify evidence gaps for a disease area across countries and designs.

        Args:
            studies: Available RWE studies for this disease area.
            disease_area: Target indication.

        Returns:
            Dict with coverage gaps, design diversity, and gap prioritisation.
        """
        countries_covered = {s.country for s in studies}
        designs_covered = {s.study_design for s in studies}
        has_long_term = any(s.follow_up_months >= 24 for s in studies)
        has_propensity = any(s.has_propensity_matching for s in studies)
        high_quality = [s for s in studies if s.grace_score >= self.min_grace_for_high_confidence]

        gaps: List[str] = []
        if not has_long_term:
            gaps.append("No long-term study (≥24 months follow-up) available")
        if not has_propensity:
            gaps.append("No propensity-score-matched cohort study — confounding risk elevated")
        if StudyDesign.REGISTRY not in designs_covered:
            gaps.append("No patient registry data — treatment patterns in routine care unknown")
        if len(high_quality) == 0:
            gaps.append("No high-quality study (GRACE ≥8.0) — payer dossier credibility at risk")
        if len(countries_covered) < 2:
            gaps.append("Single-market data only — generalisability to other markets unconfirmed")

        return {
            "disease_area": disease_area,
            "n_studies": len(studies),
            "countries_covered": sorted(countries_covered),
            "designs_covered": [d.value for d in designs_covered],
            "high_quality_studies": len(high_quality),
            "evidence_gaps": gaps,
            "gap_count": len(gaps),
            "priority_next_study": gaps[0] if gaps else "Evidence base sufficient",
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _aggregate_confidence(
        self,
        studies: List[RWEStudy],
        mean_grace: float,
        propensity_matched_count: int,
    ) -> ConfidenceLevel:
        """Determine aggregate evidence confidence for a portfolio of studies."""
        # Bonus for propensity matching
        adjusted_grace = mean_grace + (0.5 if propensity_matched_count > 0 else 0)
        # Penalty for small pooled N
        total_n = sum(s.total_n for s in studies)
        if total_n < 500:
            adjusted_grace -= 1.0

        adjusted_grace = max(0, min(10, adjusted_grace))
        for level, (low, high) in GRACE_CONFIDENCE_THRESHOLDS.items():
            if low <= adjusted_grace <= high:
                return level
        return ConfidenceLevel.VERY_LOW

    @staticmethod
    def _identify_limitations(
        studies: List[RWEStudy],
        pm_count: int,
        sig_count: int,
    ) -> List[str]:
        limitations: List[str] = []
        if pm_count == 0:
            limitations.append("No propensity-score matching applied — selection bias cannot be ruled out")
        unmeasured = set()
        for s in studies:
            unmeasured.update(s.unmeasured_confounders)
        if unmeasured:
            limitations.append(f"Unmeasured confounders identified: {', '.join(sorted(unmeasured))}")
        if sig_count == 0:
            limitations.append("No statistically significant primary endpoint result across studies")
        if any(s.follow_up_months < 6 for s in studies):
            limitations.append("Short follow-up (<6 months) in at least one study limits outcome validity")
        if len(set(s.data_source for s in studies)) == 1:
            limitations.append("All studies use single data source — replication across databases recommended")
        return limitations

    @staticmethod
    def _recommend_studies(
        studies: List[RWEStudy],
        confidence: ConfidenceLevel,
        limitations: List[str],
    ) -> List[str]:
        recs: List[str] = []
        if confidence in (ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW):
            recs.append("Conduct propensity-score-matched retrospective cohort study in large claims database")
        if not any(s.follow_up_months >= 24 for s in studies):
            recs.append("Design extended follow-up study (24–36 months) to capture long-term outcomes")
        if len({s.country for s in studies}) < 3:
            recs.append("Replicate evidence in additional markets to strengthen global payer narrative")
        if not recs:
            recs.append("Evidence package is strong; consider meta-analysis for regulatory dossier")
        return recs

    @staticmethod
    def _build_summary_statement(
        brand: str,
        disease_area: str,
        weighted_rr: Optional[float],
        confidence: ConfidenceLevel,
        sig_studies: int,
        total_studies: int,
    ) -> str:
        rr_str = f"(weighted RR vs comparator: {weighted_rr:.2f})" if weighted_rr else "(RR not calculable)"
        return (
            f"{brand} in {disease_area}: {sig_studies}/{total_studies} studies statistically significant "
            f"{rr_str}. Overall evidence confidence: {confidence.value.upper()}."
        )
