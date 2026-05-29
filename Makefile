PYTHON ?= python
SRC_PATH ?= src
REAL_START ?= 2024-01-02
REAL_END ?= 2024-01-05
REAL_LIMIT ?= 5
REAL_REQUEST_INTERVAL ?= 0.5
REAL_REQUEST_RETRIES ?= 3
REAL_RETRY_BACKOFF ?= 1.0
REAL_UNIVERSE ?= data/universe/smoke.csv
REAL_OUTPUT ?= results/real_smoke
MVP_START ?= 2023-01-01
MVP_END ?= 2024-12-31
MVP_SPLIT ?= 2023-12-29
MVP_LONG_START ?= 2021-01-01
MVP_LONG_SPLIT ?= 2023-12-29
MVP_LIMIT ?= 20
MVP_REQUEST_INTERVAL ?= 0.5
MVP_REQUEST_RETRIES ?= 3
MVP_RETRY_BACKOFF ?= 1.0
MVP_UNIVERSE ?= data/universe/mvp20.csv
MVP_OUTPUT ?= results/real_mvp
MVP_LIQUID_UNIVERSE ?= data/universe/mvp50_liquid.csv
MVP_LIQUID_OUTPUT ?= results/real_mvp50_liquid
MVP_LIQUID_LONG_OUTPUT ?= results/real_mvp50_liquid_2021_2024
MVP_CANDIDATE_UNIVERSE ?= data/universe/mvp_candidates.csv
MVP_CANDIDATE_LIMIT ?= 150
MVP_LIQUIDITY_WINDOW ?= 60
MVP_LIQUID_MIN_AVG_AMOUNT ?= 300000
MVP_INDEX_SYMBOLS ?= 000300.SH
MVP_INITIAL_CASH ?= 100000
MVP_FILLS ?= configs/fills.example.csv

.PHONY: test backtest validate signal compile real-check-env real-refresh-stock-basic real-smoke real-mvp real-mvp-liquid real-mvp-liquid-long real-mvp-liquid-local real-mvp-fills

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

real-check-env:
	test -n "$$TUSHARE_TOKEN"

real-refresh-stock-basic:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data sync --provider tushare --symbols 000001.SZ --start-date $(REAL_START) --end-date $(REAL_END) --cache-dir data/daily --with-stock-basic --request-interval $(REAL_REQUEST_INTERVAL) --request-retries $(REAL_REQUEST_RETRIES) --retry-backoff $(REAL_RETRY_BACKOFF)

real-smoke:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data universe --stock-basic data/stocks/stock_basic.csv --output $(REAL_UNIVERSE) --as-of-date $(REAL_END) --min-listed-days 180 --limit $(REAL_LIMIT)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data sync --provider tushare --symbols-file $(REAL_UNIVERSE) --limit $(REAL_LIMIT) --start-date $(REAL_START) --end-date $(REAL_END) --cache-dir data/daily --with-adj-factor --with-constraints --index-symbols 000300.SH --request-interval $(REAL_REQUEST_INTERVAL) --request-retries $(REAL_REQUEST_RETRIES) --retry-backoff $(REAL_RETRY_BACKOFF)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data adjust --symbols-file $(REAL_UNIVERSE) --limit $(REAL_LIMIT) --daily-dir data/daily --adj-factor-dir data/adj_factor --mode qfq --output-dir data/qfq_daily
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli backtest --config configs/a_share_midterm.json --symbols-file $(REAL_UNIVERSE) --limit $(REAL_LIMIT) --data-dir data/qfq_daily --start-date $(REAL_START) --end-date $(REAL_END) --output-dir $(REAL_OUTPUT)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli signal --config configs/a_share_midterm.json --symbols-file $(REAL_UNIVERSE) --limit $(REAL_LIMIT) --data-dir data/qfq_daily --start-date $(REAL_START) --end-date $(REAL_END) --output-dir $(REAL_OUTPUT) --portfolio configs/live_portfolio.example.json

real-mvp: real-check-env
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data sync --provider tushare --symbols 000001.SZ --start-date $(MVP_START) --end-date $(MVP_START) --cache-dir data/daily --with-stock-basic --request-interval $(MVP_REQUEST_INTERVAL) --request-retries $(MVP_REQUEST_RETRIES) --retry-backoff $(MVP_RETRY_BACKOFF)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data universe --stock-basic data/stocks/stock_basic.csv --output $(MVP_UNIVERSE) --as-of-date $(MVP_END) --min-listed-days 180 --limit $(MVP_LIMIT)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data sync --provider tushare --symbols-file $(MVP_UNIVERSE) --limit $(MVP_LIMIT) --start-date $(MVP_START) --end-date $(MVP_END) --cache-dir data/daily --with-adj-factor --with-constraints --index-symbols $(MVP_INDEX_SYMBOLS) --request-interval $(MVP_REQUEST_INTERVAL) --request-retries $(MVP_REQUEST_RETRIES) --retry-backoff $(MVP_RETRY_BACKOFF)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data adjust --symbols-file $(MVP_UNIVERSE) --limit $(MVP_LIMIT) --daily-dir data/daily --adj-factor-dir data/adj_factor --mode qfq --output-dir data/qfq_daily
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli backtest --config configs/a_share_midterm.json --symbols-file $(MVP_UNIVERSE) --limit $(MVP_LIMIT) --data-dir data/qfq_daily --start-date $(MVP_START) --end-date $(MVP_END) --output-dir $(MVP_OUTPUT)/backtest
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli validate --config configs/a_share_midterm.json --symbols-file $(MVP_UNIVERSE) --limit $(MVP_LIMIT) --data-dir data/qfq_daily --start-date $(MVP_START) --end-date $(MVP_END) --split-date $(MVP_SPLIT) --output-dir $(MVP_OUTPUT)/validation
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli signal --config configs/a_share_midterm.json --symbols-file $(MVP_UNIVERSE) --limit $(MVP_LIMIT) --data-dir data/qfq_daily --start-date $(MVP_START) --end-date $(MVP_END) --output-dir $(MVP_OUTPUT)/signal --portfolio configs/live_portfolio.example.json

