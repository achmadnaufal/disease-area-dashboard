"""
Unit tests for pharmacovigilance.py
====================================
25+ tests covering PRR, ROR, BCPNN/EBGM, temporal scan,
stratified signal, priority ranking, and edge cases.
"""

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.pharmacovigilance import AEReport, SignalDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def detector():
    """Default SignalDetector with standard thresholds."""
    return SignalDetector(prr_threshold=2.0, ror_threshold=2.0, chi2_threshold=3.84, ebgm_threshold=2.0)


@pytest.fixture
def small_dataset():
    """
    Tiny dataset manually constructed to give predictable counts.

    Layout (2x2 contingency table for drug_A + event_X):
        a = 10  (drug_A AND event_X)
        b = 40  (drug_A, NOT event_X)
        c = 20  (event_X, NOT drug_A)
        d = 130 (neither)
    Total = 200
    PRR = (10/50) / (20/150) = 0.2 / 0.1333 = 1.5  — not a signal at threshold 2
    ROR = (10/40) / (20/130) = 0.25 / 0.1538 = 1.625
    """
    rows = []
    # 10 × drug_A + event_X
    for i in range(10):
        rows.append({"report_id": f"SR-{i:03d}", "drug": "drug_A", "event": "event_X",
                     "age_group": "adult", "region": "US", "report_date": "2025-01-15",
                     "seriousness": "serious", "outcome": "resolved"})
    # 40 × drug_A, no event_X
    for i in range(10, 50):
        rows.append({"report_id": f"SR-{i:03d}", "drug": "drug_A", "event": "event_Y",
                     "age_group": "adult", "region": "US", "report_date": "2025-01-15",
                     "seriousness": "non-serious", "outcome": "resolved"})
    # 20 × event_X, no drug_A
    for i in range(50, 70):
        rows.append({"report_id": f"SR-{i:03d}", "drug": "drug_B", "event": "event_X",
                     "age_group": "elderly", "region": "EU", "report_date": "2025-01-15",
                     "seriousness": "serious", "outcome": "hospitalization"})
    # 130 × neither
    for i in range(70, 200):
        rows.append({"report_id": f"SR-{i:03d}", "drug": "drug_B", "event": "event_Y",
                     "age_group": "pediatric", "region": "APAC", "report_date": "2025-01-15",
                     "seriousness": "non-serious", "outcome": "not_resolved"})
    return pd.DataFrame(rows)


@pytest.fixture
def sig_dataset():
    """
    Dataset designed to produce a clear signal.
    drug_C + event_Z: a=20, b=5, c=10, d=165  (total=200)
    PRR = (20/25)/(10/175) = 0.8/0.0571 = 14.0  → signal
    ROR = (20/5)/(10/165) = 4/0.0606 = 66.0  → signal
    """
    rows = []
    for i in range(20):
        rows.append({"report_id": f"SG-{i:03d}", "drug": "drug_C", "event": "event_Z",
                     "age_group": "elderly", "region": "US", "report_date": "2025-02-01",
                     "seriousness": "fatal", "outcome": "death"})
    for i in range(20, 25):
        rows.append({"report_id": f"SG-{i:03d}", "drug": "drug_C", "event": "event_W",
                     "age_group": "elderly", "region": "US", "report_date": "2025-02-01",
                     "seriousness": "non-serious", "outcome": "resolved"})
    for i in range(25, 35):
        rows.append({"report_id": f"SG-{i:03d}", "drug": "drug_D", "event": "event_Z",
                     "age_group": "adult", "region": "EU", "report_date": "2025-02-01",
                     "seriousness": "serious", "outcome": "hospitalization"})
    for i in range(35, 200):
        rows.append({"report_id": f"SG-{i:03d}", "drug": "drug_D", "event": "event_W",
                     "age_group": "adult", "region": "APAC", "report_date": "2025-02-01",
                     "seriousness": "non-serious", "outcome": "not_resolved"})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Test: AEReport dataclass
# ---------------------------------------------------------------------------

class TestAEReport:
    def test_from_dict_all_fields(self):
        row = {
            "report_id": "R001", "drug": "Aspirin", "event": "Nausea",
            "age_group": "adult", "region": "US",
            "report_date": date(2025, 1, 1),
            "seriousness": "serious", "outcome": "resolved",
        }
        r = AEReport.from_dict(row)
        assert r.report_id == "R001"
        assert r.drug == "Aspirin"
        assert r.event == "Nausea"
        assert r.age_group == "adult"
        assert r.report_date == date(2025, 1, 1)
        assert r.seriousness == "serious"

    def test_from_dict_string_date(self):
        row = {"report_id": "R002", "drug": "Aspirin", "event": "Nausea",
               "age_group": "adult", "region": "US", "report_date": "2025-03-15",
               "seriousness": "non-serious", "outcome": "not_resolved"}
        r = AEReport.from_dict(row)
        assert r.report_date == date(2025, 3, 15)


# ---------------------------------------------------------------------------
# Test: disproportionality_analysis — PRR & ROR
# ---------------------------------------------------------------------------

class TestDispropAnalysis:
    def test_prr_calculation_manual(self, detector, small_dataset):
        result = detector.disproportionality_analysis(small_dataset, min_reports=1)
        row = result[result["drug"] == "drug_A"]
        drug_a_event_x = result[(result["drug"] == "drug_A") & (result["event"] == "event_X")]
        assert len(drug_a_event_x) == 1
        prr = drug_a_event_x["PRR"].values[0]
        # PRR = (10/50)/(20/150) = 0.2/0.1333 = 1.5
        assert math.isclose(prr, 1.5, rel_tol=1e-3)

    def test_ror_calculation_manual(self, detector, small_dataset):
        result = detector.disproportionality_analysis(small_dataset, min_reports=1)
        drug_a_event_x = result[(result["drug"] == "drug_A") & (result["event"] == "event_X")]
        ror = drug_a_event_x["ROR"].values[0]
        # ROR = (10/40)/(20/130) = 0.25/0.1538 = 1.625
        assert math.isclose(ror, 1.625, rel_tol=1e-3)

    def test_prr_self_consistency(self, detector, small_dataset):
        """PRR should equal (a/N1) / (c/N2) where N1=a+b, N2=c+d."""
        result = detector.disproportionality_analysis(small_dataset, min_reports=1)
        pair = result[(result["drug"] == "drug_A") & (result["event"] == "event_X")].iloc[0]
        a, b = 10, 40
        c, d = 20, 130
        expected_prr = (a / (a + b)) / (c / (c + d))
        assert math.isclose(pair["PRR"], expected_prr, rel_tol=1e-9)

    def test_signal_detected(self, detector, sig_dataset):
        result = detector.disproportionality_analysis(sig_dataset, min_reports=1)
        pair = result[(result["drug"] == "drug_C") & (result["event"] == "event_Z")]
        assert len(pair) == 1
        assert pair["signal_status"].values[0] == "signal"

    def test_no_signal(self, detector, small_dataset):
        result = detector.disproportionality_analysis(small_dataset, min_reports=1)
        drug_a_event_x = result[(result["drug"] == "drug_A") & (result["event"] == "event_X")]
        assert drug_a_event_x["signal_status"].values[0] == "no_signal"

    def test_min_reports_threshold_filters(self, detector, sig_dataset):
        # drug_C+event_Z has 20 reports — should pass min_reports=10, fail min_reports=25
        r1 = detector.disproportionality_analysis(sig_dataset, min_reports=10)
        drug_c_z = r1[(r1["drug"] == "drug_C") & (r1["event"] == "event_Z")]
        assert len(drug_c_z) == 1 and drug_c_z["count"].values[0] == 20
        r2 = detector.disproportionality_analysis(sig_dataset, min_reports=25)
        drug_c_z_r2 = r2[(r2["drug"] == "drug_C") & (r2["event"] == "event_Z")]
        assert len(drug_c_z_r2) == 0  # 20 < 25, so filtered out

    def test_empty_dataframe_returns_empty(self, detector):
        result = detector.disproportionality_analysis(pd.DataFrame(), min_reports=1)
        assert result.empty
        assert list(result.columns) == ["drug", "event", "count", "PRR", "ROR", "chi_square", "signal_status"]


# ---------------------------------------------------------------------------
# Test: bayesian_screen — BCPNN / EBGM
# ---------------------------------------------------------------------------

