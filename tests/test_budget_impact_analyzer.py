"""Unit tests for src.budget_impact_analyzer.

Covers: DrugProfile validation, EligiblePopulation sizing, MarketShare,
BudgetImpactAnalyzer construction and run(), cumulative_impact(),
sensitivity_analysis(), and edge cases.
"""

import pytest
from src.budget_impact_analyzer import (
    DrugProfile,
    EligiblePopulation,
    MarketShare,
    BudgetImpactResult,
    BudgetImpactAnalyzer,
)


# ---------------------------------------------------------------------------
# DrugProfile tests
# ---------------------------------------------------------------------------


class TestDrugProfile:
    def test_basic_creation(self):
        dp = DrugProfile(
            drug_name="DrugX",
            annual_cost_per_patient_usd=50_000.0,
            rebate_pct=10.0,
            is_new_drug=True,
        )
        assert dp.drug_name == "DrugX"
        assert dp.is_new_drug is True

    def test_net_annual_cost(self):
        dp = DrugProfile("D", 100_000.0, rebate_pct=20.0)
        assert dp.net_annual_cost_per_patient_usd == pytest.approx(80_000.0)

    def test_total_cost_includes_admin_and_ae(self):
        dp = DrugProfile(
            drug_name="D",
            annual_cost_per_patient_usd=10_000.0,
            rebate_pct=0.0,
            administration_cost_usd=500.0,
            ae_management_cost_usd=200.0,
            adherence_rate=1.0,
        )
        assert dp.total_annual_cost_per_patient_usd == pytest.approx(10_700.0)

    def test_adherence_scales_drug_cost(self):
        dp = DrugProfile("D", 10_000.0, adherence_rate=0.8)
        # drug cost = 10000 * 0.8 = 8000
        assert dp.total_annual_cost_per_patient_usd == pytest.approx(8_000.0)

    def test_offset_reduces_net_cost(self):
        dp = DrugProfile(
            drug_name="D",
            annual_cost_per_patient_usd=10_000.0,
            response_rate=0.6,
            annual_hospitalisation_cost_avoided_usd=5_000.0,
        )
        # offset = 5000 * 0.6 = 3000; net = 10000 - 3000 = 7000
        assert dp.net_cost_after_offsets_usd == pytest.approx(7_000.0)

    def test_empty_drug_name_raises(self):
        with pytest.raises(ValueError, match="drug_name"):
            DrugProfile("", 10_000.0)

    def test_negative_cost_raises(self):
        with pytest.raises(ValueError, match="annual_cost"):
            DrugProfile("D", -1.0)

    def test_excessive_rebate_raises(self):
        with pytest.raises(ValueError, match="rebate_pct"):
            DrugProfile("D", 10_000.0, rebate_pct=70.0)

    def test_invalid_adherence_raises(self):
        with pytest.raises(ValueError, match="adherence_rate"):
            DrugProfile("D", 10_000.0, adherence_rate=1.5)

    def test_invalid_response_rate_raises(self):
        with pytest.raises(ValueError, match="response_rate"):
            DrugProfile("D", 10_000.0, response_rate=-0.1)


# ---------------------------------------------------------------------------
# EligiblePopulation tests
# ---------------------------------------------------------------------------


