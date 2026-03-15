"""
Disease area market landscape dashboard for pharma business intelligence.

Provides tools for analyzing drug market share, brand performance,
competitor tracking, and therapy area KPIs using sales data from
pharmaceutical market research sources (e.g. IQVIA, Veeva CRM).

Author: github.com/achmadnaufal
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List


class DiseaseAreaDashboard:
    """
    Disease area market intelligence dashboard.

    Analyzes pharmaceutical sales data to compute brand market share,
    MAT (Moving Annual Total) trends, TRx/NRx metrics, and competitive
    positioning within a therapy area.

    Args:
        config: Optional dict with keys:
            - therapy_area: Name for labeling output (e.g. "Oncology")
            - rolling_months: Months for rolling calculations (default 3)

    Example:
        >>> dash = DiseaseAreaDashboard(config={"therapy_area": "Cardiovascular"})
        >>> df = dash.load_data("data/sales_data.csv")
        >>> share = dash.market_share_analysis(df)
        >>> print(share)
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.therapy_area = self.config.get("therapy_area", "Unknown")
        self.rolling_months = self.config.get("rolling_months", 3)

    def load_data(self, filepath: str) -> pd.DataFrame:
        """
        Load pharma sales data from CSV or Excel.

        Args:
            filepath: Path to file. Expected columns: period, brand,
                      trx (total prescriptions), nrx (new Rx), sales_usd.

        Returns:
            DataFrame with sales records.

        Raises:
            FileNotFoundError: If file does not exist.
        """
        p = Path(filepath)
        if not p.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")
        if p.suffix in (".xlsx", ".xls"):
            return pd.read_excel(filepath)
        return pd.read_csv(filepath)

    def validate(self, df: pd.DataFrame) -> bool:
        """
        Validate sales data structure.

        Args:
            df: DataFrame to validate.

        Returns:
            True if valid.

        Raises:
            ValueError: If empty or missing required columns.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty")
        df_cols = [c.lower().strip().replace(" ", "_") for c in df.columns]
        required = ["brand", "trx"]
        missing = [c for c in required if c not in df_cols]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return True

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names and fill missing values."""
        df = df.copy()
        df.dropna(how="all", inplace=True)
        df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
        num_cols = df.select_dtypes(include="number").columns
        for col in num_cols:
            if df[col].isnull().any():
                df[col].fillna(0, inplace=True)
        return df

    def market_share_analysis(
        self, df: pd.DataFrame, metric: str = "trx"
    ) -> pd.DataFrame:
        """
        Calculate brand market share by period and overall.

        Market share = brand metric / total market metric per period.

        Args:
            df: Sales DataFrame with brand, period, and metric columns.
            metric: Column to use for share calculation (trx, nrx, or sales_usd).

        Returns:
            DataFrame with columns: brand, period, metric_value,
            market_share_pct, rank.

        Raises:
            ValueError: If metric column not found.
        """
        df = self.preprocess(df)
        if metric not in df.columns:
            available = [c for c in df.columns if c in ["trx", "nrx", "sales_usd"]]
            raise ValueError(f"Metric '{metric}' not found. Available: {available}")

        period_col = "period" if "period" in df.columns else None
        group_cols = ["brand"] + ([period_col] if period_col else [])

        agg = df.groupby(group_cols)[metric].sum().reset_index()

        if period_col:
            agg["market_total"] = agg.groupby(period_col)[metric].transform("sum")
        else:
            agg["market_total"] = agg[metric].sum()

        agg["market_share_pct"] = (agg[metric] / agg["market_total"] * 100).round(2)
        agg = agg.rename(columns={metric: f"{metric}_value"})
        agg["rank"] = agg.groupby(period_col if period_col else [])[ 
            "market_share_pct"
        ].rank(ascending=False, method="min").astype(int) if period_col else agg["market_share_pct"].rank(ascending=False, method="min").astype(int)
        agg.drop(columns=["market_total"], inplace=True)
        return agg.sort_values(["period", "market_share_pct"] if period_col else ["market_share_pct"], ascending=[True, False] if period_col else False).reset_index(drop=True)

    def mat_trend(self, df: pd.DataFrame, metric: str = "trx") -> pd.DataFrame:
        """
        Calculate Moving Annual Total (MAT) for each brand.

        MAT is the sum of the last 12 months' data, rolled forward each month.
        Used in pharma to smooth seasonality in prescription tracking.

        Args:
            df: Sales DataFrame with period, brand, and metric columns.
                period must be sortable (e.g. "2025-01" format).
            metric: Column for MAT calculation.

        Returns:
            DataFrame with brand, period, mat_value (12-month rolling sum),
            and mat_growth_pct (year-over-year change).
        """
        df = self.preprocess(df)
        if "period" not in df.columns:
            raise ValueError("Column 'period' required for MAT trend calculation")
        if metric not in df.columns:
            raise ValueError(f"Metric column '{metric}' not found")

        df = df.sort_values("period")
        results = []
        for brand, grp in df.groupby("brand"):
            grp = grp.set_index("period")[metric].sort_index()
            mat = grp.rolling(window=12, min_periods=1).sum()
            mat_growth = mat.pct_change(periods=12) * 100
            for period, val in mat.items():
                results.append({
                    "brand": brand,
                    "period": period,
                    "mat_value": round(val, 1),
                    "mat_growth_pct": round(mat_growth.get(period, np.nan), 2),
                })
        return pd.DataFrame(results)

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run descriptive analysis and return summary metrics."""
        df = self.preprocess(df)
        result = {
            "total_records": len(df),
            "columns": list(df.columns),
            "missing_pct": (df.isnull().sum() / len(df) * 100).round(1).to_dict(),
        }
        numeric_df = df.select_dtypes(include="number")
        if not numeric_df.empty:
            result["summary_stats"] = numeric_df.describe().round(3).to_dict()
            result["totals"] = numeric_df.sum().round(2).to_dict()
            result["means"] = numeric_df.mean().round(3).to_dict()
        return result

    def run(self, filepath: str) -> Dict[str, Any]:
        """Full pipeline: load → validate → analyze."""
        df = self.load_data(filepath)
        self.validate(df)
        return self.analyze(df)

    def to_dataframe(self, result: Dict) -> pd.DataFrame:
        """Convert result dict to flat DataFrame for export."""
        rows = []
        for k, v in result.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    rows.append({"metric": f"{k}.{kk}", "value": vv})
            else:
                rows.append({"metric": k, "value": v})
        return pd.DataFrame(rows)


    def brand_segmentation(self, df: pd.DataFrame, metric: str = "trx") -> pd.DataFrame:
        """
        Segment brands into performance tiers based on share and growth trend.

        Tiers:
            - Leader: top share, positive or stable growth
            - Challenger: medium share, gaining growth
            - Niche: low share, stable or declining
            - Declining: any share, consistently negative growth

        Args:
            df: Sales DataFrame with brand, period, and metric columns.
            metric: Column to use for segmentation (trx, nrx, or sales_usd).

        Returns:
            DataFrame with brand, avg_share_pct, share_trend, segment label.
        """
        share_df = self.market_share_analysis(df, metric=metric)
        avg_share = share_df.groupby("brand")["market_share_pct"].mean().reset_index()
        avg_share.columns = ["brand", "avg_share_pct"]

        periods = sorted(share_df["period"].unique()) if "period" in share_df.columns else []
        trend_rows = []
        for brand in avg_share["brand"]:
            brand_data = share_df[share_df["brand"] == brand].sort_values("period")
            if len(brand_data) >= 2:
                x = np.arange(len(brand_data))
                y = brand_data["market_share_pct"].values
                slope = float(np.polyfit(x, y, 1)[0])
            else:
                slope = 0.0
            trend_rows.append({"brand": brand, "share_trend_slope": round(slope, 4)})

        trend_df = pd.DataFrame(trend_rows)
        result = avg_share.merge(trend_df, on="brand")

        median_share = result["avg_share_pct"].median()

        def assign_segment(row: pd.Series) -> str:
            """Assign segment label based on share magnitude and trend direction."""
            share = row["avg_share_pct"]
            slope = row["share_trend_slope"]
            if slope < -0.5:
                return "Declining"
            if share >= median_share and slope >= 0:
                return "Leader"
            if share < median_share and slope > 0.2:
                return "Challenger"
            return "Niche"

        result["segment"] = result.apply(assign_segment, axis=1)
        return result.sort_values("avg_share_pct", ascending=False).reset_index(drop=True)

    def track_adverse_events(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Track adverse events and safety signals by brand for compliance monitoring.
        
        Assumes df has columns: brand, adverse_events (count), serious_adverse_events (count).
        Identifies brands with elevated adverse event rates for pharmacovigilance review.
        
        Args:
            df: DataFrame with brand adverse event data.
            
        Returns:
            Dictionary with:
            - total_adverse_events: Total AE count across therapy area
            - ae_per_brand: AE counts and rates per brand
            - high_risk_brands: Brands exceeding 95th percentile AE rate
            - serious_ae_rate: Serious AE as % of total AE
            
        Example:
            >>> df = pd.DataFrame({...brands and AE data...})
            >>> safety = dashboard.track_adverse_events(df)
            >>> print(f"High-risk brands: {safety['high_risk_brands']}")
        """
        if df.empty:
            return {}
        
        # Ensure required columns exist
        if "adverse_events" not in df.columns:
            return {"error": "adverse_events column required"}
        
        total_ae = df["adverse_events"].sum()
        serious_ae = df.get("serious_adverse_events", pd.Series(0)).sum()
        serious_ae_rate = (serious_ae / total_ae * 100) if total_ae > 0 else 0
        
        # Calculate AE rate per brand
        ae_by_brand = df.groupby("brand").agg({
            "adverse_events": "sum",
            "serious_adverse_events": lambda x: x.sum() if "serious_adverse_events" in df.columns else 0,
        }).reset_index()
        
        ae_by_brand["ae_rate"] = ae_by_brand["adverse_events"] / ae_by_brand["adverse_events"].sum() * 100
        
        # Identify high-risk brands (>95th percentile)
        ae_threshold = ae_by_brand["ae_rate"].quantile(0.95)
        high_risk = ae_by_brand[ae_by_brand["ae_rate"] > ae_threshold]["brand"].tolist()
        
        return {
            "total_adverse_events": int(total_ae),
            "serious_adverse_event_rate": round(serious_ae_rate, 1),
            "ae_per_brand": ae_by_brand.to_dict("records"),
            "high_risk_brands": high_risk,
            "pharmacovigilance_review_required": len(high_risk) > 0,
        }

    def export_report(self, df: pd.DataFrame, output_path: str = "report.csv") -> str:
        """
        Run full analysis and export summary report to CSV.

        Args:
            df: Sales DataFrame.
            output_path: Destination file path.

        Returns:
            Absolute path of written file.
        """
        share = self.market_share_analysis(df)
        segments = self.brand_segmentation(df)
        combined = share.merge(
            segments[["brand", "avg_share_pct", "segment"]], on="brand", how="left"
        )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(out, index=False)
        return str(out.resolve())

    def segment_prescribers(
        self,
        df: pd.DataFrame,
        prescriber_col: str = "prescriber_id",
        volume_col: str = "units",
        brand_col: str = "brand",
    ) -> pd.DataFrame:
        """
        Segment prescribers by prescribing behavior using RFM-style analysis.

        Classifies healthcare professionals (HCPs) into segments based on
        total prescribing volume and brand loyalty score. Used to prioritize
        medical rep field activities.

        Args:
            df: DataFrame with prescriber transactions
            prescriber_col: Column name for prescriber identifier
            volume_col: Column name for prescription volume/units
            brand_col: Column name for brand/drug name

        Returns:
            DataFrame with prescriber_id, total_units, brand_count,
            top_brand, loyalty_score, and hcp_segment

        Raises:
            ValueError: If required columns are missing or DataFrame is empty

        Example:
            >>> df = pd.DataFrame({
            ...     "prescriber_id": ["HCP-1", "HCP-1", "HCP-2"],
            ...     "brand": ["DrugA", "DrugA", "DrugB"],
            ...     "units": [50, 30, 20],
            ... })
            >>> segments = dashboard.segment_prescribers(df)
            >>> print(segments[["prescriber_id", "hcp_segment"]])
        """
        if df.empty:
            raise ValueError("DataFrame cannot be empty")

        missing = [c for c in (prescriber_col, volume_col, brand_col) if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df = df.copy()
        df[volume_col] = pd.to_numeric(df[volume_col], errors="coerce").fillna(0)

        # Aggregate per prescriber
        agg = df.groupby(prescriber_col).agg(
            total_units=(volume_col, "sum"),
            brand_count=(brand_col, "nunique"),
            top_brand=(volume_col, lambda x: df.loc[x.index, brand_col].iloc[x.values.argmax()]),
        ).reset_index()

        # Loyalty score: proportion of prescriptions for top brand
        def loyalty(row):
            prescriber_df = df[df[prescriber_col] == row[prescriber_col]]
            by_brand = prescriber_df.groupby(brand_col)[volume_col].sum()
            if by_brand.sum() == 0:
                return 0.0
            return round(float(by_brand.max() / by_brand.sum() * 100), 1)

        agg["loyalty_score_pct"] = agg.apply(loyalty, axis=1)

        # Volume percentile thresholds
        p75 = agg["total_units"].quantile(0.75)
        p25 = agg["total_units"].quantile(0.25)

        def classify_hcp(row):
            if row["total_units"] >= p75 and row["loyalty_score_pct"] >= 70:
                return "Champion"
            elif row["total_units"] >= p75:
                return "High-Volume"
            elif row["total_units"] >= p25 and row["loyalty_score_pct"] >= 60:
                return "Loyal-Mid"
            elif row["total_units"] < p25:
                return "Low-Activity"
            else:
                return "Opportunity"

        agg["hcp_segment"] = agg.apply(classify_hcp, axis=1)

        return agg.sort_values("total_units", ascending=False).reset_index(drop=True)

    def calculate_therapy_area_share_of_voice(
        self,
        df: pd.DataFrame,
        brand_col: str = "brand",
        detailing_visits_col: str = "detailing_visits",
    ) -> pd.DataFrame:
        """
        Calculate Share of Voice (SoV) for each brand in a therapy area.

        SoV = brand detailing visits / total therapy area visits × 100.
        Used to benchmark promotion intensity vs market share.

        Args:
            df: DataFrame with brand detailing activity data
            brand_col: Column name for brand
            detailing_visits_col: Column name for detailing visit counts

        Returns:
            DataFrame with brand, total_visits, share_of_voice_pct, and rank

        Raises:
            ValueError: If DataFrame is empty or required columns missing

        Example:
            >>> df = pd.DataFrame({
            ...     "brand": ["DrugA", "DrugB", "DrugC"],
            ...     "detailing_visits": [1200, 800, 400],
            ... })
            >>> sov = dashboard.calculate_therapy_area_share_of_voice(df)
            >>> print(sov[["brand", "share_of_voice_pct"]])
        """
        if df.empty:
            raise ValueError("DataFrame cannot be empty")
        missing = [c for c in (brand_col, detailing_visits_col) if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df = df.copy()
        df[detailing_visits_col] = pd.to_numeric(df[detailing_visits_col], errors="coerce").fillna(0)

        brand_totals = df.groupby(brand_col)[detailing_visits_col].sum().reset_index()
        brand_totals.columns = ["brand", "total_visits"]

        total = brand_totals["total_visits"].sum()
        if total == 0:
            brand_totals["share_of_voice_pct"] = 0.0
        else:
            brand_totals["share_of_voice_pct"] = round(
                brand_totals["total_visits"] / total * 100, 1
            )

        brand_totals["rank"] = brand_totals["share_of_voice_pct"].rank(
            method="dense", ascending=False
        ).astype(int)

        return brand_totals.sort_values("rank").reset_index(drop=True)
