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
PYTHONPATH=src python -m letsquant.cli validate --config configs/sample_backtest.json --split-date 2024-02-15
PYTHONPATH=src python -m letsquant.cli signal --config configs/sample_backtest.json
PYTHONPATH=src python -m letsquant.cli signal --config configs/sample_backtest.json --portfolio configs/live_portfolio.example.json
PYTHONPATH=src python -m letsquant.cli fills reconcile --orders results/manual_orders.csv --fills configs/fills.example.csv
PYTHONPATH=src python -m letsquant.cli fills replay --fills configs/fills.example.csv --initial-cash 100000
PYTHONPATH=src python -m letsquant.cli fills track --orders results/manual_orders.csv --fills configs/fills.example.csv
```

## 开发环境

建议使用项目内 conda 环境，避免把 Tushare、pandas 等依赖安装到宿主 Python：

```bash
.miniforge/micromamba create -y -p .conda/envs/letsquant -f environment.yml
make PYTHON=.conda/envs/letsquant/bin/python test
```

当前环境约定：

- Python：3.10。
- 本地环境目录：`.conda/envs/letsquant`，不进入 Git。
- token 只通过环境变量传入，不写入配置或仓库。

同步 Tushare 日线到本地 CSV 缓存：

```bash
pip install '.[tushare]'
export TUSHARE_TOKEN=你的_tushare_token
export TUSHARE_API_URL=https://tt.xiaodefa.cn  # 仅代理 token 需要
PYTHONPATH=src python -m letsquant.cli data probe --trade-date 2024-01-02
PYTHONPATH=src python -m letsquant.cli data sync \
  --provider tushare \
  --symbols 000001.SZ,000002.SZ \
  --start-date 2020-01-01 \
  --end-date 2024-12-31 \
  --cache-dir data/daily \
  --with-adj-factor \
  --with-constraints \
  --with-stock-basic \
  --index-symbols 000300.SH,000905.SH \
  --request-retries 3 \
  --retry-backoff 1.0
```

也可以用配置文件补齐 `data_dir`、`symbols` 和日期范围：

```bash
PYTHONPATH=src python -m letsquant.cli data sync --config configs/a_share_midterm.json --symbols 000001.SZ
```

生成前复权或后复权日线：

```bash
PYTHONPATH=src python -m letsquant.cli data adjust \
  --symbols 000001.SZ,000002.SZ \
  --daily-dir data/daily \
  --adj-factor-dir data/adj_factor \
  --mode qfq \
  --output-dir data/qfq_daily
```

生成股票池文件：

```bash
PYTHONPATH=src python -m letsquant.cli data universe \
  --stock-basic data/stocks/stock_basic.csv \
  --output data/universe/default.csv \
  --as-of-date 2024-01-05 \
  --min-listed-days 180 \
  --daily-dir data/daily \
  --liquidity-window 20 \
  --min-avg-amount 50000000 \
  --limit 50
```

生成后的 `data/universe/default.csv` 可以直接作为 `data sync --symbols-file` 输入。

用股票池和复权行情直接覆盖配置运行：

```bash
PYTHONPATH=src python -m letsquant.cli backtest \
  --config configs/a_share_midterm.json \
  --symbols-file data/universe/default.csv \
  --limit 50 \
  --data-dir data/qfq_daily \
  --benchmark-symbol 000300.SH \
  --benchmark-dir data/index_daily \
  --output-dir results/real_backtest

PYTHONPATH=src python -m letsquant.cli validate \
  --config configs/a_share_midterm.json \
  --symbols-file data/universe/default.csv \
  --limit 50 \
  --data-dir data/qfq_daily \
  --split-date 2023-12-29 \
  --output-dir results/real_validation

PYTHONPATH=src python -m letsquant.cli signal \
  --config configs/a_share_midterm.json \
  --symbols-file data/universe/default.csv \
  --limit 50 \
  --data-dir data/qfq_daily \
  --portfolio configs/live_portfolio.example.json \
  --output-dir results/real_signal