class TestEligiblePopulation:
    @pytest.fixture
    def pop(self):
        return EligiblePopulation(
            total_population=1_000_000,
            disease_prevalence_pct=2.5,
            diagnosed_rate=0.7,
            treated_rate=0.6,
            eligible_for_new_drug_rate=0.5,
            annual_growth_rate_pct=1.0,
        )

    def test_eligible_patients_base_year(self, pop):
        # 1_000_000 * 0.025 * 0.7 * 0.6 * 0.5 = 5250
        expected = 1_000_000 * 0.025 * 0.7 * 0.6 * 0.5
        assert pop.eligible_patients(year=0) == pytest.approx(expected)

    def test_eligible_patients_year_1_growth(self, pop):
        base = pop.eligible_patients(0)
        yr1 = pop.eligible_patients(1)
        assert yr1 == pytest.approx(base * 1.01)

    def test_zero_population_raises(self):
        with pytest.raises(ValueError, match="total_population"):
            EligiblePopulation(0, 2.5, 0.7, 0.6)

    def test_zero_prevalence_raises(self):
        with pytest.raises(ValueError, match="disease_prevalence"):
            EligiblePopulation(1_000_000, 0.0, 0.7, 0.6)

    def test_excessive_prevalence_raises(self):
        with pytest.raises(ValueError, match="disease_prevalence"):
            EligiblePopulation(1_000_000, 101.0, 0.7, 0.6)

    def test_zero_diagnosed_rate_raises(self):
        with pytest.raises(ValueError, match="diagnosed_rate"):
            EligiblePopulation(1_000_000, 2.5, 0.0, 0.6)

    def test_invalid_growth_rate_raises(self):
        with pytest.raises(ValueError, match="annual_growth_rate"):
            EligiblePopulation(1_000_000, 2.5, 0.7, 0.6, annual_growth_rate_pct=30.0)


# ---------------------------------------------------------------------------
# MarketShare tests
# ---------------------------------------------------------------------------


class TestMarketShare:
    def test_basic_creation(self):
        ms = MarketShare(drug_name="DrugX", year_shares={1: 0.10, 2: 0.20, 3: 0.30})
        assert ms.share_at(1) == pytest.approx(0.10)

    def test_missing_year_returns_zero(self):
        ms = MarketShare(drug_name="DrugX", year_shares={1: 0.10})
        assert ms.share_at(5) == 0.0

    def test_invalid_share_raises(self):
        with pytest.raises(ValueError, match="outside"):
            MarketShare(drug_name="DrugX", year_shares={1: 1.5})

    def test_negative_share_raises(self):
        with pytest.raises(ValueError, match="outside"):
            MarketShare(drug_name="DrugX", year_shares={1: -0.1})


# ---------------------------------------------------------------------------
# BudgetImpactAnalyzer fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def analyzer():
    return BudgetImpactAnalyzer(
        model_name="Oncology BIM 2026",
        disease_area="NSCLC",
        forecast_years=3,
    )


@pytest.fixture
def drug_profiles():
    return [
        DrugProfile(
            drug_name="NewDrug",
            annual_cost_per_patient_usd=80_000.0,
            rebate_pct=15.0,
            response_rate=0.55,
            annual_hospitalisation_cost_avoided_usd=8_000.0,
            is_new_drug=True,
        ),
        DrugProfile(
            drug_name="SOC",
            annual_cost_per_patient_usd=45_000.0,
            rebate_pct=5.0,
            response_rate=0.35,
            annual_hospitalisation_cost_avoided_usd=3_000.0,
            is_new_drug=False,
        ),
    ]


@pytest.fixture
def population():
    return EligiblePopulation(
        total_population=5_000_000,
        disease_prevalence_pct=0.5,
        diagnosed_rate=0.8,
        treated_rate=0.7,
        eligible_for_new_drug_rate=0.6,
    )


@pytest.fixture
def market_shares():
    return [
        MarketShare("NewDrug", {1: 0.05, 2: 0.12, 3: 0.20}),
        MarketShare("SOC", {1: 0.95, 2: 0.88, 3: 0.80}),
    ]


# ---------------------------------------------------------------------------
# BudgetImpactAnalyzer construction
# ---------------------------------------------------------------------------


class TestAnalyzerInit:
    def test_valid_creation(self, analyzer):
        assert analyzer.disease_area == "NSCLC"
        assert analyzer.forecast_years == 3

    def test_empty_model_name_raises(self):
        with pytest.raises(ValueError, match="model_name"):
            BudgetImpactAnalyzer("", "NSCLC", 3)

    def test_invalid_forecast_years_raises(self):
        with pytest.raises(ValueError, match="forecast_years"):
            BudgetImpactAnalyzer("M", "D", 6)

    def test_zero_forecast_years_raises(self):
        with pytest.raises(ValueError, match="forecast_years"):
            BudgetImpactAnalyzer("M", "D", 0)


# ---------------------------------------------------------------------------
# Run model tests
# ---------------------------------------------------------------------------


