"""
KPI Alert Engine for pharmaceutical disease area dashboards.

Monitors key performance indicators against configurable thresholds and
generates structured alerts for brand managers and commercial analytics teams.

Covers:
- Market share alerts (decline vs previous period / benchmark)
- Patient funnel conversion rate alerts
- Script volume alerts (NRx, TRx)
- Persistence/adherence alerts

Severity levels follow standard BI alerting conventions:
    info     — informational; no action required
    warning  — monitor closely; potential emerging issue
    critical — immediate investigation required

Author: github.com/achmadnaufal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums & constants
# ---------------------------------------------------------------------------


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class KPIType(str, Enum):
    MARKET_SHARE = "market_share"
    NRX_VOLUME = "nrx_volume"
    TRX_VOLUME = "trx_volume"
    PERSISTENCE_6M = "persistence_6m"
    PERSISTENCE_12M = "persistence_12m"
    CONVERSION_RATE = "conversion_rate"


# Default thresholds (relative % change from baseline unless noted)
DEFAULT_THRESHOLDS: Dict[KPIType, Dict[str, float]] = {
    KPIType.MARKET_SHARE: {
        "warning_decline_pct": 2.0,   # ≥2% share point drop → warning
        "critical_decline_pct": 5.0,  # ≥5% share point drop → critical
        "min_share_pct": 5.0,         # absolute floor before critical
    },
    KPIType.NRX_VOLUME: {
        "warning_decline_pct": 5.0,
        "critical_decline_pct": 15.0,
    },
    KPIType.TRX_VOLUME: {
        "warning_decline_pct": 5.0,
        "critical_decline_pct": 15.0,
    },
    KPIType.PERSISTENCE_6M: {
        "warning_below_pct": 65.0,   # absolute persistence % threshold
        "critical_below_pct": 55.0,
    },
    KPIType.PERSISTENCE_12M: {
        "warning_below_pct": 45.0,
        "critical_below_pct": 35.0,
    },
    KPIType.CONVERSION_RATE: {
        "warning_below_pct": 60.0,
        "critical_below_pct": 45.0,
    },
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class KPISnapshot:
    """A single KPI reading for one period.

    Attributes:
        kpi_type: KPI category.
        period: Period label (e.g. '2025-Q3', '2026-03').
        current_value: Current period value (share %, volume, rate %).
        previous_value: Prior period value for delta calculation.
        benchmark_value: Optional external benchmark (e.g. class average).
        brand: Brand or product name.
        geography: Market or region label.
    """

    kpi_type: KPIType
    period: str
    current_value: float
    previous_value: float
    brand: str
    geography: str = "national"
    benchmark_value: Optional[float] = None


@dataclass
class KPIAlert:
    """An alert raised by the KPI alert engine.

    Attributes:
        kpi_type: KPI that triggered the alert.
        severity: AlertSeverity level.
        brand: Brand associated with the alert.
        geography: Market or region.
        period: Period of the triggering observation.
        current_value: Current KPI value.
        previous_value: Prior period KPI value.
        delta: Absolute change (current - previous).
        delta_pct: Relative change as percentage.
        threshold_breached: Threshold label that was breached.
        message: Human-readable alert description.
    """

    kpi_type: KPIType
    severity: AlertSeverity
    brand: str
    geography: str
    period: str
    current_value: float
    previous_value: float
    delta: float
    delta_pct: float
    threshold_breached: str
    message: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class KPIAlertEngine:
    """Evaluate KPI snapshots and generate structured alerts.

    Args:
        thresholds: Optional override of default thresholds. Merge with
            ``DEFAULT_THRESHOLDS`` — only keys provided override defaults.

    Example:
        >>> engine = KPIAlertEngine()
        >>> snapshots = [
        ...     KPISnapshot(
        ...         kpi_type=KPIType.MARKET_SHARE,
        ...         period="2026-03",
        ...         current_value=18.2,
        ...         previous_value=23.5,
        ...         brand="Oncobrand A",
        ...         geography="Indonesia",
        ...     )
        ... ]
        >>> alerts = engine.evaluate(snapshots)
        >>> for a in alerts:
        ...     print(f"[{a.severity.value.upper()}] {a.message}")
        [CRITICAL] Oncobrand A market_share dropped 5.3pp in Indonesia (18.2% vs 23.5%)
    """

    def __init__(self, thresholds: Optional[Dict] = None):
        import copy
        self.thresholds: Dict[KPIType, Dict[str, float]] = copy.deepcopy(DEFAULT_THRESHOLDS)
        if thresholds:
            for kpi_type, overrides in thresholds.items():
                if kpi_type in self.thresholds:
                    self.thresholds[kpi_type].update(overrides)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, snapshots: List[KPISnapshot]) -> List[KPIAlert]:
        """Evaluate all snapshots and return any triggered alerts.

        Args:
            snapshots: List of :class:`KPISnapshot` to evaluate.

        Returns:
            List of :class:`KPIAlert`, sorted by severity (critical first).
        """
        if not snapshots:
            return []
        alerts: List[KPIAlert] = []
        for snap in snapshots:
            alert = self._evaluate_snapshot(snap)
            if alert:
                alerts.append(alert)
        severity_order = {AlertSeverity.CRITICAL: 0, AlertSeverity.WARNING: 1, AlertSeverity.INFO: 2}
        return sorted(alerts, key=lambda a: severity_order[a.severity])

    def get_critical_alerts(self, snapshots: List[KPISnapshot]) -> List[KPIAlert]:
        """Return only critical severity alerts.

        Args:
            snapshots: List of KPI snapshots to evaluate.

        Returns:
            List of critical :class:`KPIAlert` objects.
        """
        return [a for a in self.evaluate(snapshots) if a.severity == AlertSeverity.CRITICAL]

    def summary(self, snapshots: List[KPISnapshot]) -> Dict[str, int]:
        """Return count of alerts by severity level.

        Args:
            snapshots: List of KPI snapshots.

        Returns:
            Dict with keys 'critical', 'warning', 'info', 'clean'.
        """
        alerts = self.evaluate(snapshots)
        summary_counts: Dict[str, int] = {"critical": 0, "warning": 0, "info": 0, "clean": 0}
        for alert in alerts:
            summary_counts[alert.severity.value] += 1
        clean_count = len(snapshots) - len(alerts)
        summary_counts["clean"] = max(0, clean_count)
        return summary_counts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_snapshot(self, snap: KPISnapshot) -> Optional[KPIAlert]:
        """Dispatch to the appropriate evaluator based on KPI type."""
        evaluators = {
            KPIType.MARKET_SHARE: self._eval_market_share,
            KPIType.NRX_VOLUME: self._eval_volume,
            KPIType.TRX_VOLUME: self._eval_volume,
            KPIType.PERSISTENCE_6M: self._eval_persistence,
            KPIType.PERSISTENCE_12M: self._eval_persistence,
            KPIType.CONVERSION_RATE: self._eval_conversion,
        }
        evaluator = evaluators.get(snap.kpi_type)
        if evaluator:
            return evaluator(snap)
        return None

    def _eval_market_share(self, snap: KPISnapshot) -> Optional[KPIAlert]:
        t = self.thresholds[KPIType.MARKET_SHARE]
        delta = snap.current_value - snap.previous_value
        delta_pct = (delta / snap.previous_value * 100) if snap.previous_value else 0.0
        decline_pp = abs(delta) if delta < 0 else 0.0

        if decline_pp >= t["critical_decline_pct"] or snap.current_value < t["min_share_pct"]:
            severity = AlertSeverity.CRITICAL
            threshold_lbl = "critical_decline"
        elif decline_pp >= t["warning_decline_pct"]:
            severity = AlertSeverity.WARNING
            threshold_lbl = "warning_decline"
        else:
            return None

        msg = (
            f"{snap.brand} market_share dropped {decline_pp:.1f}pp in "
            f"{snap.geography} ({snap.current_value:.1f}% vs {snap.previous_value:.1f}%)"
        )
        return self._build_alert(snap, severity, delta, delta_pct, threshold_lbl, msg)

    def _eval_volume(self, snap: KPISnapshot) -> Optional[KPIAlert]:
        t = self.thresholds[snap.kpi_type]
        delta = snap.current_value - snap.previous_value
        delta_pct = (delta / snap.previous_value * 100) if snap.previous_value else 0.0
        decline_pct = abs(delta_pct) if delta < 0 else 0.0

        if decline_pct >= t["critical_decline_pct"]:
            severity = AlertSeverity.CRITICAL
            threshold_lbl = "critical_decline"
        elif decline_pct >= t["warning_decline_pct"]:
            severity = AlertSeverity.WARNING
            threshold_lbl = "warning_decline"
        else:
            return None

        kpi_label = snap.kpi_type.value.upper()
        msg = (
            f"{snap.brand} {kpi_label} fell {decline_pct:.1f}% in "
            f"{snap.geography} ({snap.current_value:,.0f} vs {snap.previous_value:,.0f})"
        )
        return self._build_alert(snap, severity, delta, delta_pct, threshold_lbl, msg)

    def _eval_persistence(self, snap: KPISnapshot) -> Optional[KPIAlert]:
        t = self.thresholds[snap.kpi_type]
        delta = snap.current_value - snap.previous_value
        delta_pct = (delta / snap.previous_value * 100) if snap.previous_value else 0.0

        if snap.current_value < t["critical_below_pct"]:
            severity = AlertSeverity.CRITICAL
            threshold_lbl = "critical_below"
        elif snap.current_value < t["warning_below_pct"]:
            severity = AlertSeverity.WARNING
            threshold_lbl = "warning_below"
        else:
            return None

        kpi_label = snap.kpi_type.value
        msg = (
            f"{snap.brand} {kpi_label} is {snap.current_value:.1f}% in "
            f"{snap.geography} — below {'critical' if severity == AlertSeverity.CRITICAL else 'warning'} threshold"
        )
        return self._build_alert(snap, severity, delta, delta_pct, threshold_lbl, msg)

    def _eval_conversion(self, snap: KPISnapshot) -> Optional[KPIAlert]:
        t = self.thresholds[KPIType.CONVERSION_RATE]
        delta = snap.current_value - snap.previous_value
        delta_pct = (delta / snap.previous_value * 100) if snap.previous_value else 0.0

        if snap.current_value < t["critical_below_pct"]:
            severity = AlertSeverity.CRITICAL
            threshold_lbl = "critical_below"
        elif snap.current_value < t["warning_below_pct"]:
            severity = AlertSeverity.WARNING
            threshold_lbl = "warning_below"
        else:
            return None

        msg = (
            f"{snap.brand} conversion rate is {snap.current_value:.1f}% in "
            f"{snap.geography} — low patient journey throughput"
        )
        return self._build_alert(snap, severity, delta, delta_pct, threshold_lbl, msg)

    @staticmethod
    def _build_alert(
        snap: KPISnapshot,
        severity: AlertSeverity,
        delta: float,
        delta_pct: float,
        threshold_breached: str,
        message: str,
    ) -> KPIAlert:
        return KPIAlert(
            kpi_type=snap.kpi_type,
            severity=severity,
            brand=snap.brand,
            geography=snap.geography,
            period=snap.period,
            current_value=round(snap.current_value, 4),
            previous_value=round(snap.previous_value, 4),
            delta=round(delta, 4),
            delta_pct=round(delta_pct, 2),
            threshold_breached=threshold_breached,
            message=message,
        )
