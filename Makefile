PYTHON ?= python
SRC_PATH ?= src

.PHONY: test backtest signal compile

test:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m unittest discover -s tests

backtest:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli backtest --config configs/sample_backtest.json

signal:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m letsquant.cli signal --config configs/sample_backtest.json --portfolio configs/live_portfolio.example.json

compile:
	PYTHONPATH=$(SRC_PATH) $(PYTHON) -m compileall src tests
