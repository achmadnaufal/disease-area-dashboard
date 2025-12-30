# Changelog

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