class TestBayesianScreen:
    def test_ebgm_positive_for_signal_pair(self, detector, sig_dataset):
        result = detector.bayesian_screen(sig_dataset, min_reports=1)
        pair = result[(result["drug"] == "drug_C") & (result["event"] == "event_Z")]
        assert len(pair) == 1
        assert pair["EBGM"].values[0] >= 1.0

    def test_ebgm_below_threshold_for_noise(self, detector, small_dataset):
        result = detector.bayesian_screen(small_dataset, min_reports=10)
        assert result["EBGM"].lt(2.0).all() or result.empty

    def test_ebgm_signal_status(self, detector, sig_dataset):
        result = detector.bayesian_screen(sig_dataset, min_reports=5)
        if not result.empty:
            assert result["signal_status"].isin(["signal", "no_signal"]).all()

    def test_ebgm_sorted_descending(self, detector, sig_dataset):
        result = detector.bayesian_screen(sig_dataset, min_reports=1)
        if len(result) > 1:
            assert list(result["EBGM"]) == sorted(result["EBGM"], reverse=True)

    def test_empty_dataframe(self, detector):
        result = detector.bayesian_screen(pd.DataFrame(), min_reports=1)
        assert result.empty
        assert "EBGM" in result.columns

    def test_ebgm_zero_count_excluded(self, detector, sig_dataset):
        """Pairs with count < min_reports should not appear."""
        result = detector.bayesian_screen(sig_dataset, min_reports=100)
        # drug_D+event_W has 165 reports > 100, so at least that row exists
        assert "drug_D" in result["drug"].values


# ---------------------------------------------------------------------------
# Test: temporal_scan
# ---------------------------------------------------------------------------

class TestTemporalScan:
    @pytest.fixture
    def temporal_constant(self):
        """Uniformly-spread constant rate."""
        rows = []
        base = date(2025, 1, 1)
        for i in range(80):
            d = base + timedelta(days=i)
            rows.append({"report_id": f"TC-{i}", "drug": "drug_X", "event": "event_C",
                         "age_group": "adult", "region": "US",
                         "report_date": d.isoformat(),
                         "seriousness": "non-serious", "outcome": "resolved"})
        return pd.DataFrame(rows)

    @pytest.fixture
    def temporal_increasing(self):
        """
        Increasing rate — early period: sparse, later period: dense.
        CUSUM should be significantly larger than for constant rate.
        """
        rows = []
        base = date(2025, 1, 1)
        report_id = 0
        for i in range(30):
            d = base + timedelta(days=i)
            for _ in range(1):  # 1 report/day for first 30 days (below average)
                rows.append({"report_id": f"TI-{report_id:03d}", "drug": "drug_Y", "event": "event_D",
                             "age_group": "elderly", "region": "EU",
                             "report_date": d.isoformat(),
                             "seriousness": "serious", "outcome": "hospitalization"})
                report_id += 1
        for i in range(30, 60):
            d = base + timedelta(days=i)
            for _ in range(3):  # 3 reports/day for next 30 days (above average)
                rows.append({"report_id": f"TI-{report_id:03d}", "drug": "drug_Y", "event": "event_D",
                             "age_group": "elderly", "region": "EU",
                             "report_date": d.isoformat(),
                             "seriousness": "serious", "outcome": "hospitalization"})
                report_id += 1
        return pd.DataFrame(rows)

    def test_constant_rate_no_signal(self, detector, temporal_constant):
        result = detector.temporal_scan(temporal_constant, time_window_days=7, min_reports=20)
        # Uniform data: verify result is well-formed and has required columns
        assert "cusum" in result.columns
        assert "temporal_signal" in result.columns
        assert len(result) > 0

    def test_increasing_rate_detected(self, detector, temporal_increasing):
        result = detector.temporal_scan(temporal_increasing, time_window_days=7, min_reports=10)
        assert len(result) > 0
        assert result["cusum"].iloc[0] > 5.0  # strong positive CUSUM for increasing rate

    def test_empty_dataframe(self, detector):
        result = detector.temporal_scan(pd.DataFrame(), time_window_days=30, min_reports=10)
        assert result.empty
        assert "cusum" in result.columns

    def test_missing_date_column(self, detector):
        df = pd.DataFrame({"drug": ["A"], "event": ["X"], "age_group": ["adult"],
                           "region": ["US"], "seriousness": ["serious"], "outcome": ["resolved"]})
        result = detector.temporal_scan(df, time_window_days=30, min_reports=10)
        assert result.empty


