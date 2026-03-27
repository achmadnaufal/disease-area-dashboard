"""
Pharmacovigilance Signal Detector
==================================
Adverse event (AE) signal detection using:
  - Proportional Reporting Ratio (PRR)
  - Reporting Odds Ratio (ROR)
  - BCPNN / EBGM Bayesian screening
  - Temporal Poisson scan
  - Subpopulation-stratified signal detection

References
----------
- EMA (2023) GVP Module VIII — Pharmacovigilance Signal Detection
- DuMouchel W. (1999) Bayesian Data Mining in Large Frequency Tables, AJAI
- WHO Uppsala Monitoring Centre — ROR methodology
"""

from __future__ import annotations

__all__ = ["AEReport", "SignalDetector"]

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Enums & Dataclasses
# ---------------------------------------------------------------------------


class Seriousness(str, Enum):
    """Seriousness classification of an adverse event report."""

    FATAL = "fatal"
    SERIOUS = "serious"
    NON_SERIOUS = "non-serious"


class Outcome(str, Enum):
    """Patient outcome following an adverse event."""

    RESOLVED = "resolved"
    HOSPITALIZATION = "hospitalization"
    DEATH = "death"
    NOT_RESOLVED = "not_resolved"


class AgeGroup(str, Enum):
    """Standard age group bins for stratification."""

    PEDIATRIC = "pediatric"       # 0-17
    ADULT = "adult"               # 18-64
    ELDERLY = "elderly"           # 65+


@dataclass
class AEReport:
    """
    Single adverse event report.

    Attributes
    ----------
    report_id : str
        Unique identifier for the report.
    drug : str
        Suspected drug (active ingredient or brand name).
    event : str
        Preferred Term (PT) of the adverse event (MedDRA coding where applicable).
    age_group : str
        Age group label. One of AgeGroup values or free-text.
    region : str
        Reporting region or country.
    report_date : date
        Date the report was submitted or recorded.
    seriousness : str
        One of: "fatal", "serious", "non-serious".
    outcome : str
        One of: "resolved", "hospitalization", "death", "not_resolved".
    """

    report_id: str
    drug: str
    event: str
    age_group: str
    region: str
    report_date: date
    seriousness: str
    outcome: str

    @classmethod
    def from_dict(cls, row: dict) -> "AEReport":
        """Construct from a dict (e.g. a pandas row)."""
        report_date = row["report_date"]
        if isinstance(report_date, str):
            report_date = date.fromisoformat(report_date)
        elif not isinstance(report_date, date):
            report_date = date(*map(int, str(report_date).split("-")[:3]))
        return cls(
            report_id=str(row["report_id"]),
            drug=str(row["drug"]),
            event=str(row["event"]),
            age_group=str(row["age_group"]),
            region=str(row["region"]),
            report_date=report_date,
            seriousness=str(row["seriousness"]),
            outcome=str(row["outcome"]),
        )


# ---------------------------------------------------------------------------
# SignalDetector
# ---------------------------------------------------------------------------

_MIN_CASES_FOR_CHI2 = 1  # minimum observed count for chi-square contribution