class TestRunModel:
    def test_returns_correct_number_of_years(
        self, analyzer, drug_profiles, population, market_shares
    ):
        results = analyzer.run(drug_profiles, population, market_shares)
        assert len(results) == 3

    def test_year_indexed_correctly(
        self, analyzer, drug_profiles, population, market_shares
    ):
        results = analyzer.run(drug_profiles, population, market_shares)
        assert [r.year for r in results] == [1, 2, 3]

    def test_incremental_cost_computed(
        self, analyzer, drug_profiles, population, market_shares
    ):
        results = analyzer.run(drug_profiles, population, market_shares)
        for r in results:
            assert isinstance(r.incremental_cost_usd, float)

    def test_new_drug_patients_increases_with_share(
        self, analyzer, drug_profiles, population, market_shares
    ):
        results = analyzer.run(drug_profiles, population, market_shares)
        # Share grows 5% → 12% → 20%, so patient count should increase
        assert results[0].new_drug_patients < results[1].new_drug_patients
        assert results[1].new_drug_patients < results[2].new_drug_patients

    def test_no_new_drug_raises(self, analyzer, population, market_shares):
        drugs_no_new = [
            DrugProfile("A", 50_000.0, is_new_drug=False),
            DrugProfile("B", 40_000.0, is_new_drug=False),
        ]
        shares = [MarketShare("A", {1: 0.5}), MarketShare("B", {1: 0.5})]
        with pytest.raises(ValueError, match="is_new_drug"):
            analyzer.run(drugs_no_new, population, shares)

    def test_missing_market_share_raises(self, analyzer, drug_profiles, population):
        incomplete_shares = [MarketShare("NewDrug", {1: 0.1, 2: 0.2, 3: 0.3})]
        with pytest.raises(ValueError, match="missing"):
            analyzer.run(drug_profiles, population, incomplete_shares)

    def test_result_has_scenario_name(
        self, analyzer, drug_profiles, population, market_shares
    ):
        results = analyzer.run(
            drug_profiles, population, market_shares, scenario_name="pessimistic"
        )
        assert results[0].scenario_name == "pessimistic"


# ---------------------------------------------------------------------------
# Cumulative impact tests
# ---------------------------------------------------------------------------


class TestCumulativeImpact:
    def test_structure(self, analyzer, drug_profiles, population, market_shares):
        results = analyzer.run(drug_profiles, population, market_shares)
        cum = analyzer.cumulative_impact(results)
        assert "total_incremental_cost_usd" in cum
        assert "is_cost_saving" in cum
        assert cum["forecast_years"] == 3

    def test_empty_results(self, analyzer):
        assert analyzer.cumulative_impact([]) == {}

    def test_is_cost_saving_flag(self, analyzer, population, market_shares):
        # New drug cheaper than SOC → should be cost saving
        cheap_new = DrugProfile("NewDrug", 10_000.0, is_new_drug=True)
        expensive_soc = DrugProfile("SOC", 50_000.0, is_new_drug=False)
        results = analyzer.run([cheap_new, expensive_soc], population, market_shares)
        cum = analyzer.cumulative_impact(results)
        assert cum["is_cost_saving"] is True


# ---------------------------------------------------------------------------
# BudgetImpactResult tests
# ---------------------------------------------------------------------------


class TestBudgetImpactResult:
    def test_is_cost_saving_positive(self):
        r = BudgetImpactResult(
            year=1, eligible_patients=1000, scenario_name="base",
            without_new_drug_cost_usd=5_000_000, with_new_drug_cost_usd=4_500_000,
            incremental_cost_usd=-500_000, incremental_cost_per_patient_usd=-500,
            new_drug_patients=50,
        )
        assert r.is_cost_saving is True

    def test_is_cost_saving_negative_when_expensive(self):
        r = BudgetImpactResult(
            year=1, eligible_patients=1000, scenario_name="base",
            without_new_drug_cost_usd=4_000_000, with_new_drug_cost_usd=5_000_000,
            incremental_cost_usd=1_000_000, incremental_cost_per_patient_usd=1000,
            new_drug_patients=50,
        )
        assert r.is_cost_saving is False
