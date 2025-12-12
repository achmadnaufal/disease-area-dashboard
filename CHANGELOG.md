# Changelog

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
