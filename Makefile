PYTHON ?= python
SRC_PATH ?= src
REAL_START ?= 2024-01-02
REAL_END ?= 2024-01-05
REAL_LIMIT ?= 5
REAL_REQUEST_INTERVAL ?= 0.5
REAL_UNIVERSE ?= data/universe/smoke.csv
REAL_OUTPUT ?= results/real_smoke

.PHONY: test backtest validate signal compile real-refresh-stock-basic real-smoke

test:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m unittest discover -s tests

backtest:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli backtest --config configs/sample_backtest.json

validate:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli validate --config configs/sample_backtest.json --split-date 2024-02-15 --output-dir results/validation_sample

signal:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli signal --config configs/sample_backtest.json --portfolio configs/live_portfolio.example.json

compile:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m compileall src tests

real-refresh-stock-basic:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data sync --provider tushare --symbols 000001.SZ --start-date $(REAL_START) --end-date $(REAL_END) --cache-dir data/daily --with-stock-basic --request-interval $(REAL_REQUEST_INTERVAL)

real-smoke:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data universe --stock-basic data/stocks/stock_basic.csv --output $(REAL_UNIVERSE) --as-of-date $(REAL_END) --min-listed-days 180 --limit $(REAL_LIMIT)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data sync --provider tushare --symbols-file $(REAL_UNIVERSE) --limit $(REAL_LIMIT) --start-date $(REAL_START) --end-date $(REAL_END) --cache-dir data/daily --with-adj-factor --with-constraints --index-symbols 000300.SH --request-interval $(REAL_REQUEST_INTERVAL)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data adjust --symbols-file $(REAL_UNIVERSE) --limit $(REAL_LIMIT) --daily-dir data/daily --adj-factor-dir data/adj_factor --mode qfq --output-dir data/qfq_daily
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli backtest --config configs/a_share_midterm.json --symbols-file $(REAL_UNIVERSE) --limit $(REAL_LIMIT) --data-dir data/qfq_daily --start-date $(REAL_START) --end-date $(REAL_END) --output-dir $(REAL_OUTPUT)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli signal --config configs/a_share_midterm.json --symbols-file $(REAL_UNIVERSE) --limit $(REAL_LIMIT) --data-dir data/qfq_daily --start-date $(REAL_START) --end-date $(REAL_END) --output-dir $(REAL_OUTPUT) --portfolio configs/live_portfolio.example.json
