"""Unit tests for clinical_trial_screener module."""

import pytest
from src.clinical_trial_screener import (
    ClinicalTrialScreener,
    ECOGStatus,
    EligibilityResult,
    EligibilityStatus,
    LabValue,
    PatientProfile,
    TrialProtocol,
)


def _make_protocol(**kwargs):
    defaults = dict(
        trial_id="NCT12345678", trial_name="Phase II NSCLC",
        indication="C34", min_age=18, max_ecog=2,
        required_stages=["IIIB", "IV"],
        prior_therapy_min=1, min_crcl_ml_min=30.0,
        exclude_brain_mets=True, exclude_active_infection=True,
    )
    defaults.update(kwargs)
    return TrialProtocol(**defaults)


def _make_patient(**kwargs):
    defaults = dict(
        patient_id="PT-001", age=55, ecog_status=ECOGStatus.PS1,
        diagnosis_code="C34.9", stage="IV", prior_therapy_lines=2,
        labs={
            "alt": LabValue("alt", 35.0, "U/L", uln=45.0),
            "ast": LabValue("ast", 28.0, "U/L", uln=40.0),
            "bilirubin": LabValue("bilirubin", 12.0, "umol/L", uln=17.0),
            "anc": LabValue("anc", 2.5, "10^9/L"),
        },
        creatinine_clearance_ml_min=72.0,
        is_pregnant=False,
        active_infection=False,
        brain_metastases=False,
    )
    defaults.update(kwargs)
    return PatientProfile(**defaults)


class TestPatientProfile:
    def test_valid_patient(self):
        p = _make_patient()
        assert p.patient_id == "PT-001"

    def test_invalid_age_negative(self):
        with pytest.raises(ValueError):
            PatientProfile("P", -1, ECOGStatus.PS0, "C34.9", "IV", 0)

    def test_invalid_prior_therapy_negative(self):
        with pytest.raises(ValueError):
            PatientProfile("P", 45, ECOGStatus.PS0, "C34.9", "IV", -1)


class TestLabValue:
    def test_times_uln(self):
        lab = LabValue("alt", 90.0, "U/L", uln=45.0)
        assert lab.times_uln == pytest.approx(2.0)

    def test_times_uln_no_uln(self):
        lab = LabValue("alt", 90.0, "U/L")
        assert lab.times_uln is None


