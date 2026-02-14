"""Tests for epidemiology metrics."""
import pytest
from epidemiology_metrics import EpidemiologyMetrics


class TestEpidemiologyMetrics:
    """Test epidemiology metrics."""
    
    def test_initialization(self):
        """Test valid initialization."""
        metrics = EpidemiologyMetrics("COVID-19", cases=1000, population=1000000, deaths=50)
        assert metrics.disease_name == "COVID-19"
        assert metrics.cases == 1000
    
    def test_invalid_population(self):
        """Test invalid population."""
        with pytest.raises(ValueError):
            EpidemiologyMetrics("Disease", cases=100, population=-1000)
    
    def test_incidence_rate(self):
        """Test incidence rate calculation."""
        metrics = EpidemiologyMetrics("Disease", cases=100, population=100000)
        rate = metrics.calculate_incidence_rate(per=100000)
        assert rate == pytest.approx(100.0, 0.1)
    
    def test_mortality_rate(self):
        """Test mortality rate calculation."""
        metrics = EpidemiologyMetrics("Disease", cases=1000, population=1000000, deaths=100)
        cfr = metrics.calculate_mortality_rate()
        assert cfr == pytest.approx(10.0, 0.1)
    
    def test_metrics_summary(self):
        """Test metrics summary generation."""
        metrics = EpidemiologyMetrics("Malaria", cases=5000, population=1000000, deaths=100)
        result = metrics.calculate_metrics()
        assert "disease" in result
        assert "incidence_per_100k" in result
        assert "cfr_percent" in result