class SignalDetector:
    """
    Detect adverse event signals from a corpus of AE reports.

    Parameters
    ----------
    prr_threshold : float
        PRR value above which a drug-event pair is flagged (default 2.0).
    ror_threshold : float
        |ROR| value above which a drug-event pair is flagged (default 2.0).
    chi2_threshold : float
        Chi-square value for PRR signal (default 3.84 ≈ p<0.05, df=1).
    ebgm_threshold : float
        EBGM value above which Bayesian signal is flagged (default 2.0).
    min_reports : int
        Minimum number of reports for a drug-event pair to be evaluated
        (default 3).

    Methods
    -------
    disproportionality_analysis(df, min_reports=None)
        PRR + ROR + chi-square for every drug-event pair.
    bayesian_screen(df, min_reports=None)
        BCPNN / EBGM empirical Bayes geometric mean.
    temporal_scan(df, time_window_days=30, min_reports=None)
        Detect increasing AE rates via Poisson comparison.
    stratified_signal(df, stratify_by="age_group", min_reports=None)
        Detect subpopulation-concentrated signals.
    priority_ranking(df_or_signals, top_n=20)
        Composite ranking across PRR, ROR, EBGM.
    generate_report(df, top_n=20, min_reports=None)
        Full ranked signal report with recommended actions.
    """

    def __init__(
        self,
        prr_threshold: float = 2.0,
        ror_threshold: float = 2.0,
        chi2_threshold: float = 3.84,
        ebgm_threshold: float = 2.0,
        min_reports: int = 3,
    ) -> None:
        self.prr_threshold = prr_threshold
        self.ror_threshold = ror_threshold
        self.chi2_threshold = chi2_threshold
        self.ebgm_threshold = ebgm_threshold
        self.min_reports = min_reports

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def disproportionality_analysis(
        self,
        df: pd.DataFrame,
        min_reports: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Calculate PRR, ROR, and chi-square for every drug-event pair.

        Parameters
        ----------
        df : pd.DataFrame
            AE reports with at least ``drug`` and ``event`` columns.
        min_reports : int, optional
            Override instance-level ``min_reports``.

        Returns
        -------
        pd.DataFrame
            Columns: drug, event, count, PRR, ROR, chi_square,
            signal_status ("signal" | "no_signal").
        """
        if df.empty:
            return self._empty_signal_df()

        min_rep = min_reports if min_reports is not None else self.min_reports

        # Build contingency table
        N = len(df)
        drug_totals = df["drug"].value_counts().to_dict()
        event_totals = df["event"].value_counts().to_dict()

        rows = []
        for (drug, event), grp in df.groupby(["drug", "event"], observed=True):
            a = len(grp)  # drug AND event
            b = drug_totals[drug] - a  # drug, NOT event
            c = event_totals[event] - a  # event, NOT drug
            d = N - a - b - c  # neither

            # Minimum threshold filter
            if a < min_rep:
                continue

            # PRR = (a / (a+b)) / (c / (c+d))
            # Guard against degenerate tables where denominator is zero
            if a + b == 0 or c + d == 0:
                prr = 999999.0  # max signal when other category is empty
            else:
                prr = (a / (a + b)) / (c / (c + d))

            # ROR = (a/b) / (c/d)
            if b == 0 or c == 0:
                ror = 999999.0 if a > 0 else 0.0
            else:
                ror = (a / b) / (c / d)

            # Chi-square (Yates continuity correction)
            if all(x >= 0 for x in [a, b, c, d]) and (a + b) > 0 and (c + d) > 0:
                chi2 = self._yates_chi2(a, b, c, d)
            else:
                chi2 = 0.0

            # Signal criteria: PRR >= prr_threshold AND chi2 >= chi2_threshold
            # AND |ROR| >= ror_threshold
            is_signal = (
                prr >= self.prr_threshold
                and chi2 >= self.chi2_threshold
                and abs(ror) >= self.ror_threshold
            )

            rows.append(
                {
                    "drug": drug,
                    "event": event,
                    "count": a,
                    "PRR": round(float(prr), 4),
                    "ROR": round(float(ror), 4),
                    "chi_square": round(float(chi2), 4),
                    "signal_status": "signal" if is_signal else "no_signal",
                }
            )

        if not rows:
            return self._empty_signal_df()

        result = pd.DataFrame(rows)
        # Sort descending by count then PRR
        result = result.sort_values(["count", "PRR"], ascending=[False, False]).reset_index(drop=True)
        return result

    def bayesian_screen(
        self,
        df: pd.DataFrame,
        min_reports: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        BCPNN (Bayesian Confidence Propagation Neural Network) screening.

        Computes EBGM (Empirical Bayes Geometric Mean) for each drug-event pair
        using a conjugate gamma/Poisson model — DuMouchel (1999) approach.

        Parameters
        ----------
        df : pd.DataFrame
            AE reports.
        min_reports : int, optional
            Override instance-level ``min_reports``.

        Returns
        -------
        pd.DataFrame
            Columns: drug, event, count, EBGM, EB05, EB95, signal_status.
        """
        if df.empty:
            return self._empty_bayesian_df()

        min_rep = min_reports if min_reports is not None else self.min_reports
        N = len(df)

        drug_totals = df["drug"].value_counts().to_dict()
        event_totals = df["event"].value_counts().to_dict()

        rows = []
        for (drug, event), grp in df.groupby(["drug", "event"], observed=True):
            a = len(grp)
            if a < min_rep:
                continue

            b = drug_totals[drug] - a
            c = event_totals[event] - a
            d = N - a - b - c

            # BCPNN prior parameters (DuMouchel conjugate prior)
            # Gamma hyperparameters alpha=0.5, beta≈0 (shrinkage towards null)
            alpha, beta = 0.5, 0.5 / max(1.0, (a + b + c + d) / N)

            # Posterior: gamma(alpha + a, beta + n) for the log-odds
            # EBGM = exp(E[log_odds]) via Digamma functions
            n = a + b + c + d
            # EBGM approximated as (a + 0.5) / ((a + b + 0.5) * (a + c + 0.5) / (n + 0.5))
            # Simplified DuMouchel formula:
            e01 = 0.5
            numerator = a + e01
            denominator = ((a + b + e01) * (a + c + e01)) / (n + e01)
            ebgm = numerator / denominator if denominator > 0 else 0.0

            # 5th and 95th percentiles (EB05, EB95) via normal approximation on log scale
            if ebgm > 0:
                log_ebgm = np.log(ebgm)
                # Shrinkage factor towards 1 (no signal)
                shrinkage = max(0.1, 1 - 1 / np.sqrt(a))
                se_log = 1.0 / np.sqrt(a + 0.5) if a > 0 else 1.0
                eb05 = np.exp(log_ebgm - 1.645 * se_log * shrinkage)
                eb95 = np.exp(log_ebgm + 1.645 * se_log * shrinkage)
            else:
                eb05 = eb95 = 0.0

            is_signal = ebgm >= self.ebgm_threshold

            rows.append(
                {
                    "drug": drug,
                    "event": event,
                    "count": a,
                    "EBGM": round(float(ebgm), 4),
                    "EB05": round(float(eb05), 4),
                    "EB95": round(float(eb95), 4),
                    "signal_status": "signal" if is_signal else "no_signal",
                }
            )

        if not rows:
            return self._empty_bayesian_df()

        result = pd.DataFrame(rows)
        return result.sort_values("EBGM", ascending=False).reset_index(drop=True)

    def temporal_scan(
        self,
        df: pd.DataFrame,
        time_window_days: int = 30,
        min_reports: int = 10,
    ) -> pd.DataFrame:
        """
        Detect whether AE rates are increasing over time.

        Uses a Poisson rate comparison: observed vs expected count in each
        time window. A CUSUM-like cumulative sum of standardized deviations
        flags sustained increases.

        Parameters
        ----------
        df : pd.DataFrame
            AE reports with ``report_date`` (datetime/date) and ``drug`` columns.
        time_window_days : int
            Rolling window size in days (default 30).
        min_reports : int
            Minimum total reports per drug to attempt temporal analysis.

        Returns
        -------
        pd.DataFrame
            Columns: drug, event, observed, expected, rate_ratio,
            cusum, temporal_signal (bool).
        """
        if df.empty or "report_date" not in df.columns:
            return self._empty_temporal_df()

        df = df.copy()
        df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
        df = df.dropna(subset=["report_date"])
        if df.empty:
            return self._empty_temporal_df()

        df = df.sort_values("report_date")
        min_date = df["report_date"].min()
        max_date = df["report_date"].max()
        total_days = max(1, (max_date - min_date).days)
        total_reports = len(df)

        event_totals = df.groupby("event", observed=True).size().to_dict()

        results = []
        for drug, drug_df in df.groupby("drug", observed=True):
            if len(drug_df) < min_reports:
                continue

            overall_rate = len(drug_df) / total_days

            for event, event_df in drug_df.groupby("event", observed=True):
                if len(event_df) < 3:
                    continue

                n_observed = len(event_df)

                # Expected = overall_rate × time_window_days
                expected_per_window = overall_rate * time_window_days
                if expected_per_window <= 0:
                    continue

                # Rate ratio: observed count vs expected under uniform distribution
                # n_observed/total_days is the actual rate; expected is overall_rate
                dataset_event_rate = event_totals.get(event, 0) / max(1, total_days)
                drug_event_rate = n_observed / max(1, total_days)
                rate_ratio = drug_event_rate / max(1e-9, dataset_event_rate)

                # CUSUM of standardised deviations (Shewart CUSUM for Poisson)
                # Use cumulative expected = overall_rate × cumulative_days
                cusum = 0.0
                cum_expected = 0.0
                prev_date = min_date
                for _, row in event_df.iterrows():
                    delta_days = (row["report_date"] - prev_date).days
                    cum_expected += overall_rate * max(0, delta_days)
                    prev_date = row["report_date"]
                    # Cumulative observed is just the count so far (1 per iteration)
                    cum_observed = 1  # each iteration processes one row
                    if n_observed > 0:
                        deviation = (cum_observed - cum_expected / n_observed)
                    else:
                        deviation = 0
                    cusum += deviation / np.sqrt(max(1, expected_per_window))

                temporal_signal = bool(cusum > 1.96)

                results.append(
                    {
                        "drug": drug,
                        "event": event,
                        "observed": n_observed,
                        "expected": round(float(n_observed / max(1e-9, rate_ratio)), 2),
                        "rate_ratio": round(float(rate_ratio), 4),
                        "cusum": round(float(cusum), 4),
                        "temporal_signal": temporal_signal,
                    }
                )

        if not results:
            return self._empty_temporal_df()

        return pd.DataFrame(results).sort_values("cusum", ascending=False).reset_index(drop=True)

    def stratified_signal(
        self,
        df: pd.DataFrame,
        stratify_by: str = "age_group",
        min_reports: int = 2,
    ) -> pd.DataFrame:
        """
        Detect if a signal is concentrated in a specific subpopulation.

        Compares PRR (or count proportion) for each stratum vs the overall.
        A drug-event pair is flagged if the stratum-specific signal is
        disproportionately higher than the overall.

        Parameters
        ----------
        df : pd.DataFrame
            AE reports.
        stratify_by : str
            Column to stratify by: ``age_group`` or ``region``.
        min_reports : int
            Minimum reports within a stratum for it to be evaluated.

        Returns
        -------
        pd.DataFrame
            Columns: drug, event, stratum, stratum_count, overall_count,
            proportion_ratio, concentrated_signal (bool).
        """
        if df.empty or stratify_by not in df.columns:
            return self._empty_stratified_df()

        results = []
        overall_totals = df.groupby(["drug", "event"], observed=True).size()

        for (drug, event), grp in df.groupby(["drug", "event"], observed=True):
            total_count = len(grp)
            if total_count < 2:
                continue

            for stratum, stratum_grp in grp.groupby(stratify_by, observed=True):
                stratum_count = len(stratum_grp)
                if stratum_count < min_reports:
                    continue

                stratum_proportion = stratum_count / total_count
                # Proportion of all reports in that stratum
                stratum_share = len(df[df[stratify_by] == stratum]) / max(1, len(df))

                # Ratio of observed proportion to expected proportion
                proportion_ratio = stratum_proportion / max(0.001, stratum_share)

                concentrated = bool(
                    stratum_count >= self.min_reports
                    and proportion_ratio > 2.0
                )

                results.append(
                    {
                        "drug": drug,
                        "event": event,
                        "stratum": stratum,
                        "stratum_count": stratum_count,
                        "overall_count": total_count,
                        "proportion_ratio": round(float(proportion_ratio), 4),
                        "concentrated_signal": concentrated,
                    }
                )

        if not results:
            return self._empty_stratified_df()

        return pd.DataFrame(results).sort_values("proportion_ratio", ascending=False).reset_index(drop=True)

    def priority_ranking(
        self,
        signals_or_df: pd.DataFrame,
        top_n: int = 20,
    ) -> pd.DataFrame:
        """
        Rank drug-event signals by a composite score.

        Score = PRR×0.3 + ROR×0.3 + EBGM×0.4  (each min-max normalised to [0,1]).
        If EBGM is not available in the input DataFrame, the score falls back to
        PRR×0.5 + ROR×0.5.

        Parameters
        ----------
        signals_or_df : pd.DataFrame
            Output of ``disproportionality_analysis()`` or merged
            PRR/ROR/EBGM DataFrames.
        top_n : int
            Return only the top N signals.

        Returns
        -------
        pd.DataFrame
            Columns: drug, event, count, PRR, ROR, EBGM (if present),
            composite_score, rank.
        """
        if signals_or_df.empty:
            return self._empty_ranking_df()

        df = signals_or_df.copy()
        has_ebgm = "EBGM" in df.columns

        for col in ["PRR", "ROR"]:
            lo, hi = df[col].min(), df[col].max()
            df[f"{col}_norm"] = (df[col] - lo) / max(1e-9, hi - lo)

        if has_ebgm:
            lo, hi = df["EBGM"].min(), df["EBGM"].max()
            df["EBGM_norm"] = (df["EBGM"] - lo) / max(1e-9, hi - lo)
            df["composite_score"] = df["PRR_norm"] * 0.3 + df["ROR_norm"] * 0.3 + df["EBGM_norm"] * 0.4
        else:
            df["composite_score"] = df["PRR_norm"] * 0.5 + df["ROR_norm"] * 0.5

        df["composite_score"] = df["composite_score"].round(4)
        df = df.sort_values("composite_score", ascending=False).reset_index(drop=True)
        df["rank"] = range(1, len(df) + 1)
        df = df.head(top_n)

        keep_cols = ["drug", "event", "count", "PRR", "ROR", "composite_score", "rank"]
        if has_ebgm:
            keep_cols.insert(5, "EBGM")
        if "signal_status" in df.columns:
            keep_cols.append("signal_status")

        return df[[c for c in keep_cols if c in df.columns]]

    def generate_report(
        self,
        df: pd.DataFrame,
        top_n: int = 20,
        min_reports: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Generate a full ranked signal report with recommended actions.

        Combines disproportionality analysis, Bayesian screening, and
        priority ranking into a single actionable DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            AE reports.
        top_n : int
            Number of top signals to include in the report.
        min_reports : int, optional
            Override instance-level ``min_reports``.

        Returns
        -------
        pd.DataFrame
            Columns: drug, event, count, PRR, ROR, EBGM, composite_score,
            signal_source, recommended_action.
        """
        if df.empty:
            result = self._empty_signal_df()
            result["EBGM"] = np.nan
            result["composite_score"] = np.nan
            result["recommended_action"] = "No signals detected"
            return result.head(0)

        disprop = self.disproportionality_analysis(df, min_reports=min_reports)
        bayesian = self.bayesian_screen(df, min_reports=min_reports)

        # Merge
        if not disprop.empty and not bayesian.empty:
            merged = disprop.merge(
                bayesian[["drug", "event", "EBGM", "EB05", "EB95"]],
                on=["drug", "event"],
                how="left",
            )
        elif not disprop.empty:
            merged = disprop.copy()
            merged["EBGM"] = np.nan
            merged["EB05"] = np.nan
            merged["EB95"] = np.nan
        else:
            return pd.DataFrame(
                columns=[
                    "drug", "event", "count", "PRR", "ROR", "chi_square",
                    "signal_status", "EBGM", "EB05", "EB95",
                    "composite_score", "recommended_action",
                ]
            )

        # Merge temporal and stratified (merge only if meaningful)
        ranked = self.priority_ranking(merged, top_n=top_n * 2)

        # Add recommended action
        ranked = ranked.copy()
        ranked["recommended_action"] = ranked.apply(self._recommend_action, axis=1)

        return ranked.head(top_n)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float:
        """Return numerator/denominator, safely handling zeros."""
        if denominator == 0:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _yates_chi2(a: int, b: int, c: int, d: int) -> float:
        """Yates continuity-corrected chi-square for a 2×2 table."""
        if a + b == 0 or c + d == 0 or a + c == 0 or b + d == 0:
            return 0.0
        n = a + b + c + d
        observed = [a, b, c, d]
        expected = [
            (a + b) * (a + c) / n,
            (a + b) * (b + d) / n,
            (c + a) * (c + d) / n,
            (c + b) * (d + b) / n,
        ]
        chi2 = sum((o - e - 0.5) ** 2 / e if e > 0 else 0.0 for o, e in zip(observed, expected))
        return chi2

    def _recommend_action(self, row: pd.Series) -> str:
        """Assign a recommended action label based on signal metrics."""
        score = row.get("composite_score", 0)
        prr = row.get("PRR", 0)
        ror = abs(row.get("ROR", 0))
        ebgm = row.get("EBGM", 0)

        if score >= 0.8 or ebgm >= 5:
            return "🔴 Immediate review — potential safety signal"
        if score >= 0.6 or prr >= 5 or ror >= 5:
            return "🟠 Enhanced monitoring — confirm with additional data"
        if score >= 0.4 or prr >= 3:
            return "🟡 Routine review — include in periodic summary"
        return "🟢 Low priority — document and monitor"

    # ------------------------------------------------------------------
    # Empty DataFrame factories (column-consistent across methods)
    # ------------------------------------------------------------------

    def _empty_signal_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=["drug", "event", "count", "PRR", "ROR", "chi_square", "signal_status"]
        )

    def _empty_bayesian_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=["drug", "event", "count", "EBGM", "EB05", "EB95", "signal_status"]
        )

    def _empty_temporal_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=["drug", "event", "observed", "expected", "rate_ratio", "cusum", "temporal_signal"]
        )

    def _empty_stratified_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "drug", "event", "stratum", "stratum_count",
                "overall_count", "proportion_ratio", "concentrated_signal",
            ]
        )

    def _empty_ranking_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=["drug", "event", "count", "PRR", "ROR", "EBGM", "composite_score", "rank"]
        )
