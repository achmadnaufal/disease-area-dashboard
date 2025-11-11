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