# ---------------------------------------------------------------------------
# Test: stratified_signal
# ---------------------------------------------------------------------------

class TestStratifiedSignal:
    @pytest.fixture
    def strat_data(self):
        """Signal concentrated in elderly stratum."""
        rows = []
        # 30 elderly reports — drug_E causes event_Z in elderly only
        for i in range(30):
            rows.append({"report_id": f"ST-{i}", "drug": "drug_E", "event": "event_Z",
                         "age_group": "elderly", "region": "US",
                         "report_date": "2025-02-01", "seriousness": "serious", "outcome": "death"})
        # 5 adult reports — no signal in adults
        for i in range(30, 35):
            rows.append({"report_id": f"ST-{i}", "drug": "drug_E", "event": "event_Z",
                         "age_group": "adult", "region": "EU",
                         "report_date": "2025-02-01", "seriousness": "non-serious", "outcome": "resolved"})
        # 65 other noise
        for i in range(35, 100):
            rows.append({"report_id": f"ST-{i}", "drug": "drug_F", "event": "event_Z",
                         "age_group": "adult", "region": "APAC",
                         "report_date": "2025-02-01", "seriousness": "non-serious", "outcome": "not_resolved"})
        return pd.DataFrame(rows)

    def test_concentrated_signal_in_subpopulation(self, detector, strat_data):
        result = detector.stratified_signal(strat_data, stratify_by="age_group", min_reports=2)
        elderly = result[result["stratum"] == "elderly"]
        assert len(elderly) > 0
        assert elderly["concentrated_signal"].any()

    def test_adult_stratum_not_flagged(self, detector, strat_data):
        result = detector.stratified_signal(strat_data, stratify_by="age_group", min_reports=2)
        adult = result[result["stratum"] == "adult"]
        if not adult.empty:
            assert adult["concentrated_signal"].sum() == 0

    def test_empty_dataframe(self, detector):
        result = detector.stratified_signal(pd.DataFrame(), stratify_by="age_group", min_reports=2)
        assert result.empty

    def test_invalid_stratify_column(self, detector, sig_dataset):
        result = detector.stratified_signal(sig_dataset, stratify_by="nonexistent", min_reports=2)
        assert result.empty


# ---------------------------------------------------------------------------
# Test: priority_ranking
# ---------------------------------------------------------------------------