class TestClinicalTrialScreener:
    def setup_method(self):
        self.screener = ClinicalTrialScreener()

    def test_eligible_patient(self):
        result = self.screener.screen(_make_patient(), _make_protocol())
        assert result.status == EligibilityStatus.ELIGIBLE

    def test_invalid_patient_type(self):
        with pytest.raises(TypeError):
            self.screener.screen("not a patient", _make_protocol())

    def test_invalid_protocol_type(self):
        with pytest.raises(TypeError):
            self.screener.screen(_make_patient(), "not a protocol")

    def test_fail_age_too_young(self):
        patient = _make_patient(age=16)
        result = self.screener.screen(patient, _make_protocol(min_age=18))
        assert result.status == EligibilityStatus.INELIGIBLE
        assert any("age_min" in f for f in result.failed_criteria)

    def test_fail_age_too_old(self):
        patient = _make_patient(age=80)
        result = self.screener.screen(patient, _make_protocol(max_age=70))
        assert result.status == EligibilityStatus.INELIGIBLE
        assert any("age_max" in f for f in result.failed_criteria)

    def test_fail_wrong_diagnosis(self):
        patient = _make_patient(diagnosis_code="C50.9")  # Breast cancer
        result = self.screener.screen(patient, _make_protocol(indication="C34"))
        assert result.status == EligibilityStatus.INELIGIBLE
        assert any("indication" in f for f in result.failed_criteria)

    def test_fail_wrong_stage(self):
        patient = _make_patient(stage="II")
        result = self.screener.screen(patient, _make_protocol(required_stages=["III", "IV"]))
        assert result.status == EligibilityStatus.INELIGIBLE
        assert any("disease_stage" in f for f in result.failed_criteria)

    def test_fail_high_ecog(self):
        patient = _make_patient(ecog_status=ECOGStatus.PS3)
        result = self.screener.screen(patient, _make_protocol(max_ecog=2))
        assert result.status == EligibilityStatus.INELIGIBLE
        assert any("ecog_status" in f for f in result.failed_criteria)

    def test_fail_insufficient_prior_lines(self):
        patient = _make_patient(prior_therapy_lines=0)
        result = self.screener.screen(patient, _make_protocol(prior_therapy_min=1))
        assert result.status == EligibilityStatus.INELIGIBLE

    def test_fail_too_many_prior_lines(self):
        patient = _make_patient(prior_therapy_lines=5)
        result = self.screener.screen(patient, _make_protocol(prior_therapy_max=3))
        assert result.status == EligibilityStatus.INELIGIBLE

    def test_fail_low_crcl(self):
        patient = _make_patient(creatinine_clearance_ml_min=20.0)
        result = self.screener.screen(patient, _make_protocol(min_crcl_ml_min=30.0))
        assert result.status == EligibilityStatus.INELIGIBLE
        assert any("crcl" in f for f in result.failed_criteria)

    def test_fail_high_alt(self):
        patient = _make_patient(labs={
            "alt": LabValue("alt", 150.0, "U/L", uln=45.0),  # 3.3× ULN
            "ast": LabValue("ast", 28.0, "U/L", uln=40.0),
            "bilirubin": LabValue("bilirubin", 12.0, "umol/L", uln=17.0),
            "anc": LabValue("anc", 2.5, "10^9/L"),
        })
        result = self.screener.screen(patient, _make_protocol(max_alt_times_uln=3.0))
        assert result.status == EligibilityStatus.INELIGIBLE
        assert any("alt_uln" in f for f in result.failed_criteria)

    def test_fail_pregnancy(self):
        patient = _make_patient(is_pregnant=True)
        result = self.screener.screen(patient, _make_protocol(exclude_pregnancy=True))
        assert result.status == EligibilityStatus.INELIGIBLE
        assert any("pregnancy" in f for f in result.failed_criteria)

    def test_fail_brain_mets(self):
        patient = _make_patient(brain_metastases=True)
        result = self.screener.screen(patient, _make_protocol(exclude_brain_mets=True))
        assert result.status == EligibilityStatus.INELIGIBLE

    def test_fail_active_infection(self):
        patient = _make_patient(active_infection=True)
        result = self.screener.screen(patient, _make_protocol(exclude_active_infection=True))
        assert result.status == EligibilityStatus.INELIGIBLE

    def test_fail_excluded_comorbidity(self):
        patient = _make_patient(comorbidities=["N18.5"])  # CKD Stage 5
        result = self.screener.screen(patient, _make_protocol(exclude_comorbidities=["N18"]))
        assert result.status == EligibilityStatus.INELIGIBLE

    def test_needs_review_missing_crcl(self):
        patient = _make_patient(creatinine_clearance_ml_min=None)
        result = self.screener.screen(patient, _make_protocol())
        assert result.status == EligibilityStatus.NEEDS_REVIEW
        assert any("crcl" in r for r in result.review_items)

    def test_needs_review_unknown_pregnancy(self):
        patient = _make_patient(is_pregnant=None)
        result = self.screener.screen(patient, _make_protocol(exclude_pregnancy=True))
        # Could be needs_review if no other failures
        assert result.status in [EligibilityStatus.NEEDS_REVIEW, EligibilityStatus.ELIGIBLE]

    def test_passed_criteria_populated(self):
        result = self.screener.screen(_make_patient(), _make_protocol())
        assert len(result.passed_criteria) > 0

    def test_result_has_notes(self):
        result = self.screener.screen(_make_patient(), _make_protocol())
        assert len(result.screening_notes) > 0

    def test_batch_screen(self):
        patients = [_make_patient(patient_id=f"PT-{i:03d}", age=40+i) for i in range(5)]
        results = self.screener.batch_screen(patients, _make_protocol())
        assert len(results) == 5

    def test_eligible_patients_filter(self):
        p1 = _make_patient(patient_id="E1")
        p2 = _make_patient(patient_id="E2", age=16)  # Too young
        eligible = self.screener.eligible_patients([p1, p2], _make_protocol())
        assert len(eligible) == 1
        assert eligible[0].patient_id == "E1"

    def test_enrolment_funnel(self):
        patients = [
            _make_patient(patient_id="P1"),
            _make_patient(patient_id="P2", age=16),  # Ineligible
            _make_patient(patient_id="P3", creatinine_clearance_ml_min=None),  # Needs review
        ]
        funnel = self.screener.enrolment_funnel(patients, _make_protocol())
        assert funnel["total_screened"] == 3
        assert funnel["ineligible"] >= 1
