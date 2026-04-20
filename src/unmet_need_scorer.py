"""
Unmet Need Composite Scoring for Disease Area Market Landscape.

Quantifies unmet medical and commercial need across disease areas (e.g.,
HER2+ breast cancer, T2DM, HFrEF, NSCLC, RA) using a transparent
composite index aligned with payer, HTA, and portfolio-prioritisation
frameworks. The composite blends five normalised sub-scores:

    1. Disease burden        — DALY rate per 100k (IHME GBD 2019)
    2. Treatment effectiveness gap — 1 - current 5-year response / survival
    3. Safety burden         — Grade 3+ AE / discontinuation rate
    4. Access restriction    — 1 - reimbursed coverage fraction
    5. Patient-reported burden — HRQoL/EQ-5D decrement (0-1)

Each sub-score is min-max normalised to 0-100 within the supplied
portfolio and combined via user-configurable weights (defaults per
IMI BEACON unmet-need framework).

Higher composite score = higher unmet need = higher strategic priority.

References:
    - IHME (2020) Global Burden of Disease Study 2019. Lancet 396:1204-22.
    - WHO (2023) Priority Medicines for Europe and the World Update.
    - EFPIA (2021) Unmet Medical Need: A Framework for Assessment.
    - Vreman R. et al. (2019) Unmet medical need: an introduction to
      definitions and stakeholder perceptions. Value Health 22(11):1275-82.
    - IMI BEACON consortium (2022) Multi-criteria decision analysis for
      unmet need prioritisation in oncology.

Author: github.com/achmadnaufal
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Mapping, Optional, Tuple


# Default weights follow the IMI BEACON unmet-need framework
# (burden 30%, effectiveness gap 25%, safety 15%, access 15%, HRQoL 15%).
DEFAULT_WEIGHTS: Dict[str, float] = {
    "burden": 0.30,
    "effectiveness_gap": 0.25,
    "safety": 0.15,
    "access": 0.15,
    "hrqol": 0.15,
}

TIER_THRESHOLDS: Tuple[Tuple[str, float], ...] = (
    ("CRITICAL", 75.0),
    ("HIGH", 55.0),
    ("MODERATE", 35.0),
    ("LOW", 0.0),
)


@dataclass(frozen=True)
class DiseaseAreaProfile:
    """
    Raw disease-area inputs for unmet-need scoring.

    All values refer to the most recent full year of evidence.

    Attributes:
        disease_area: Human-readable name (e.g., ``HER2+ Breast Cancer``).
        daly_per_100k: Age-standardised DALY rate per 100,000 (IHME GBD).
        five_year_response_rate: Fraction (0-1) of patients achieving
            durable response / 5-year survival on current standard of care.
        grade3_ae_rate: Fraction (0-1) of treated patients experiencing
            CTCAE Grade 3+ AEs on standard of care.
        reimbursed_coverage: Fraction (0-1) of eligible patients with
            reimbursed access to guideline-recommended therapy.
        hrqol_decrement: Health-related quality-of-life utility decrement
            (0-1, higher = worse; EQ-5D or similar).
        prevalence_per_100k: Optional disease prevalence per 100k for
            market sizing (not part of the composite score).
        therapy_area: Optional grouping (``Oncology``, ``Cardiometabolic``).
    """

    disease_area: str
    daly_per_100k: float
    five_year_response_rate: float
    grade3_ae_rate: float
    reimbursed_coverage: float
    hrqol_decrement: float
    prevalence_per_100k: Optional[float] = None
    therapy_area: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.disease_area or not self.disease_area.strip():
            raise ValueError("disease_area cannot be empty.")
        if self.daly_per_100k < 0:
            raise ValueError("daly_per_100k must be non-negative.")
        for name, value in (
            ("five_year_response_rate", self.five_year_response_rate),
            ("grade3_ae_rate", self.grade3_ae_rate),
            ("reimbursed_coverage", self.reimbursed_coverage),
            ("hrqol_decrement", self.hrqol_decrement),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]; got {value}.")
        if self.prevalence_per_100k is not None and self.prevalence_per_100k < 0:
            raise ValueError("prevalence_per_100k must be non-negative.")


@dataclass(frozen=True)
class UnmetNeedScore:
    """Composite unmet-need score with per-dimension breakdown."""

    disease_area: str
    burden_score: float
    effectiveness_gap_score: float
    safety_score: float
    access_score: float
    hrqol_score: float
    composite_score: float
    tier: str

    @property
    def sub_scores(self) -> Dict[str, float]:
        """Return per-dimension sub-scores as a dict."""
        return {
            "burden": self.burden_score,
            "effectiveness_gap": self.effectiveness_gap_score,
            "safety": self.safety_score,
            "access": self.access_score,
            "hrqol": self.hrqol_score,
        }


def _validate_weights(weights: Mapping[str, float]) -> Dict[str, float]:
    """Validate and normalise weights to sum to 1.0."""
    expected = set(DEFAULT_WEIGHTS)
    missing = expected - set(weights)
    if missing:
        raise ValueError(f"weights missing keys: {sorted(missing)}")
    for key, value in weights.items():
        if key not in expected:
            raise ValueError(f"Unknown weight key '{key}'. Expected: {sorted(expected)}")
        if value < 0:
            raise ValueError(f"Weight '{key}' must be non-negative; got {value}.")
    total = sum(weights.values())
    if total == 0:
        raise ValueError("Sum of weights must be > 0.")
    return {k: v / total for k, v in weights.items()}


def _min_max_normalise(values: List[float], invert: bool = False) -> List[float]:
    """
    Min-max normalise a list to 0-100.

    Args:
        values: raw numeric values.
        invert: If True, larger raw values map to smaller scores
            (used for effectiveness rate and reimbursed coverage where
            higher raw value = lower unmet need).

    Returns:
        List of scores in [0, 100]. All values equal => 50.0 for all.
    """
    if not values:
        return []
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        return [50.0 for _ in values]
    span = vmax - vmin
    if invert:
        return [round((vmax - v) / span * 100, 2) for v in values]
    return [round((v - vmin) / span * 100, 2) for v in values]


def _classify_tier(score: float) -> str:
    """Map a 0-100 composite score onto a priority tier."""
    for tier, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "LOW"


class UnmetNeedScorer:
    """
    Composite unmet-need scorer for disease-area portfolios.

    The scorer operates on a *closed portfolio* of disease areas — all
    sub-score normalisation is performed relative to the supplied cohort,
    so adding or removing a disease area will rebalance the composite
    scores. This matches how HTA and portfolio-prioritisation committees
    evaluate candidate indications against a fixed comparator set.

    Example::

        scorer = UnmetNeedScorer()
        scorer.add(DiseaseAreaProfile(
            disease_area="NSCLC",
            daly_per_100k=310.0,
            five_year_response_rate=0.22,
            grade3_ae_rate=0.38,
            reimbursed_coverage=0.55,
            hrqol_decrement=0.42,
        ))
        scorer.add(DiseaseAreaProfile(
            disease_area="T2DM",
            daly_per_100k=620.0,
            five_year_response_rate=0.68,
            grade3_ae_rate=0.08,
            reimbursed_coverage=0.92,
            hrqol_decrement=0.17,
        ))
        for score in scorer.score_portfolio():
            print(score.disease_area, score.tier, score.composite_score)
    """

    def __init__(
        self,
        weights: Optional[Mapping[str, float]] = None,
        profiles: Optional[List[DiseaseAreaProfile]] = None,
    ) -> None:
        """
        Initialise the scorer.

        Args:
            weights: Optional override for composite weights. Must contain
                keys: burden, effectiveness_gap, safety, access, hrqol.
                Re-normalised to sum to 1.
            profiles: Optional initial list of :class:`DiseaseAreaProfile`.
        """
        self.weights: Dict[str, float] = _validate_weights(
            weights if weights is not None else DEFAULT_WEIGHTS
        )
        self._profiles: Tuple[DiseaseAreaProfile, ...] = tuple(profiles or ())
        self._seen: Tuple[str, ...] = tuple(p.disease_area for p in self._profiles)
        if len(set(self._seen)) != len(self._seen):
            raise ValueError("Duplicate disease_area entries in initial profiles.")

    # ------------------------------------------------------------------
    # Data management (immutable — returns new list/state where relevant)
    # ------------------------------------------------------------------

    @property
    def profiles(self) -> Tuple[DiseaseAreaProfile, ...]:
        """Return an immutable snapshot of registered profiles."""
        return self._profiles

    def add(self, profile: DiseaseAreaProfile) -> None:
        """
        Register a disease-area profile.

        Args:
            profile: A :class:`DiseaseAreaProfile` instance.

        Raises:
            ValueError: If a profile with the same ``disease_area`` already
                exists in the portfolio.
        """
        if profile.disease_area in self._seen:
            raise ValueError(
                f"disease_area '{profile.disease_area}' already in portfolio."
            )
        self._profiles = self._profiles + (profile,)
        self._seen = self._seen + (profile.disease_area,)

    def add_bulk(self, profiles: List[DiseaseAreaProfile]) -> int:
        """
        Bulk-register profiles.

        Args:
            profiles: list of profiles to add.

        Returns:
            Number of profiles added.
        """
        for p in profiles:
            self.add(p)
        return len(profiles)

    def with_weights(self, weights: Mapping[str, float]) -> "UnmetNeedScorer":
        """
        Return a *new* scorer with different weights (no mutation).

        Args:
            weights: Weight override (same keys as DEFAULT_WEIGHTS).
        """
        return UnmetNeedScorer(weights=weights, profiles=list(self._profiles))

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_portfolio(self) -> List[UnmetNeedScore]:
        """
        Score every profile in the portfolio.

        Returns:
            List of :class:`UnmetNeedScore`, sorted by composite score
            descending (most urgent first).

        Raises:
            RuntimeError: If the portfolio is empty.
        """
        if not self._profiles:
            raise RuntimeError("Cannot score an empty portfolio.")

        burden = _min_max_normalise([p.daly_per_100k for p in self._profiles])
        eff_gap = _min_max_normalise(
            [p.five_year_response_rate for p in self._profiles], invert=True
        )
        safety = _min_max_normalise([p.grade3_ae_rate for p in self._profiles])
        access = _min_max_normalise(
            [p.reimbursed_coverage for p in self._profiles], invert=True
        )
        hrqol = _min_max_normalise([p.hrqol_decrement for p in self._profiles])

        w = self.weights
        scores: List[UnmetNeedScore] = []
        for i, profile in enumerate(self._profiles):
            composite = (
                burden[i] * w["burden"]
                + eff_gap[i] * w["effectiveness_gap"]
                + safety[i] * w["safety"]
                + access[i] * w["access"]
                + hrqol[i] * w["hrqol"]
            )
            composite = round(composite, 2)
            scores.append(
                UnmetNeedScore(
                    disease_area=profile.disease_area,
                    burden_score=burden[i],
                    effectiveness_gap_score=eff_gap[i],
                    safety_score=safety[i],
                    access_score=access[i],
                    hrqol_score=hrqol[i],
                    composite_score=composite,
                    tier=_classify_tier(composite),
                )
            )
        return sorted(scores, key=lambda s: -s.composite_score)

    def score_for(self, disease_area: str) -> UnmetNeedScore:
        """
        Return the score for a single disease area.

        Args:
            disease_area: Name of the disease area.

        Raises:
            KeyError: If the disease area is not in the portfolio.
        """
        for score in self.score_portfolio():
            if score.disease_area == disease_area:
                return score
        raise KeyError(f"disease_area '{disease_area}' not in portfolio.")

    def top_n(self, n: int = 3) -> List[UnmetNeedScore]:
        """
        Return the top-N disease areas by composite score.

        Args:
            n: number of entries to return (must be > 0).

        Raises:
            ValueError: If ``n`` is not positive.
        """
        if n <= 0:
            raise ValueError("n must be positive.")
        return self.score_portfolio()[:n]

    def tier_distribution(self) -> Dict[str, int]:
        """
        Count disease areas per priority tier.

        Returns:
            dict ``{tier: count}`` across CRITICAL, HIGH, MODERATE, LOW.
        """
        counts: Dict[str, int] = {t: 0 for t, _ in TIER_THRESHOLDS}
        for score in self.score_portfolio():
            counts[score.tier] += 1
        return counts

    def sub_score_table(self) -> List[Dict[str, float]]:
        """
        Return a flat per-disease table with all sub-scores.

        Useful for feeding a DataFrame, dashboard, or CSV export.

        Returns:
            list of dicts with disease_area, composite_score, tier,
            and each sub-score field.
        """
        rows: List[Dict[str, float]] = []
        for score in self.score_portfolio():
            row: Dict[str, float] = {
                "disease_area": score.disease_area,
                "composite_score": score.composite_score,
                "tier": score.tier,
            }
            row.update(score.sub_scores)
            rows.append(row)
        return rows

    def full_report(self) -> Dict:
        """
        Generate a comprehensive portfolio unmet-need report.

        Returns:
            dict with weights, tier distribution, top-3 rankings, and
            per-disease sub-score table.
        """
        scored = self.score_portfolio()
        top = scored[: min(3, len(scored))]
        return {
            "weights": dict(self.weights),
            "portfolio_size": len(self._profiles),
            "tier_distribution": self.tier_distribution(),
            "top_priorities": [
                {
                    "disease_area": s.disease_area,
                    "tier": s.tier,
                    "composite_score": s.composite_score,
                }
                for s in top
            ],
            "sub_scores": self.sub_score_table(),
        }

    def __len__(self) -> int:
        return len(self._profiles)

    def __repr__(self) -> str:
        return (
            f"UnmetNeedScorer(portfolio_size={len(self._profiles)}, "
            f"weights={self.weights})"
        )


__all__ = [
    "DEFAULT_WEIGHTS",
    "DiseaseAreaProfile",
    "UnmetNeedScore",
    "UnmetNeedScorer",
]

# Suppress unused-import lint for ``replace`` — kept as public re-export
# for downstream consumers wanting to derive modified profiles.
_ = replace
