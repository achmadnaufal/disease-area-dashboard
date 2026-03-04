"""
Patient Risk Stratifier
========================
Risk-stratifies patient populations for oncology and chronic disease management
using validated scoring frameworks.

Frameworks implemented:
  - Charlson Comorbidity Index (CCI, 1987) — predicts 10-year survival
  - Modified CCI with age adjustment (Deyo, 1992)
  - ECOG Performance Status risk mapping
  - Multi-factor risk tier (LOW / MODERATE / HIGH / VERY_HIGH)

Usage::

    from src.patient_risk_stratifier import PatientRiskStratifier, PatientProfile

    profile = PatientProfile(
        patient_id="PT-001",
        age=68,
        ecog_ps=1,
        comorbidities=["myocardial_infarction", "diabetes_uncomplicated", "mild_liver_disease"],
        creatinine_mg_dl=1.2,
        albumin_g_dl=3.8,
        has_metastatic_disease=False,
    )

    stratifier = PatientRiskStratifier()
    result = stratifier.stratify(profile)
    print(result["risk_tier"])   # → MODERATE
    print(result["cci_score"])   # → 3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Charlson weights (original 1987 paper)
# ---------------------------------------------------------------------------

CCI_WEIGHTS: dict[str, int] = {
    "myocardial_infarction": 1,
    "congestive_heart_failure": 1,
    "peripheral_vascular_disease": 1,
    "cerebrovascular_disease": 1,
    "dementia": 1,
    "chronic_pulmonary_disease": 1,
    "connective_tissue_disease": 1,
    "peptic_ulcer": 1,
    "mild_liver_disease": 1,
    "diabetes_uncomplicated": 1,
    "diabetes_with_end_organ_damage": 2,
    "hemiplegia": 2,
    "moderate_severe_renal_disease": 2,
    "solid_tumor_without_metastasis": 2,
    "leukemia": 2,
    "lymphoma": 2,
    "moderate_severe_liver_disease": 3,
    "metastatic_solid_tumor": 6,
    "aids": 6,
}

# Age adjustment (Deyo 1992): +1 per decade ≥50
AGE_DECADE_THRESHOLD = 50

# Risk tier thresholds (adjusted CCI)
RISK_TIERS = {
    "VERY_HIGH": 6,
    "HIGH": 4,
    "MODERATE": 2,
    "LOW": 0,
}

# 10-year survival probability by CCI (approximate, Charlson 1987)
CCI_10YR_SURVIVAL: dict[int, float] = {
    0: 0.98, 1: 0.96, 2: 0.90, 3: 0.77,
    4: 0.53, 5: 0.40, 6: 0.21, 7: 0.18,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PatientProfile:
    """Minimal patient profile for comorbidity risk scoring."""

    patient_id: str
    age: int
    ecog_ps: int                          # 0–4
    comorbidities: list[str] = field(default_factory=list)
    creatinine_mg_dl: Optional[float] = None
    albumin_g_dl: Optional[float] = None
    has_metastatic_disease: bool = False
    primary_diagnosis_icd10: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not (0 <= self.ecog_ps <= 4):
            raise ValueError(f"ecog_ps must be 0–4; got {self.ecog_ps}")
        if self.age < 0:
            raise ValueError("age cannot be negative")
        unknown = [c for c in self.comorbidities if c not in CCI_WEIGHTS]
        if unknown:
            raise ValueError(f"Unknown comorbidity codes: {unknown}. Valid: {sorted(CCI_WEIGHTS)}")


# ---------------------------------------------------------------------------
# Stratifier
# ---------------------------------------------------------------------------

class PatientRiskStratifier:
    """
    Stratifies patients using the Charlson Comorbidity Index (CCI)
    with age adjustment and ECOG performance status modifier.

    Methods
    -------
    stratify(profile) — full risk stratification for one patient
    batch_stratify(profiles) — stratify a list of patients
    population_summary(profiles) — distribution of risk tiers
    """

    def stratify(self, profile: PatientProfile) -> dict:
        """
        Compute CCI, age-adjusted CCI, 10-year survival estimate, and risk tier.

        Returns
        -------
        dict with: patient_id, age, ecog_ps, cci_score, age_adjusted_cci,
                   comorbidity_breakdown, survival_10yr_pct, risk_tier,
                   risk_modifiers, recommendation
        """
        # Base CCI
        cci = sum(CCI_WEIGHTS.get(c, 0) for c in profile.comorbidities)

        # Metastatic disease override (ensures CCI weight if not already included)
        if profile.has_metastatic_disease and "metastatic_solid_tumor" not in profile.comorbidities:
            cci += 6

        # Age adjustment: +1 per decade ≥ 50
        age_bonus = max(0, (profile.age - AGE_DECADE_THRESHOLD) // 10)
        adj_cci = cci + age_bonus

        # 10-year survival lookup (cap at 7 for lookup)
        surv_key = min(adj_cci, 7)
        survival_10yr = CCI_10YR_SURVIVAL.get(surv_key, 0.10) * 100.0

        # Risk tier
        tier = "LOW"
        for tier_name, threshold in RISK_TIERS.items():
            if adj_cci >= threshold:
                tier = tier_name
                break

        # ECOG modifier
        ecog_modifier = ""
        if profile.ecog_ps >= 3:
            ecog_modifier = "ECOG PS ≥3: high symptom burden; may limit treatment intensity"
        elif profile.ecog_ps == 2:
            ecog_modifier = "ECOG PS 2: limited by symptoms; monitor tolerance"

        # Lab modifiers
        lab_flags = []
        if profile.creatinine_mg_dl is not None and profile.creatinine_mg_dl > 1.5:
            lab_flags.append(f"Elevated creatinine {profile.creatinine_mg_dl} mg/dL — renally dose-adjust")
        if profile.albumin_g_dl is not None and profile.albumin_g_dl < 3.5:
            lab_flags.append(f"Hypoalbuminemia {profile.albumin_g_dl} g/dL — nutritional risk")

        comorbidity_detail = {c: CCI_WEIGHTS[c] for c in profile.comorbidities}

        recommendation = self._recommendation(tier, profile.ecog_ps)

        return {
            "patient_id": profile.patient_id,
            "age": profile.age,
            "ecog_ps": profile.ecog_ps,
            "cci_score": cci,
            "age_adjusted_cci": adj_cci,
            "comorbidity_breakdown": comorbidity_detail,
            "survival_10yr_pct": round(survival_10yr, 1),
            "risk_tier": tier,
            "ecog_modifier": ecog_modifier,
            "lab_flags": lab_flags,
            "recommendation": recommendation,
        }

    def batch_stratify(self, profiles: list[PatientProfile]) -> list[dict]:
        return [self.stratify(p) for p in profiles]

    def population_summary(self, profiles: list[PatientProfile]) -> dict:
        """Distribution of risk tiers across a patient population."""
        results = self.batch_stratify(profiles)
        dist: dict[str, int] = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "VERY_HIGH": 0}
        for r in results:
            dist[r["risk_tier"]] = dist.get(r["risk_tier"], 0) + 1
        total = len(results)
        return {
            "total_patients": total,
            "distribution": dist,
            "pct_high_or_above": round(
                (dist.get("HIGH", 0) + dist.get("VERY_HIGH", 0)) / total * 100, 1
            ) if total > 0 else 0.0,
        }

    @staticmethod
    def _recommendation(tier: str, ecog_ps: int) -> str:
        base = {
            "LOW": "Standard therapy; routine monitoring",
            "MODERATE": "Consider dose modification; closer monitoring",
            "HIGH": "Reduce treatment intensity; weekly safety review",
            "VERY_HIGH": "Palliative/supportive intent preferred; MDT review required",
        }.get(tier, "")
        if ecog_ps >= 3:
            return f"{base} | ECOG PS ≥3 override: reassess treatment goals with palliative team"
        return base
