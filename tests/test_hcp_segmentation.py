"""
Unit tests for HCP prescriber segmentation and Share of Voice calculation.
"""
import pytest
import pandas as pd
from src.main import DiseaseAreaDashboard


@pytest.fixture
def dashboard():
    return DiseaseAreaDashboard()


@pytest.fixture
def prescriber_df():
    return pd.DataFrame({
        "prescriber_id": ["HCP-1"] * 4 + ["HCP-2"] * 3 + ["HCP-3"] * 2 + ["HCP-4"] * 1,
        "brand": ["DrugA", "DrugA", "DrugA", "DrugB",
                  "DrugB", "DrugB", "DrugA",
                  "DrugA", "DrugB",
                  "DrugC"],
        "units": [50, 40, 30, 10, 60, 50, 20, 5, 3, 2],
    })


class TestSegmentPrescribers:

    def test_returns_dataframe(self, dashboard, prescriber_df):
        result = dashboard.segment_prescribers(prescriber_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4  # 4 unique prescribers

    def test_required_columns_present(self, dashboard, prescriber_df):
        result = dashboard.segment_prescribers(prescriber_df)
        for col in ("prescriber_id", "total_units", "loyalty_score_pct", "hcp_segment"):
            assert col in result.columns

    def test_empty_dataframe_raises(self, dashboard):
        with pytest.raises(ValueError, match="DataFrame cannot be empty"):
            dashboard.segment_prescribers(pd.DataFrame())

    def test_missing_column_raises(self, dashboard, prescriber_df):
        bad_df = prescriber_df.drop(columns=["units"])
        with pytest.raises(ValueError, match="Missing required columns"):
            dashboard.segment_prescribers(bad_df, volume_col="units")

    def test_hcp_segments_are_valid(self, dashboard, prescriber_df):
        valid_segments = {"Champion", "High-Volume", "Loyal-Mid", "Low-Activity", "Opportunity"}
        result = dashboard.segment_prescribers(prescriber_df)
        for seg in result["hcp_segment"]:
            assert seg in valid_segments

    def test_loyalty_score_between_0_and_100(self, dashboard, prescriber_df):
        result = dashboard.segment_prescribers(prescriber_df)
        assert (result["loyalty_score_pct"] >= 0).all()
        assert (result["loyalty_score_pct"] <= 100).all()


class TestShareOfVoice:

    def test_basic_sov(self, dashboard):
        df = pd.DataFrame({
            "brand": ["DrugA", "DrugB", "DrugC"],
            "detailing_visits": [1200, 800, 400],
        })
        result = dashboard.calculate_therapy_area_share_of_voice(df)
        total_sov = result["share_of_voice_pct"].sum()
        assert abs(total_sov - 100.0) < 0.1

    def test_rank_assigned(self, dashboard):
        df = pd.DataFrame({
            "brand": ["DrugA", "DrugB"],
            "detailing_visits": [700, 300],
        })
        result = dashboard.calculate_therapy_area_share_of_voice(df)
        assert result.iloc[0]["rank"] == 1
        assert result.iloc[1]["rank"] == 2

    def test_empty_raises(self, dashboard):
        with pytest.raises(ValueError, match="DataFrame cannot be empty"):
            dashboard.calculate_therapy_area_share_of_voice(pd.DataFrame())

    def test_zero_visits_handled(self, dashboard):
        df = pd.DataFrame({
            "brand": ["DrugA", "DrugB"],
            "detailing_visits": [0, 0],
        })
        result = dashboard.calculate_therapy_area_share_of_voice(df)
        assert (result["share_of_voice_pct"] == 0.0).all()
