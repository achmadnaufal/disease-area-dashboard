# Contributing to Disease Area Dashboard

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/disease-area-dashboard.git`
3. Install dev dependencies: `pip install -r requirements.txt`
4. Create a feature branch: `git checkout -b feat/your-feature`

## Development Guidelines

- Follow PEP 8 style conventions
- Add type hints to all public functions
- Write unit tests for new features (`pytest tests/ -v`)
- Update `CHANGELOG.md` with a summary of changes

## Areas for Contribution

- IQVIA Symphony Health data format reader
- Veeva CRM call activity integration
- Streamlit dashboard UI layer
- Payer/formulary access analysis module
- Forecast modelling (ARIMA, Prophet) for TRx projections
- Additional therapy area data generators

## Submitting a PR

1. Ensure all tests pass: `pytest tests/ -v`
2. Use semantic commit messages: `feat: add IQVIA Symphony Health data parser`
3. Open a pull request with a clear description

Questions? Open an issue.
