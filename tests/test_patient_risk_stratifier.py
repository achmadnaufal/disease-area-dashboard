"""Unit tests for PatientRiskStratifier."""
import pytest
from src.patient_risk_stratifier import PatientRiskStratifier, PatientProfile


def _profile(**kwargs) -> PatientProfile:
    defaults = dict(
        patient_id="PT-001", age=60, ecog_ps=1, comorbidities=[],
        creatinine_mg_dl=None, albumin_g_dl=None
    )
    defaults.update(kwargs)
    return PatientProfile(**defaults)


class TestPatientProfileValidation:
    def test_valid_profile(self):
        p = _profile()
        assert p.patient_id == "PT-001"

    def test_invalid_ecog_raises(self):
        with pytest.raises(ValueError):
            _profile(ecog_ps=5)

    def test_negative_age_raises(self):
        with pytest.raises(ValueError):
            _profile(age=-1)

    def test_unknown_comorbidity_raises(self):
        with pytest.raises(ValueError):
            _profile(comorbidities=["flying_disease"])


class TestStratification:
    def setup_method(self):
        self.s = PatientRiskStratifier()

    def test_no_comorbidities_low_risk(self):
        r = self.s.stratify(_profile(age=40, comorbidities=[]))
        assert r["risk_tier"] == "LOW"
        assert r["cci_score"] == 0

    def test_cci_score_correct(self):
        r = self.s.stratify(_profile(comorbidities=["myocardial_infarction", "diabetes_uncomplicated"]))
        assert r["cci_score"] == 2

    def test_age_bonus_added(self):
        p50 = self.s.stratify(_profile(age=50, comorbidities=[]))
        p70 = self.s.stratify(_profile(age=70, comorbidities=[]))
        assert p70["age_adjusted_cci"] > p50["age_adjusted_cci"]

    def test_very_high_risk(self):
        r = self.s.stratify(_profile(comorbidities=["metastatic_solid_tumor", "moderate_severe_liver_disease"]))
        assert r["risk_tier"] == "VERY_HIGH"

    def test_survival_estimate_between_0_and_100(self):
        r = self.s.stratify(_profile())
        assert 0.0 <= r["survival_10yr_pct"] <= 100.0

    def test_high_creatinine_lab_flag(self):
        r = self.s.stratify(_profile(creatinine_mg_dl=2.0))
        assert any("creatinine" in f.lower() for f in r["lab_flags"])

    def test_hypoalbuminemia_lab_flag(self):
        r = self.s.stratify(_profile(albumin_g_dl=3.0))
        assert any("albumin" in f.lower() or "hypoalbumin" in f.lower() for f in r["lab_flags"])

    def test_ecog3_modifier(self):
        r = self.s.stratify(_profile(ecog_ps=3))
        assert "ECOG PS" in r["ecog_modifier"]

    def test_ecog0_no_modifier(self):
        r = self.s.stratify(_profile(ecog_ps=0))
        assert r["ecog_modifier"] == ""

    def test_recommendation_present(self):
        r = self.s.stratify(_profile())
        assert len(r["recommendation"]) > 0

    def test_batch_stratify_length(self):
        profiles = [_profile(patient_id=f"PT-{i:03d}") for i in range(5)]
        results = self.s.batch_stratify(profiles)
        assert len(results) == 5

    def test_population_summary(self):
        profiles = [
            _profile(patient_id="A", comorbidities=[]),
            _profile(patient_id="B", comorbidities=["metastatic_solid_tumor"]),
        ]
        summary = self.s.population_summary(profiles)
        assert summary["total_patients"] == 2
        assert 0.0 <= summary["pct_high_or_above"] <= 100.0

    def test_metastatic_disease_flag_adds_cci(self):
        r_no_meta = self.s.stratify(_profile(has_metastatic_disease=False, comorbidities=[]))
        r_meta = self.s.stratify(_profile(has_metastatic_disease=True, comorbidities=[]))
        assert r_meta["cci_score"] > r_no_meta["cci_score"]
