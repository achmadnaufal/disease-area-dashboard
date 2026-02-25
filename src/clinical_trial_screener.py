"""Clinical trial patient screener and eligibility checker.

Implements CTCAE v5.0-aligned inclusion/exclusion criteria checking,
ECOG performance status assessment, and organ function eligibility
for oncology and rare disease clinical trials.

References:
    NCI CTCAE v5.0 (2017) Common Terminology Criteria for Adverse Events.
    ECOG-ACRIN (2020) ECOG Performance Status Scale.
    ICH E6(R2) (2016) Guideline for Good Clinical Practice.
    FDA (2020) Enhancing the Diversity of Clinical Trial Populations — Eligibility Criteria, Enrolment Practices, and Trial Designs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ECOGStatus(Enum):
    """Eastern Cooperative Oncology Group (ECOG) performance status."""
    PS0 = 0  # Fully active, no restrictions
    PS1 = 1  # Restricted in strenuous activity; ambulatory; light work
    PS2 = 2  # Ambulatory >50% of waking hours; limited self-care
    PS3 = 3  # Confined to bed/chair >50% of waking hours
    PS4 = 4  # Completely disabled


class EligibilityStatus(Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    NEEDS_REVIEW = "needs_review"  # Criteria met but requires PI discretion


@dataclass
class LabValue:
    """A single laboratory test result.

    Args:
        test_name: Standardised test name (e.g. "creatinine_umol_l").
        value: Numeric result.
        unit: Measurement unit.
        uln: Upper Limit of Normal for the performing lab (optional).
        lln: Lower Limit of Normal (optional).
    """
    test_name: str
    value: float
    unit: str
    uln: Optional[float] = None  # Upper Limit of Normal
    lln: Optional[float] = None  # Lower Limit of Normal

    @property
    def times_uln(self) -> Optional[float]:
        """Value expressed as × Upper Limit of Normal."""
        if self.uln and self.uln > 0:
            return self.value / self.uln
        return None


@dataclass
class PatientProfile:
    """Candidate patient profile for trial eligibility screening.

    Args:
        patient_id: De-identified patient identifier.
        age: Age in years.
        ecog_status: ECOG performance status.
        diagnosis_code: ICD-10 primary diagnosis code.
        stage: Disease stage (e.g. "III", "IV", "relapsed_refractory").
        prior_therapy_lines: Number of prior treatment lines.
        labs: Dict of lab_name → LabValue.
        comorbidities: List of ICD-10 comorbidity codes.
        weight_kg: Body weight in kg (for dose calculation eligibility).
        creatinine_clearance_ml_min: Cockcroft-Gault CrCl (ml/min).
        is_pregnant: Pregnancy status (None = not assessed).
        active_infection: Whether active uncontrolled infection present.
        brain_metastases: Whether brain metastases present.
        notes: Free-text clinical notes.
    """
    patient_id: str
    age: int
    ecog_status: ECOGStatus
    diagnosis_code: str
    stage: str
    prior_therapy_lines: int
    labs: Dict[str, LabValue] = field(default_factory=dict)
    comorbidities: List[str] = field(default_factory=list)
    weight_kg: Optional[float] = None
    creatinine_clearance_ml_min: Optional[float] = None
    is_pregnant: Optional[bool] = None
    active_infection: bool = False
    brain_metastases: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if self.age < 0 or self.age > 130:
            raise ValueError(f"age {self.age} is out of range 0–130")
        if self.prior_therapy_lines < 0:
            raise ValueError("prior_therapy_lines must be non-negative")


@dataclass
class TrialProtocol:
    """Simplified clinical trial inclusion/exclusion criteria.

    Args:
        trial_id: Unique trial identifier (e.g. NCT number).
        trial_name: Short trial name.
        indication: Disease indication (ICD-10 prefix).
        min_age: Minimum patient age (inclusive).
        max_age: Maximum patient age (inclusive), None = no limit.
        max_ecog: Maximum acceptable ECOG score.
        required_stages: Accepted disease stages (empty = any).
        prior_therapy_min: Minimum prior therapy lines required.
        prior_therapy_max: Maximum prior therapy lines allowed (None = no limit).
        min_crcl_ml_min: Minimum creatinine clearance (ml/min).
        max_alt_times_uln: Maximum ALT as × ULN.
        max_ast_times_uln: Maximum AST as × ULN.
        max_bilirubin_times_uln: Maximum total bilirubin × ULN.
        max_neutrophils_times_lln: Minimum ANC (× 10^9/L).
        exclude_pregnancy: Whether pregnancy is an exclusion criterion.
        exclude_brain_mets: Whether brain metastases are excluded.
        exclude_active_infection: Whether active infection is excluded.
        exclude_comorbidities: ICD-10 codes that exclude patients.
    """
    trial_id: str
    trial_name: str
    indication: str
    min_age: int = 18
    max_age: Optional[int] = None
    max_ecog: int = 2
    required_stages: List[str] = field(default_factory=list)
    prior_therapy_min: int = 0
    prior_therapy_max: Optional[int] = None
    min_crcl_ml_min: float = 30.0
    max_alt_times_uln: float = 3.0
    max_ast_times_uln: float = 3.0
    max_bilirubin_times_uln: float = 1.5
    min_anc_10e9_l: float = 1.0
    exclude_pregnancy: bool = True
    exclude_brain_mets: bool = True
    exclude_active_infection: bool = True
    exclude_comorbidities: List[str] = field(default_factory=list)


@dataclass
class EligibilityResult:
    """Result of screening a patient against a trial protocol."""
    patient_id: str
    trial_id: str
    status: EligibilityStatus
    passed_criteria: List[str]
    failed_criteria: List[str]
    review_items: List[str]
    screening_notes: str


class ClinicalTrialScreener:
    """Screen patient profiles against clinical trial eligibility criteria.

    Checks inclusion/exclusion criteria in a standardised order and returns
    a structured eligibility report with specific criteria outcomes.

    Example::

        screener = ClinicalTrialScreener()
        protocol = TrialProtocol(
            trial_id="NCT12345678", trial_name="Phase II NSCLC Study",
            indication="C34", min_age=18, max_ecog=1,
            required_stages=["IIIB", "IV"],
        )
        patient = PatientProfile(
            patient_id="PT-001", age=55, ecog_status=ECOGStatus.PS1,
            diagnosis_code="C34.9", stage="IV", prior_therapy_lines=1,
            labs={"alt": LabValue("alt", 35.0, "U/L", uln=45.0)},
            creatinine_clearance_ml_min=72.0,
        )
        result = screener.screen(patient, protocol)
        print(result.status)  # EligibilityStatus.ELIGIBLE
    """

    def screen(
        self, patient: PatientProfile, protocol: TrialProtocol
    ) -> EligibilityResult:
        """Screen a patient against a trial protocol.

        Args:
            patient: PatientProfile with clinical data.
            protocol: TrialProtocol with eligibility criteria.

        Returns:
            EligibilityResult with status and criterion-by-criterion breakdown.
        """
        if not isinstance(patient, PatientProfile):
            raise TypeError("patient must be a PatientProfile")
        if not isinstance(protocol, TrialProtocol):
            raise TypeError("protocol must be a TrialProtocol")

        passed = []
        failed = []
        review = []

        def _check(criterion_name: str, condition: bool, failure_msg: str, is_review: bool = False) -> bool:
            if condition:
                passed.append(criterion_name)
                return True
            else:
                if is_review:
                    review.append(f"{criterion_name}: {failure_msg}")
                else:
                    failed.append(f"{criterion_name}: {failure_msg}")
                return False

        # --- Age ---
        _check("age_min", patient.age >= protocol.min_age,
               f"Age {patient.age} < minimum {protocol.min_age}")
        if protocol.max_age is not None:
            _check("age_max", patient.age <= protocol.max_age,
                   f"Age {patient.age} > maximum {protocol.max_age}")

        # --- Diagnosis ---
        _check("indication", patient.diagnosis_code.startswith(protocol.indication),
               f"Diagnosis {patient.diagnosis_code} does not match indication {protocol.indication}")

        # --- Stage ---
        if protocol.required_stages:
            _check("disease_stage", patient.stage in protocol.required_stages,
                   f"Stage '{patient.stage}' not in required {protocol.required_stages}")

        # --- ECOG ---
        _check("ecog_status", patient.ecog_status.value <= protocol.max_ecog,
               f"ECOG PS{patient.ecog_status.value} exceeds maximum PS{protocol.max_ecog}")

        # --- Prior therapy lines ---
        _check("prior_therapy_min", patient.prior_therapy_lines >= protocol.prior_therapy_min,
               f"Prior lines {patient.prior_therapy_lines} < minimum {protocol.prior_therapy_min}")
        if protocol.prior_therapy_max is not None:
            _check("prior_therapy_max", patient.prior_therapy_lines <= protocol.prior_therapy_max,
                   f"Prior lines {patient.prior_therapy_lines} > maximum {protocol.prior_therapy_max}")

        # --- Renal function ---
        if patient.creatinine_clearance_ml_min is not None:
            _check("crcl", patient.creatinine_clearance_ml_min >= protocol.min_crcl_ml_min,
                   f"CrCl {patient.creatinine_clearance_ml_min:.0f} < minimum {protocol.min_crcl_ml_min:.0f} ml/min")
        else:
            review.append("crcl: Creatinine clearance not provided — requires measurement")

        # --- Liver function ---
        for lab_key, max_uln, criterion_name in [
            ("alt", protocol.max_alt_times_uln, "alt_uln"),
            ("ast", protocol.max_ast_times_uln, "ast_uln"),
            ("bilirubin", protocol.max_bilirubin_times_uln, "bilirubin_uln"),
        ]:
            if lab_key in patient.labs:
                lab = patient.labs[lab_key]
                xul = lab.times_uln
                if xul is not None:
                    _check(criterion_name, xul <= max_uln,
                           f"{lab_key.upper()} {xul:.1f}× ULN exceeds limit {max_uln}× ULN")
                else:
                    review.append(f"{criterion_name}: {lab_key} ULN not provided — requires lab-specific ULN")
            else:
                review.append(f"{criterion_name}: {lab_key.upper()} not measured")

        # --- ANC ---
        if "anc" in patient.labs:
            _check("anc", patient.labs["anc"].value >= protocol.min_anc_10e9_l,
                   f"ANC {patient.labs['anc'].value:.1f} × 10^9/L < minimum {protocol.min_anc_10e9_l}")
        else:
            review.append("anc: ANC not measured")

        # --- Exclusions ---
        if protocol.exclude_pregnancy and patient.is_pregnant:
            failed.append("pregnancy: Patient is pregnant — exclusion criterion")
        elif protocol.exclude_pregnancy and patient.is_pregnant is None:
            review.append("pregnancy: Pregnancy status not assessed")

        if protocol.exclude_brain_mets:
            _check("brain_mets", not patient.brain_metastases,
                   "Patient has brain metastases — exclusion criterion")

        if protocol.exclude_active_infection:
            _check("active_infection", not patient.active_infection,
                   "Patient has active uncontrolled infection — exclusion criterion")

        # --- Comorbidity exclusions ---
        for excl_code in protocol.exclude_comorbidities:
            matching = [c for c in patient.comorbidities if c.startswith(excl_code)]
            if matching:
                failed.append(
                    f"comorbidity_exclusion: Excluded comorbidity {matching[0]} present"
                )

        # Determine overall status
        if failed:
            status = EligibilityStatus.INELIGIBLE
        elif review:
            status = EligibilityStatus.NEEDS_REVIEW
        else:
            status = EligibilityStatus.ELIGIBLE

        note_parts = []
        if status == EligibilityStatus.ELIGIBLE:
            note_parts.append(f"Patient meets all {len(passed)} criteria for {protocol.trial_id}.")
        elif status == EligibilityStatus.INELIGIBLE:
            note_parts.append(
                f"Patient fails {len(failed)} criterion/criteria for {protocol.trial_id}."
            )
        else:
            note_parts.append(
                f"Patient passes {len(passed)} criteria but {len(review)} items require review."
            )

        return EligibilityResult(
            patient_id=patient.patient_id,
            trial_id=protocol.trial_id,
            status=status,
            passed_criteria=passed,
            failed_criteria=failed,
            review_items=review,
            screening_notes=" ".join(note_parts),
        )

    def batch_screen(
        self, patients: List[PatientProfile], protocol: TrialProtocol
    ) -> List[EligibilityResult]:
        """Screen multiple patients against the same protocol.

        Args:
            patients: List of PatientProfile instances.
            protocol: TrialProtocol to screen against.

        Returns:
            List of EligibilityResult, one per patient.
        """
        return [self.screen(p, protocol) for p in patients]

    def eligible_patients(
        self, patients: List[PatientProfile], protocol: TrialProtocol
    ) -> List[PatientProfile]:
        """Return only patients with ELIGIBLE status.

        Args:
            patients: Candidates to screen.
            protocol: Trial protocol.

        Returns:
            Subset of patients who meet all criteria.
        """
        results = self.batch_screen(patients, protocol)
        eligible_ids = {r.patient_id for r in results if r.status == EligibilityStatus.ELIGIBLE}
        return [p for p in patients if p.patient_id in eligible_ids]

    def enrolment_funnel(
        self, patients: List[PatientProfile], protocol: TrialProtocol
    ) -> Dict[str, int]:
        """Count patients by eligibility status for recruitment planning.

        Returns:
            Dict with counts for eligible, ineligible, and needs_review.
        """
        results = self.batch_screen(patients, protocol)
        funnel = {"eligible": 0, "ineligible": 0, "needs_review": 0, "total_screened": len(results)}
        for r in results:
            funnel[r.status.value] += 1
        return funnel
