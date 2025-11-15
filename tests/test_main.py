"""Unit tests for DiseaseAreaDashboard."""
import pytest
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, "/Users/johndoe/projects/disease-area-dashboard")
from src.main import DiseaseAreaDashboard


@pytest.fixture
def sales_df():
    periods = ["2025-01", "2025-02", "2025-03", "2025-04"] * 3
    brands = ["BrandA"] * 4 + ["BrandB"] * 4 + ["BrandC"] * 4
    trx = [1200, 1250, 1300, 1350, 800, 820, 850, 880, 400, 390, 410, 420]
    nrx = [300, 310, 320, 330, 200, 205, 210, 215, 100, 98, 102, 105]
    sales = [t * 45.0 for t in trx]
    return pd.DataFrame({"period": periods, "brand": brands, "trx": trx, "nrx": nrx, "sales_usd": sales})


@pytest.fixture
def dash():
    return DiseaseAreaDashboard(config={"therapy_area": "Cardiovascular"})


class TestValidation:
    def test_empty_raises(self, dash):
        with pytest.raises(ValueError, match="empty"):
            dash.validate(pd.DataFrame())

    def test_missing_columns_raises(self, dash):
        df = pd.DataFrame({"period": ["2025-01"], "sales_usd": [1000]})
        with pytest.raises(ValueError, match="Missing required columns"):
            dash.validate(df)

    def test_valid_passes(self, dash, sales_df):
        assert dash.validate(sales_df) is True


class TestMarketShare:
    def test_returns_dataframe(self, dash, sales_df):
        result = dash.market_share_analysis(sales_df)
        assert isinstance(result, pd.DataFrame)

    def test_share_sums_to_100_per_period(self, dash, sales_df):
        result = dash.market_share_analysis(sales_df)
        for period, grp in result.groupby("period"):
            total = grp["market_share_pct"].sum()
            assert abs(total - 100.0) < 0.5, f"Period {period}: sum={total}"

    def test_brand_a_has_highest_share(self, dash, sales_df):
        result = dash.market_share_analysis(sales_df)
        avg_share = result.groupby("brand")["market_share_pct"].mean()
        assert avg_share.idxmax() == "BrandA"

    def test_invalid_metric_raises(self, dash, sales_df):
        with pytest.raises(ValueError):
            dash.market_share_analysis(sales_df, metric="nonexistent")

    def test_sales_metric_works(self, dash, sales_df):
        result = dash.market_share_analysis(sales_df, metric="sales_usd")
        assert "sales_usd_value" in result.columns

    def test_rank_column_present(self, dash, sales_df):
        result = dash.market_share_analysis(sales_df)
        assert "rank" in result.columns


class TestMATTrend:
    def test_returns_dataframe(self, dash, sales_df):
        result = dash.mat_trend(sales_df)
        assert isinstance(result, pd.DataFrame)

    def test_mat_columns(self, dash, sales_df):
        result = dash.mat_trend(sales_df)
        assert "mat_value" in result.columns
        assert "brand" in result.columns
        assert "period" in result.columns

    def test_mat_value_positive(self, dash, sales_df):
        result = dash.mat_trend(sales_df)
        assert (result["mat_value"] > 0).all()

    def test_missing_period_raises(self, dash):
        df = pd.DataFrame({"brand": ["A", "B"], "trx": [100, 200]})
        with pytest.raises(ValueError, match="period"):
            dash.mat_trend(df)


class TestBrandSegmentation:
    def test_returns_dataframe(self, dash, sales_df):
        result = dash.brand_segmentation(sales_df)
        assert isinstance(result, pd.DataFrame)

    def test_all_brands_present(self, dash, sales_df):
        result = dash.brand_segmentation(sales_df)
        assert set(result["brand"]) == {"BrandA", "BrandB", "BrandC"}

    def test_segment_column_present(self, dash, sales_df):
        result = dash.brand_segmentation(sales_df)
        assert "segment" in result.columns

    def test_valid_segments(self, dash, sales_df):
        result = dash.brand_segmentation(sales_df)
        valid_segments = {"Leader", "Challenger", "Niche", "Declining"}
        assert set(result["segment"]).issubset(valid_segments)

    def test_brand_a_is_leader_or_niche(self, dash, sales_df):
        result = dash.brand_segmentation(sales_df)
        brand_a_seg = result[result["brand"] == "BrandA"]["segment"].values[0]
        assert brand_a_seg in {"Leader", "Challenger", "Niche", "Declining"}

    def test_nrx_metric_works(self, dash, sales_df):
        result = dash.brand_segmentation(sales_df, metric="nrx")
        assert "segment" in result.columns


class TestExportReport:
    def test_export_creates_file(self, dash, sales_df, tmp_path):
        out = str(tmp_path / "report.csv")
        path = dash.export_report(sales_df, output_path=out)
        assert Path(path).exists()

    def test_export_has_segment_column(self, dash, sales_df, tmp_path):
        out = str(tmp_path / "report.csv")
        dash.export_report(sales_df, output_path=out)
        result = pd.read_csv(out)
        assert "segment" in result.columns
