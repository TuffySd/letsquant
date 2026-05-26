.PHONY: test backtest signal compile

test:
	PYTHONPATH=src python -m unittest discover -s tests

backtest:
	PYTHONPATH=src python -m letsquant.cli backtest --config configs/sample_backtest.json

signal:
	PYTHONPATH=src python -m letsquant.cli signal --config configs/sample_backtest.json --portfolio configs/live_portfolio.example.json

compile:
	PYTHONPATH=src python -m compileall src tests
