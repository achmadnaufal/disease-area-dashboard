# Changelog

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