real-mvp-liquid:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data universe --stock-basic data/stocks/stock_basic.csv --output $(MVP_CANDIDATE_UNIVERSE) --as-of-date $(MVP_END) --min-listed-days 180 --limit $(MVP_CANDIDATE_LIMIT)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data sync --provider tushare --symbols-file $(MVP_CANDIDATE_UNIVERSE) --limit $(MVP_CANDIDATE_LIMIT) --start-date $(MVP_START) --end-date $(MVP_END) --cache-dir data/daily --with-adj-factor --with-constraints --index-symbols $(MVP_INDEX_SYMBOLS) --request-interval $(MVP_REQUEST_INTERVAL) --request-retries $(MVP_REQUEST_RETRIES) --retry-backoff $(MVP_RETRY_BACKOFF)
	$(MAKE) PYTHON=$(PYTHON) real-mvp-liquid-local MVP_LIMIT=$(MVP_LIMIT) MVP_LIQUID_UNIVERSE=$(MVP_LIQUID_UNIVERSE) MVP_LIQUID_OUTPUT=$(MVP_LIQUID_OUTPUT) MVP_LIQUIDITY_WINDOW=$(MVP_LIQUIDITY_WINDOW) MVP_LIQUID_MIN_AVG_AMOUNT=$(MVP_LIQUID_MIN_AVG_AMOUNT) MVP_START=$(MVP_START) MVP_END=$(MVP_END) MVP_SPLIT=$(MVP_SPLIT)

real-mvp-liquid-long:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data universe --stock-basic data/stocks/stock_basic.csv --output $(MVP_CANDIDATE_UNIVERSE) --as-of-date $(MVP_END) --min-listed-days 180 --limit $(MVP_CANDIDATE_LIMIT)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data sync --provider tushare --symbols-file $(MVP_CANDIDATE_UNIVERSE) --limit $(MVP_CANDIDATE_LIMIT) --start-date $(MVP_LONG_START) --end-date $(MVP_END) --cache-dir data/daily --with-adj-factor --with-constraints --index-symbols $(MVP_INDEX_SYMBOLS) --request-interval $(MVP_REQUEST_INTERVAL) --request-retries $(MVP_REQUEST_RETRIES) --retry-backoff $(MVP_RETRY_BACKOFF)
	$(MAKE) PYTHON=$(PYTHON) real-mvp-liquid-local MVP_LIMIT=$(MVP_LIMIT) MVP_LIQUID_UNIVERSE=$(MVP_LIQUID_UNIVERSE) MVP_LIQUID_OUTPUT=$(MVP_LIQUID_LONG_OUTPUT) MVP_LIQUIDITY_WINDOW=$(MVP_LIQUIDITY_WINDOW) MVP_LIQUID_MIN_AVG_AMOUNT=$(MVP_LIQUID_MIN_AVG_AMOUNT) MVP_START=$(MVP_LONG_START) MVP_END=$(MVP_END) MVP_SPLIT=$(MVP_LONG_SPLIT)

real-mvp-liquid-local:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data universe --stock-basic data/stocks/stock_basic.csv --output $(MVP_LIQUID_UNIVERSE) --as-of-date $(MVP_END) --min-listed-days 180 --daily-dir data/daily --liquidity-window $(MVP_LIQUIDITY_WINDOW) --min-avg-amount $(MVP_LIQUID_MIN_AVG_AMOUNT) --sort-by avg_amount --limit $(MVP_LIMIT)
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli data adjust --symbols-file $(MVP_LIQUID_UNIVERSE) --limit $(MVP_LIMIT) --daily-dir data/daily --adj-factor-dir data/adj_factor --mode qfq --output-dir data/qfq_daily
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli backtest --config configs/a_share_midterm.json --symbols-file $(MVP_LIQUID_UNIVERSE) --limit $(MVP_LIMIT) --data-dir data/qfq_daily --start-date $(MVP_START) --end-date $(MVP_END) --output-dir $(MVP_LIQUID_OUTPUT)/backtest
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli validate --config configs/a_share_midterm.json --symbols-file $(MVP_LIQUID_UNIVERSE) --limit $(MVP_LIMIT) --data-dir data/qfq_daily --start-date $(MVP_START) --end-date $(MVP_END) --split-date $(MVP_SPLIT) --output-dir $(MVP_LIQUID_OUTPUT)/validation
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli signal --config configs/a_share_midterm.json --symbols-file $(MVP_LIQUID_UNIVERSE) --limit $(MVP_LIMIT) --data-dir data/qfq_daily --start-date $(MVP_START) --end-date $(MVP_END) --output-dir $(MVP_LIQUID_OUTPUT)/signal --portfolio configs/live_portfolio.example.json

real-mvp-fills:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli fills reconcile --orders $(MVP_OUTPUT)/signal/manual_orders.csv --fills $(MVP_FILLS) --output $(MVP_OUTPUT)/fill_reconciliation.csv
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli fills replay --fills $(MVP_FILLS) --initial-cash $(MVP_INITIAL_CASH) --output-dir $(MVP_OUTPUT)/fill_replay
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli fills track --orders $(MVP_OUTPUT)/signal/manual_orders.csv --fills $(MVP_FILLS) --output $(MVP_OUTPUT)/tracking_diff.csv