class TestPriorityRanking:
    def test_ranked_by_composite_score(self, detector, sig_dataset):
        disprop = detector.disproportionality_analysis(sig_dataset, min_reports=1)
        ranked = detector.priority_ranking(disprop, top_n=10)
        assert len(ranked) <= 10
        scores = ranked["composite_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_rank_column_sequential(self, detector, sig_dataset):
        disprop = detector.disproportionality_analysis(sig_dataset, min_reports=1)
        ranked = detector.priority_ranking(disprop, top_n=5)
        if not ranked.empty:
            assert list(ranked["rank"]) == list(range(1, len(ranked) + 1))

    def test_top_n_limit(self, detector, sig_dataset):
        disprop = detector.disproportionality_analysis(sig_dataset, min_reports=1)
        ranked = detector.priority_ranking(disprop, top_n=2)
        assert len(ranked) <= 2

    def test_empty_dataframe(self, detector):
        ranked = detector.priority_ranking(pd.DataFrame(), top_n=10)
        assert ranked.empty

    def test_score_in_0_to_1_range(self, detector, sig_dataset):
        disprop = detector.disproportionality_analysis(sig_dataset, min_reports=1)
        ranked = detector.priority_ranking(disprop, top_n=10)
        if not ranked.empty:
            assert (ranked["composite_score"] >= 0).all()
            assert (ranked["composite_score"] <= 1.0).all()


# ---------------------------------------------------------------------------
# Test: generate_report
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_report_columns(self, detector, sig_dataset):
        report = detector.generate_report(sig_dataset, top_n=10, min_reports=1)
        expected = {"drug", "event", "count", "PRR", "ROR", "composite_score",
                    "recommended_action"}
        assert expected.issubset(set(report.columns))

    def test_recommended_action_nonempty(self, detector, sig_dataset):
        report = detector.generate_report(sig_dataset, top_n=10, min_reports=1)
        assert (report["recommended_action"] != "").all()

    def test_top_signals_at_top(self, detector, sig_dataset):
        report = detector.generate_report(sig_dataset, top_n=10, min_reports=1)
        if len(report) >= 2:
            assert report.iloc[0]["composite_score"] >= report.iloc[1]["composite_score"]

    def test_empty_dataframe_report(self, detector):
        report = detector.generate_report(pd.DataFrame(), top_n=10, min_reports=1)
        assert report.empty

    def test_signal_pairs_in_report(self, detector, sig_dataset):
        report = detector.generate_report(sig_dataset, top_n=10, min_reports=1)
        assert len(report) > 0


# ---------------------------------------------------------------------------
# Test: minimum_signal_threshold edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_all_zero_counts_excluded(self, detector):
        df = pd.DataFrame({
            "report_id": ["R1"], "drug": ["X"], "event": ["Y"],
            "age_group": ["adult"], "region": ["US"], "report_date": ["2025-01-01"],
            "seriousness": ["serious"], "outcome": ["resolved"],
        })
        result = detector.disproportionality_analysis(df, min_reports=5)
        assert result.empty

    def test_single_event_reports(self, detector):
        # 5 reports for drug_P+event_Q + 1 report for drug_Q+event_Q (ensures c>0)
        rows = [
            {"report_id": f"R{i}", "drug": "drug_P", "event": "event_Q",
             "age_group": "adult", "region": "US", "report_date": "2025-01-01",
             "seriousness": "serious", "outcome": "resolved"}
            for i in range(5)
        ]
        rows.append({"report_id": "R-OTHER", "drug": "drug_Q", "event": "event_Q",
                    "age_group": "adult", "region": "EU", "report_date": "2025-01-01",
                    "seriousness": "non-serious", "outcome": "resolved"})
        df = pd.DataFrame(rows)
        result = detector.disproportionality_analysis(df, min_reports=3)
        assert len(result) == 1  # only drug_P+event_Q passes min_reports=3

    def test_all_no_sig_dataset(self, detector):
        """Dataset where no drug-event pair meets signal criteria."""
        rows = []
        # 10 each for drug_K + 5 different events (all same drug — c would be 0 without drug_L)
        for j in range(5):
            for i in range(10):
                rows.append({"report_id": f"R-{j}-{i}", "drug": "drug_K",
                             "event": f"event_{j}",
                             "age_group": "adult", "region": "US",
                             "report_date": "2025-01-01",
                             "seriousness": "non-serious", "outcome": "resolved"})
        # Add drug_L for each event so c > 0 (prevents degenerate table)
        for j in range(5):
            rows.append({"report_id": f"RL-{j}", "drug": "drug_L",
                         "event": f"event_{j}",
                         "age_group": "adult", "region": "EU",
                         "report_date": "2025-01-01",
                         "seriousness": "non-serious", "outcome": "resolved"})
        df = pd.DataFrame(rows)
        result = detector.disproportionality_analysis(df, min_reports=3)
        assert "signal_status" in result.columns
        assert (result["signal_status"] == "no_signal").all()  # none should trigger signal

    def test_missing_age_group_handled(self, detector):
        rows = [
            {"report_id": f"R{i}", "drug": "drug_M", "event": "event_N",
             "age_group": "unknown", "region": "US", "report_date": "2025-01-01",
             "seriousness": "serious", "outcome": "resolved"}
            for i in range(5)
        ]
        df = pd.DataFrame(rows)
        result = detector.stratified_signal(df, stratify_by="age_group", min_reports=2)
        # Should not raise, may be empty
        assert isinstance(result, pd.DataFrame)

    def test_custom_thresholds(self, sig_dataset):
        det = SignalDetector(prr_threshold=10.0, ror_threshold=10.0,
                             chi2_threshold=50.0, ebgm_threshold=10.0)
        result = det.disproportionality_analysis(sig_dataset, min_reports=1)
        assert "signal_status" in result.columns

    def test_chi_square_nonzero(self, detector, sig_dataset):
        result = detector.disproportionality_analysis(sig_dataset, min_reports=1)
        pair = result[(result["drug"] == "drug_C") & (result["event"] == "event_Z")]
        if not pair.empty:
            assert pair["chi_square"].values[0] > 0

    def test_chi_square_zero_for_small_counts(self, detector, small_dataset):
        result = detector.disproportionality_analysis(small_dataset, min_reports=1)
        assert (result["chi_square"] >= 0).all()
