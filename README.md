# LetsQuant

LetsQuant 是一个面向 A 股中短期策略的研究、回测和人工交易信号项目。当前版本先建立可运行闭环：读取本地日线 CSV，执行趋势突破策略回测，并在收盘后输出次日可人工执行的买入/卖出指令。

## 当前定位

- 市场：A 股。
- 频率：中短期，日线级别，非高频。
- 资金规模默认：100,000 元人民币。
- 执行方式：系统产生信号，用户在券商交易软件中人工确认下单。
- 首要目标：稳定、可验证、可复盘，而不是快速堆策略。

## 快速开始

```bash
python -m unittest discover -s tests
PYTHONPATH=src python -m letsquant.cli backtest --config configs/sample_backtest.json
PYTHONPATH=src python -m letsquant.cli signal --config configs/sample_backtest.json
PYTHONPATH=src python -m letsquant.cli signal --config configs/sample_backtest.json --portfolio configs/live_portfolio.example.json
```

回测结果默认输出到 `results/`：

- `metrics.json`：收益、回撤、夏普、交易次数等指标。
- `trades.csv`：实际成交记录。
- `signals.csv`：历史信号记录。
- `equity_curve.csv`：每日权益曲线。
- `current_signals.csv`：当前最新收盘后的待确认人工指令。
- `manual_orders.csv`：包含建议股数和参考价格的人工下单清单。

## 数据格式

本地 CSV 放在 `data/sample/` 或你配置的目录下，每个股票一个文件，例如 `000001.SZ.csv`。支持以下字段名：

- 日期：`trade_date` 或 `date`，格式支持 `YYYYMMDD`、`YYYY-MM-DD`。
- 股票代码：文件名或字段 `ts_code` / `symbol`。
- 行情：`open`、`high`、`low`、`close`。
- 成交量：`vol` 或 `volume`。
- 成交额：`amount` 可选。

## 策略说明

初始策略是 `TrendBreakoutStrategy`：

- 入场：短中长期均线多头排列，收盘价突破前 N 日高点，动量为正，成交量不低于近期均量阈值。
- 出场：跌破中期均线、触发固定止损、触发移动止盈、超过最长持仓天数。
- 执行：第 T 日收盘后生成信号，第 T+1 个可交易日按开盘价加滑点成交。

这只是第一条基准线，用来验证数据、成本、风控和复盘流程。后续策略应该先和它做同一套回测对照。

## 实盘持仓文件

`signal` 命令可以读取一个可选持仓文件，用来区分空仓买入信号和已有持仓卖出信号：

```json
{
  "cash": 100000,
  "positions": {
    "000001.SZ": {
      "shares": 1700,
      "cost_basis": 11.24,
      "entry_date": "2024-02-05",
      "highest_close": 12.42,
      "last_price": 10.25
    }
  }
}
```

## 风控默认值

- 单票目标仓位：不超过总权益 20%。
- 最大同时持仓：5 只。
- 现金保留：5%。
- 买卖数量：按 A 股 100 股整手向下取整。
- 成本：佣金、最低佣金、卖出印花税、滑点均可配置。

## 后续演进

建议按以下顺序推进：

1. 接入稳定数据源，并建立本地缓存。
2. 扩展股票池过滤：ST、停牌、上市时间、成交额、涨跌停。
3. 加入复权、分红送转、指数基准和行业暴露。
4. 增加滚动样本外验证，避免只对历史过拟合。
5. 建立每日收盘后自动任务，输出人工交易清单。

更多细节见 `docs/strategy_playbook.md` 和 `docs/data_providers.md`。