```

跑一个最小真实数据 smoke：

```bash
make PYTHON=.conda/envs/letsquant/bin/python real-smoke
```

该命令复用本地 `data/stocks/stock_basic.csv`。如果需要刷新股票基础信息，先单独运行：

```bash
make PYTHON=.conda/envs/letsquant/bin/python real-refresh-stock-basic
```

`real-smoke` 默认只跑 `REAL_LIMIT=5`、`REAL_START=2024-01-02` 到 `REAL_END=2024-01-05`，用于验证端到端流程。扩大范围时可以覆盖变量，例如：

```bash
make PYTHON=.conda/envs/letsquant/bin/python real-smoke REAL_LIMIT=20 REAL_START=2023-01-01 REAL_END=2024-12-31
```

跑 MVP 主体全链路：

```bash
export TUSHARE_TOKEN=你的_tushare_token
export TUSHARE_API_URL=https://tt.xiaodefa.cn  # 仅代理 token 需要
make PYTHON=.conda/envs/letsquant/bin/python real-mvp
```

默认会跑 `MVP_LIMIT=20` 只股票，区间为 `MVP_START=2023-01-01` 到 `MVP_END=2024-12-31`，并用 `MVP_SPLIT=2023-12-29` 做样本内/样本外验证。输出位于 `results/real_mvp/`：

- `backtest/`：完整区间回测和基准对比。
- `validation/`：样本内/样本外验证。
- `signal/`：最新人工交易信号和 `manual_orders.csv`。

扩大到 50 只股票时可以覆盖输出目录，避免覆盖 20 只 MVP 结果：

```bash
make PYTHON=.conda/envs/letsquant/bin/python real-mvp \
  MVP_LIMIT=50 \
  MVP_UNIVERSE=data/universe/mvp50.csv \
  MVP_OUTPUT=results/real_mvp50
