"""
Unit tests for KPIAlertEngine.
"""

import pytest
from src.kpi_alert_engine import (
    KPIAlertEngine,
    KPISnapshot,
    KPIAlert,
    KPIType,
    AlertSeverity,
)


@pytest.fixture
def engine():
    return KPIAlertEngine()


def make_snap(kpi_type, current, previous, brand="BrandX", geo="Indonesia", period="2026-03"):
    return KPISnapshot(
        kpi_type=kpi_type,
        period=period,
        current_value=current,
        previous_value=previous,
        brand=brand,
        geography=geo,
    )


class TestMarketShare:
    def test_no_alert_when_stable(self, engine):
        snap = make_snap(KPIType.MARKET_SHARE, 22.0, 22.5)
        alerts = engine.evaluate([snap])
        assert len(alerts) == 0

    def test_warning_on_moderate_decline(self, engine):
        snap = make_snap(KPIType.MARKET_SHARE, 20.0, 22.5)  # 2.5pp drop
        alerts = engine.evaluate([snap])
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_critical_on_large_decline(self, engine):
        snap = make_snap(KPIType.MARKET_SHARE, 16.0, 23.0)  # 7pp drop
        alerts = engine.evaluate([snap])
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_critical_when_below_minimum_share(self, engine):
        snap = make_snap(KPIType.MARKET_SHARE, 3.0, 3.5)
        alerts = engine.evaluate([snap])
        assert alerts[0].severity == AlertSeverity.CRITICAL


class TestVolumeAlerts:
    def test_nrx_warning_on_5pct_decline(self, engine):
        snap = make_snap(KPIType.NRX_VOLUME, 9400, 10000)  # -6%
        alerts = engine.evaluate([snap])
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_trx_critical_on_large_decline(self, engine):
        snap = make_snap(KPIType.TRX_VOLUME, 8000, 10000)  # -20%
        alerts = engine.evaluate([snap])
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_no_alert_on_increase(self, engine):
        snap = make_snap(KPIType.NRX_VOLUME, 11000, 10000)
        alerts = engine.evaluate([snap])
        assert len(alerts) == 0


class TestPersistenceAlerts:
    def test_6m_warning_below_65(self, engine):
        snap = make_snap(KPIType.PERSISTENCE_6M, 62.0, 68.0)
        alerts = engine.evaluate([snap])
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_6m_critical_below_55(self, engine):
        snap = make_snap(KPIType.PERSISTENCE_6M, 50.0, 70.0)
        alerts = engine.evaluate([snap])
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_12m_warning(self, engine):
        snap = make_snap(KPIType.PERSISTENCE_12M, 42.0, 50.0)
        alerts = engine.evaluate([snap])
        assert alerts[0].severity == AlertSeverity.WARNING


class TestConversionRate:
    def test_warning_below_60(self, engine):
        snap = make_snap(KPIType.CONVERSION_RATE, 58.0, 65.0)
        alerts = engine.evaluate([snap])
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_critical_below_45(self, engine):
        snap = make_snap(KPIType.CONVERSION_RATE, 40.0, 62.0)
        alerts = engine.evaluate([snap])
        assert alerts[0].severity == AlertSeverity.CRITICAL


class TestEvaluate:
    def test_empty_input_returns_empty(self, engine):
        assert engine.evaluate([]) == []

    def test_alerts_sorted_critical_first(self, engine):
        snaps = [
            make_snap(KPIType.NRX_VOLUME, 9400, 10000, brand="A"),        # warning
            make_snap(KPIType.MARKET_SHARE, 15.0, 23.0, brand="B"),       # critical
        ]
        alerts = engine.evaluate(snaps)
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_alert_message_contains_brand(self, engine):
        snap = make_snap(KPIType.MARKET_SHARE, 15.0, 22.0, brand="MyBrand")
        alerts = engine.evaluate([snap])
        assert "MyBrand" in alerts[0].message


class TestSummary:
    def test_summary_keys(self, engine):
        summary = engine.summary([])
        assert set(summary.keys()) == {"critical", "warning", "info", "clean"}

    def test_summary_counts(self, engine):
        snaps = [
            make_snap(KPIType.MARKET_SHARE, 15.0, 23.0),   # critical
            make_snap(KPIType.NRX_VOLUME, 9400, 10000),     # warning
            make_snap(KPIType.NRX_VOLUME, 11000, 10000),    # no alert → clean
        ]
        s = engine.summary(snaps)
        assert s["critical"] == 1
        assert s["warning"] == 1
        assert s["clean"] == 1


class TestCustomThresholds:
    def test_custom_threshold_applied(self):
        engine = KPIAlertEngine(thresholds={
            KPIType.MARKET_SHARE: {"warning_decline_pct": 1.0, "critical_decline_pct": 3.0}
        })
        snap = make_snap(KPIType.MARKET_SHARE, 21.5, 23.0)  # 1.5pp drop — warning with custom threshold
        alerts = engine.evaluate([snap])
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING
