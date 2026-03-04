## [1.2.0] - 2026-04-01

### Added
- **Patient Risk Stratifier** (`src/patient_risk_stratifier.py`) — Charlson Comorbidity Index (CCI) risk stratification for oncology and chronic disease populations
  - `PatientProfile` dataclass: age, ECOG PS (0–4), comorbidities (17 validated CCI conditions), creatinine, albumin, metastatic disease flag
  - `PatientRiskStratifier.stratify()`: base CCI, age-adjusted CCI (Deyo 1992 +1/decade ≥50), Charlson 10-year survival estimate, risk tier (LOW/MODERATE/HIGH/VERY_HIGH)
  - Lab flags: elevated creatinine (>1.5 mg/dL) and hypoalbuminemia (<3.5 g/dL)
  - ECOG PS modifier: automated clinical recommendation adjustment for PS ≥2
  - `batch_stratify()`, `population_summary()` for trial and population health analytics
  - References: Charlson et al. (1987) J Chronic Dis; Deyo et al. (1992) J Clin Epidemiol
- **Unit tests** — 17 new tests in `tests/test_patient_risk_stratifier.py` (all passing)

## [1.1.0] - 2026-03-31

### Added
- **Clinical Trial Screener** (`src/clinical_trial_screener.py`) — CTCAE v5.0-aligned patient eligibility checker for oncology and rare disease trials
  - `PatientProfile` dataclass: age, ECOG status, diagnosis ICD-10, stage, prior therapy lines, labs, comorbidities, pregnancy, brain mets, active infection
  - `TrialProtocol` dataclass: configurable inclusion/exclusion criteria (age, ECOG, stage, CrCl, liver function, ANC, comorbidity codes)
  - `ClinicalTrialScreener.screen()`: criterion-by-criterion eligibility with ELIGIBLE/INELIGIBLE/NEEDS_REVIEW output
  - `LabValue.times_uln`: auto-computed ALT/AST/bilirubin as × Upper Limit of Normal
  - `batch_screen()`, `eligible_patients()`, `enrolment_funnel()` for recruitment planning
  - ECOG PS0–PS4 status validation with configurable max acceptable PS
  - Renal/hepatic exclusion logic (CrCl, ALT, AST, bilirubin, ANC)
  - Comorbidity ICD-10 prefix exclusion matching
- **Unit tests** — 28 new tests in `tests/test_clinical_trial_screener.py` (all passing)

### References
- NCI CTCAE v5.0 (2017) Common Terminology Criteria for Adverse Events.
- ECOG-ACRIN (2020) ECOG Performance Status Scale.
- ICH E6(R2) (2016) Guideline for Good Clinical Practice.

## [New] - 2026-03-28
### Added
- Edge case validators and handlers
- Comprehensive unit tests
- Realistic sample data (realistic_data.csv)
- Enhanced README with validation examples

# Changelog

## [2.0.0] - 2026-03-26

### Added
- **RealWorldEvidenceAnalyzer** (`src/real_world_evidence_analyzer.py`) — RWE synthesis for HEOR and payer dossiers
  - `RWEStudy` dataclass with GRACE checklist score, propensity matching flag, unmeasured confounders
  - Computed properties: Relative Risk, ARR, NNT, statistical significance, confidence level
  - GRACE-based confidence classification: HIGH / MODERATE / LOW / VERY_LOW
  - `synthesize()`: sample-size-weighted aggregate RR across multiple studies
  - `filter_by_confidence()`: filter study portfolio by minimum evidence quality
  - `evidence_gap_report()`: identify missing evidence types (long-term, propensity, registry, multi-market)
  - Narrative summary statement generator for payer/KOL communication
  - Limitation auto-detection: no propensity matching, unmeasured confounders, single data source
  - Recommended next study generation based on evidence gaps
- Unit tests: 16 new tests in `tests/test_real_world_evidence_analyzer.py`

## [1.9.0] - 2026-03-25

### Added
- **Market Penetration Estimator** (`src/market_penetration_estimator.py`) — patient funnel analysis and opportunity gap sizing
  - Four-stage patient funnel: Prevalent → Diagnosed → Treated → On Brand
  - Absolute patient counts derived from population × epidemiological rates
  - Penetration rates at each funnel stage with multi-level brand penetration views
  - Gap quantification: undiagnosed patients, untreated diagnosed, competitor-treated
  - Opportunity scores (0–100) per funnel stage, indicating remaining headroom
  - Primary opportunity identification (diagnosis/treatment/brand switch)
  - Stage-specific strategic recommendations for field force and KAM teams
  - Multi-market comparison sorted by brand opportunity score
  - Supports both chronic disease (prevalence-based) and acute (incidence-based) modes
- Unit tests: 17 new tests in `tests/test_market_penetration_estimator.py`

## [1.8.0] - 2026-03-23

### Added
- `src/therapy_line_segmentation.py` — Therapy Line Segmentation engine
  - `PatientRecord` dataclass with full validation
  - `TherapyLineSegmentation` class with market share, progression, and channel analytics
  - `market_share_by_line()` — drug share % within 1L/2L/3L+
  - `progression_rates()` — % patients progressing to next therapy line
  - `discontinuation_breakdown()` — reason split with optional line filter
  - `channel_split()` — hospital/retail/specialty distribution
  - `full_summary()` — comprehensive segmentation dashboard dict
- `data/sample_therapy_line_data.csv` — 25 NSCLC patient records across ID/TH/VN
- 21 unit tests in `tests/test_therapy_line_segmentation.py`

## [1.7.0] - 2026-03-22

### Added
- **Treatment Switching Analyzer** (`src/treatment_switching_analyzer.py`) — therapy switch flow analysis for disease area BI
  - `SwitchEvent` dataclass capturing patient, date, from/to drug, therapy line, reason code, and payer type
  - `SwitchFlowSummary` dataclass with net patient flow, brand-to-generic rate, and competitive loss rate
  - `brand_switch_summary()` — full switching KPIs for a target brand with therapy line and payer filters
  - `therapy_line_progression()` — distribution of switch events across Line 1/2/3 with optional patient-level filter
  - `formulary_signal_detector()` — detects spikes in formulary/step-edit reason codes indicating managed care pressure
  - `reason_code_distribution()` — switch reason breakdown (cost, efficacy, formulary, physician) filterable by drug pair
  - Configurable generic-detection heuristics for brand-to-generic rate calculation
  - Case-insensitive drug name matching throughout
- **Unit tests** — 25 tests in `tests/test_treatment_switching_analyzer.py` covering all public methods, filters, and edge cases

### References
- IQVIA Pharmacy Claims Analysis Framework (IQVIA Institute, 2023)
- PhRMA Medication Switching and Adherence Research Best Practices
- ISPOR Good Practices for Observational Studies (2022)

## [1.6.0] - 2026-03-21

### Added
- **KPI Alert Engine** (`src/kpi_alert_engine.py`) — automated KPI threshold monitoring for commercial analytics
  - Monitors market share, NRx/TRx volume, persistence (6m/12m), and conversion rate KPIs
  - Three severity levels: info, warning, critical
  - `evaluate()` returns sorted alerts (critical first)
  - `get_critical_alerts()` for dashboard priority view
  - `summary()` counts by severity for reporting headers
  - Configurable thresholds via constructor override
  - `KPISnapshot` and `KPIAlert` dataclasses for structured I/O
- **Sample data** — `sample_data/kpi_snapshots_sample.csv` with 10 brand-geography-KPI combinations
- **Unit tests** — 20 new tests in `tests/test_kpi_alert_engine.py`

## [1.5.0] - 2026-03-18

### Added
- **Patient Journey Funnel Analysis** (`src/patient_journey_funnel.py`) — end-to-end patient pathway modelling
  - `FunnelStage` dataclass with conversion rates, drop counts, and drop reasons
  - `PatientJourneyFunnel` with overall conversion rate, biggest-drop stage identification, and summary reporting
  - `PatientJourneyAnalyzer.build_funnel()`: constructs 6-stage funnel (diagnosed → maintained 12m) from conversion rates
  - `opportunity_score()`: quantifies commercial gap at each stage (untreated, competitor share, persistence gaps)
  - `compare_brands()`: side-by-side funnel comparison sorted by 12-month retention
  - Industry benchmark rates from IQVIA/Veeva frameworks
- **Sample data** — `sample_data/patient_journey_data.csv` with 9 brand scenarios across T2D, CVD, Oncology, Respiratory
- **Unit tests** — 29 tests in `tests/test_patient_journey.py` covering funnel construction, opportunity scoring, and edge cases

## [1.4.0] - 2026-03-15

### Added
- **HCP Prescriber Segmentation** — `segment_prescribers()`: Classifies HCPs into Champion/High-Volume/Loyal-Mid/Opportunity/Low-Activity using volume percentiles and brand loyalty score
- **Share of Voice Calculator** — `calculate_therapy_area_share_of_voice()`: Calculates promotional SoV per brand with ranking for therapy area benchmarking
- **Unit Tests** — 10 new tests in `tests/test_hcp_segmentation.py` covering segmentation logic, SoV calculation, and edge cases
- **README** — Added HCP segmentation and Share of Voice usage examples

## [CURRENT] - 2026-03-07

### Added
- Add epidemiological metrics (prevalence, incidence)
- Enhanced README with getting started guide
- Comprehensive unit tests for core functions
- Real-world sample data and fixtures

### Improved
- Edge case handling for null/empty inputs
- Boundary condition validation

### Fixed
- Various edge cases and corner scenarios

---

## [2026-03-08]
- Enhanced documentation and examples
- Added unit test fixtures and test coverage
- Added comprehensive docstrings to key functions
- Added error handling for edge cases
- Improved README with setup and usage examples

## [2.1.0] - 2026-03-27

### Added
- **Budget Impact Analyzer** (`src/budget_impact_analyzer.py`) — ISPOR-aligned payer Budget Impact Model for new drug market entry
  - `DrugProfile` dataclass: gross price, rebate%, administration cost, adherence, response rate, hospitalisation offset, AE cost; computed `net_annual_cost_per_patient_usd`, `total_annual_cost_per_patient_usd`, `net_cost_after_offsets_usd` properties
  - `EligiblePopulation` dataclass: population funnel (prevalence→diagnosed→treated→eligible) with annual growth factor
  - `MarketShare` dataclass: year-indexed market share trajectory per drug
  - `BudgetImpactAnalyzer` class (1–5 year forecast horizon)
  - `run()`: full budget impact run returning annual `BudgetImpactResult` per year (with/without new drug)
  - `cumulative_impact()`: aggregated total and average annual incremental cost over horizon
  - `sensitivity_analysis()`: one-way price sensitivity (±N% list price) across configured variations
  - `BudgetImpactResult.is_cost_saving` property for downstream logic
  - Without-scenario: new drug share redistributed proportionally to comparator drugs
- **Unit tests** — 37 new tests in `tests/test_budget_impact_analyzer.py` covering all classes, run scenarios, edge cases

### References
- Sullivan et al. (2014) ISPOR Good Practice Guidelines for BIM. Value in Health 17(1):5–14
- NICE (2022) NICE Health Technology Evaluations: Methods Guide §6