```

真实接口默认 `MVP_REQUEST_RETRIES=3`、`MVP_RETRY_BACKOFF=1.0`，用于处理偶发 SSL 或代理连接抖动。

交易日后，有真实成交文件时继续跑：

```bash
make PYTHON=.conda/envs/letsquant/bin/python real-mvp-fills MVP_FILLS=path/to/fills.csv
```

该目标会生成成交对账、实际持仓回放和计划 vs 实际跟踪误差。

回测结果默认输出到 `results/`：

- `metrics.json`：收益、回撤、Calmar、夏普、交易次数、胜率、平均持仓天数、换手率、年度收益和月度收益等指标。
- 真实配置默认从 `data/index_daily/000300.SH.csv` 读取沪深 300 基准，`metrics.json` 会追加 `benchmark_total_return`、`benchmark_max_drawdown`、`excess_total_return` 等对比指标。
- `validation_metrics.json`：`validate` 命令按 `--split-date` 输出样本内、样本外和稳健性摘要；两段明细分别写入 `in_sample/` 和 `out_sample/`。
- `trades.csv`：实际成交记录。
- `fill_reconciliation.csv`：`fills reconcile` 命令比较计划订单和真实成交，标记 `filled`、`partial`、`not_filled`、`overfilled`、`unplanned`，并计算股数差异、成交均价、滑点和费用。
- `fill_replay/positions.csv` 和 `fill_replay/summary.csv`：`fills replay` 命令用真实成交回放现金、持仓均价和已实现盈亏。
- `tracking_diff.csv`：`fills track` 命令按股票汇总计划订单和真实成交的净股数、现金流、成交金额和费用差异。
- `order_rejections.csv`：因停牌、涨停买入、跌停卖出等约束未成交的信号。
- `signals.csv`：历史信号记录。
- `equity_curve.csv`：每日权益曲线。
- `current_signals.csv`：当前最新收盘后的待确认人工指令。
- `manual_orders.csv`：包含建议股数、参考价格和人工复核备注的下单清单；备注会标出最新行情日是否停牌、是否收在涨跌停，并提示复核公告、新闻和财报日程。

Tushare 扩展缓存目录：

- `data/daily/`：日线行情；启用 `--with-constraints` 后会合并 `is_suspended`、`limit_up`、`limit_down`。
- `data/adj_factor/`：复权因子。
- `data/limits/`：按交易日缓存涨跌停价格。
- `data/suspensions/`：按交易日缓存停复牌信息。
- `data/stocks/`：股票基础信息。
- `data/index_daily/`：指数日线行情。
- `data/qfq_daily/`：前复权日线行情，可作为回测 `data_dir`。
- `data/hfq_daily/`：后复权日线行情。
- `data/universe/`：股票池 CSV，支持作为批量同步输入。

`data/limits/*.complete` 和 `data/suspensions/*.complete` 是日级约束缓存完成标记；同一日期范围复跑时会复用已完成缓存，减少重复接口请求。

## 数据格式

本地 CSV 放在 `data/sample/` 或你配置的目录下，每个股票一个文件，例如 `000001.SZ.csv`。支持以下字段名：

- 日期：`trade_date` 或 `date`，格式支持 `YYYYMMDD`、`YYYY-MM-DD`。
- 股票代码：文件名或字段 `ts_code` / `symbol`。
- 行情：`open`、`high`、`low`、`close`。
- 成交量：`vol` 或 `volume`。
- 成交额：`amount` 可选。
- 交易约束：`is_suspended` / `suspended` / `paused`、`limit_up` / `up_limit`、`limit_down` / `down_limit` 可选。

## 策略说明

初始策略是 `TrendBreakoutStrategy`：

- 入场：短中长期均线多头排列，收盘价突破前 N 日高点，动量为正，成交量不低于近期均量阈值。
- 出场：跌破中期均线、触发固定止损、触发移动止盈、超过最长持仓天数。
- 执行：第 T 日收盘后生成信号，第 T+1 个可交易日按开盘价加滑点成交；若数据标记停牌、涨停买入或跌停卖出，则记录为拒单。

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

## 实盘成交回填

人工下单后，可以把真实成交记录保存为 CSV，再和 `manual_orders.csv` 对账：

```bash
PYTHONPATH=src python -m letsquant.cli fills reconcile \
  --orders results/manual_orders.csv \
  --fills configs/fills.example.csv \
  --output results/fill_reconciliation.csv

PYTHONPATH=src python -m letsquant.cli fills replay \
  --fills configs/fills.example.csv \
  --initial-cash 100000 \
  --output-dir results/fill_replay

PYTHONPATH=src python -m letsquant.cli fills track \
  --orders results/manual_orders.csv \
  --fills configs/fills.example.csv \
  --output results/tracking_diff.csv
```

`fills.csv` 字段：

- `signal_date`：信号日期，用于匹配 `manual_orders.csv`。
- `trade_date`：实际成交日期。
- `symbol`、`action`、`shares`、`price`：成交股票、方向、股数和价格。
- `commission`、`stamp_tax`、`transfer_fee`：实际费用，可填 0。
- `note`：可选备注。

`fills replay` 会按成交日期排序回放成交，买入增加持仓并更新平均成本，卖出减少持仓并计算已实现盈亏；如果卖出股数超过当前持仓，会直接报错。

`fills track` 会按股票聚合计划订单和实际成交，输出 `matched`、`drift`、`not_filled`、`unplanned`，用于复盘执行偏差。

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

## 当前需要准备的资源

- Tushare Pro token：用于自动同步真实 A 股日线数据。token 只通过 `TUSHARE_TOKEN` 环境变量传入，不要写入配置文件或仓库。
- Tushare 权限/积分：至少需要覆盖日线行情接口；后续还会需要复权因子、股票基础信息、停复牌、涨跌停和指数行情。
- Redis：当前阶段不需要。日线级中短期研究先用本地 CSV 缓存，等引入 Web 服务、任务队列或并发数据抓取后再评估。
