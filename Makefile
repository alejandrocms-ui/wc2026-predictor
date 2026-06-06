.PHONY: help install install-dev refresh offline app test lint fmt backtest clean

help:
	@echo "wc2026-predictor — common tasks"
	@echo "  make install      core + app deps (zero-key runtime)"
	@echo "  make install-dev  + dev tooling (pytest, ruff, black)"
	@echo "  make refresh      rebuild everything (ingest -> fit -> simulate -> persist)"
	@echo "  make offline      rebuild using cached/seed data only"
	@echo "  make app          launch the Streamlit app"
	@echo "  make test         run the test suite"
	@echo "  make backtest     regenerate MODEL_REPORT.md (walk-forward, RPS vs Elo)"
	@echo "  make lint / fmt   ruff check / black+ruff format"

install:
	pip install -e ".[app]"

install-dev:
	pip install -e ".[app,ml,dev]"

refresh:
	python -m wc2026.pipeline

offline:
	python -m wc2026.pipeline --offline

app:
	streamlit run wc2026/app/main.py

test:
	pytest -q

backtest:
	python scripts/run_backtest.py

lint:
	ruff check wc2026 tests

fmt:
	black wc2026 tests scripts
	ruff check --fix wc2026 tests

clean:
	rm -rf data/cache/*.parquet data/*.duckdb .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
