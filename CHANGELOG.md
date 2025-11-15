# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.3.0] - 2026-03-05
### Added
- `brand_segmentation()`: segments brands into Leader/Challenger/Niche/Declining tiers using share and trend slope
- `export_report()`: runs full analysis and exports branded market share + segment report to CSV
- 8 new unit tests covering segmentation, segment validity, and CSV export
### Improved
- README updated with brand segmentation usage example and output table

## [1.2.0] - 2026-03-04
### Added
- `market_share_analysis()`: brand TRx/NRx/sales share per period with ranking
- `mat_trend()`: Moving Annual Total (MAT) with YoY growth % per brand
- Sample cardiovascular sales data (4 brands, 4 periods)
- 13 unit tests covering validation, market share math, and MAT calculation
### Fixed
- `validate()` checks for required brand and trx columns
- `preprocess()` fills missing numeric values with 0 (not median, appropriate for pharma)
## [1.1.0] - 2026-03-02
### Added
- Add predictive epidemiology module and market sizing templates
- Improved unit test coverage
- Enhanced documentation with realistic examples
