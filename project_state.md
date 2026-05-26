# Project State

更新时间：2026-05-26

## 项目目标

LetsQuant 是一个面向 A 股中短期策略的量化研究、回测和人工交易信号系统。

当前资金规模按 100,000 元人民币设计，暂不接券商交易 API。系统目标是：

- 使用稳定数据源做历史回测和持续策略验证。
- 收盘后生成次日可人工执行的买入/卖出指令。
- 支持后续逐步接入 Tushare、聚宽、AShareHub 等数据源。
- 优先保证可验证、可复盘、可演进，避免一开始做成黑箱策略。

## 当前已完成

### 项目结构

已建立 Python 项目骨架：

- `src/letsquant/`：核心代码。
- `configs/`：回测和实盘持仓配置。
- `data/sample/`：示例行情 CSV。
- `tests/`：单元测试。
- `docs/`：策略和数据源文档。
- `results/`：运行后生成的回测和信号输出目录。

主要入口：

- `PYTHONPATH=src python -m letsquant.cli backtest --config configs/sample_backtest.json`
- `PYTHONPATH=src python -m letsquant.cli signal --config configs/sample_backtest.json`
- `make test`
- `make backtest`
- `make signal`
- `make compile`

### 数据层

已实现本地 CSV 数据源：

- 文件：`src/letsquant/data/csv_source.py`
- 每个股票一个 CSV，例如 `data/sample/000001.SZ.csv`
- 支持字段：`trade_date/date`、`ts_code/symbol`、`open`、`high`、`low`、`close`、`vol/volume`、`amount`
- 支持日期过滤、排序、重复日期检查

已预留 Tushare 数据源骨架：

- 文件：`src/letsquant/data/tushare_source.py`
- 当前未强制依赖 Tushare，避免没有 token 时项目无法运行。
- 后续安装可选依赖：`pip install '.[tushare]'`

### 策略层

已实现第一条基准策略 `TrendBreakoutStrategy`：

- 文件：`src/letsquant/strategies/trend_breakout.py`
- 入场逻辑：
  - 短、中、长期均线多头排列
  - 收盘价突破前 N 日高点
  - N 日动量大于阈值
  - 成交量不低于近期均量阈值
- 出场逻辑：
  - 固定止损
  - 移动止盈
  - 跌破中期均线
  - 超过最长持仓天数

重要约束：这只是基准策略，用于验证框架，不是最终投资策略。

### 回测层

已实现事件式日线回测引擎：

- 文件：`src/letsquant/execution/backtester.py`
- 第 T 日收盘后生成信号
- 第 T+1 个可交易日按开盘价成交
- 支持：
  - 初始资金
  - 现金余额
  - 持仓市值
  - 账户权益曲线
  - 最大回撤
  - 年化收益
  - 夏普比率
  - 交易记录
  - 胜率

已加入 A 股交易约束：

- 100 股整手
- 单票目标仓位上限
- 最大持仓数
- 现金保留比例
- 买卖滑点
- 佣金
- 最低佣金
- 卖出印花税
- 过户费

### 人工交易指令层

已实现人工下单清单生成：

- 文件：`src/letsquant/execution/instructions.py`
- 输出：`results/manual_orders.csv`
- 包含：
  - 信号日期
  - 股票代码
  - 买入/卖出方向
  - 建议股数
  - 参考价格
  - 估算成交金额
  - 策略原因
  - 人工复核备注

卖出信号会读取实盘持仓文件中的股数。买入信号会根据现金、仓位上限、滑点和 100 股整手估算建议股数。

实盘持仓模板：

- `configs/live_portfolio.example.json`

### 配置与示例

已建立两个配置：

- `configs/sample_backtest.json`：使用样例数据的可运行配置
- `configs/a_share_midterm.json`：面向真实 A 股数据的中短期默认配置

示例数据：

- `data/sample/000001.SZ.csv`

样例回测输出：

- `results/metrics.json`
- `results/trades.csv`
- `results/signals.csv`
- `results/equity_curve.csv`
- `results/current_signals.csv`
- `results/manual_orders.csv`

### 文档

已写入：

- `README.md`：项目定位、快速开始、数据格式、策略说明、风控默认值
- `docs/strategy_playbook.md`：策略验证纪律、每日人工执行流程、后续约束
- `docs/data_providers.md`：数据源规划、Tushare/AkShare/聚宽/AShareHub 判断
- `docs/git_workflow.md`：Git 本地仓库、分支、里程碑提交和 GitHub 凭据安全要求

### Git 仓库

当前环境将标准 `.git` 路径挂载为只读空目录，普通 `git init` 无法使用标准 `.git` 目录。因此项目使用 `.git-local/` 作为本地 Git 元数据目录。

当前 Git 命令格式：

```bash
git --git-dir=.git-local --work-tree=. status
git --git-dir=.git-local --work-tree=. log --oneline --decorate --graph --all
```

也可以使用包装脚本：

```bash
scripts/git-local status
scripts/git-local log --oneline --decorate --graph --all
```

本地 Git 用户配置：

- `user.email`: `shendan_sd@126.com`
- `user.name`: `shendan_sd`

安全要求：

- 不允许把 GitHub 密码、token、SSH 私钥或其他凭据写入 `docs/`、`project_state.md`、配置文件或提交历史。
- GitHub 远程建议使用 SSH、GitHub CLI 或 credential manager。
- 如果凭据在聊天或日志中暴露，需要立即修改密码并检查账号安全。

## 已验证命令

以下命令已通过：

```bash
make test
make compile
make backtest
PYTHONPATH=src python -m letsquant.cli signal --config configs/sample_backtest.json --portfolio configs/live_portfolio.example.json
```

当前测试：

- `tests/test_indicators.py`
- `tests/test_backtester.py`
- `tests/test_instructions.py`

测试数量：5 个，全部通过。

样例回测结果：

- 初始资金：100,000
- 最终权益：100,672.56
- 总收益：0.67%
- 最大回撤：-1.29%
- 交易次数：2
- 卖出交易数：1
- 胜率：100%

注意：样例数据是为了验证系统闭环，不能代表真实策略表现。

## 数据源判断

最近核对日期：2026-05-26。

优先建议：

1. Tushare Pro
   - 优先级最高。
   - 适合先采购或申请。
   - 需要日线、复权因子、股票基础信息、停复牌、涨跌停、指数行情。

2. AShareHub
   - REST API 形态简单，可作为轻量备选。

3. 聚宽 JQData
   - 研究环境友好，但需要确认本地 API、导出和授权方式。

4. AkShare
   - 免费，适合补充和探索。
   - 当前官方仓库要求 Python 3.9+，本项目当前环境是 Python 3.8，接入前要么升级环境，要么只在单独环境使用。

参考链接：

- Tushare：https://tushare.pro/document/2
- AkShare：https://github.com/akfamily/akshare
- 聚宽：https://www.joinquant.com/data
- AShareHub：https://asharehub.com/zh/docs

## 当前限制

当前版本还没有处理以下真实 A 股约束：

- 前复权/后复权价格处理
- 停牌
- 涨跌停无法成交
- ST、退市整理、上市未满 N 日过滤
- 成交额和流动性股票池过滤
- 指数基准对比
- 行业暴露
- 多股票真实股票池批量回测
- 样本内/样本外切分
- 滚动参数验证
- 实盘成交回填和跟踪误差分析

这些是后续策略可信度提升的关键。

## 后续计划

### P0：数据接入与缓存

目标：拿到真实 A 股历史数据，替换样例 CSV。

要做：

- 确认并采购/配置数据源，优先 Tushare Pro。
- 实现数据下载命令，例如 `letsquant data sync`。
- 建立本地缓存目录 `data/cache/` 或 `data/daily/`。
- 统一字段为项目内部 `Bar` 模型。
- 下载并保存：
  - 日线行情
  - 复权因子
  - 股票基础信息
  - 停复牌
  - 涨跌停
  - 指数行情

验收标准：

- 可以指定股票池和日期范围自动更新数据。
- 回测不再依赖手工 CSV。

### Git 里程碑要求

每个新里程碑开始时创建分支：

```bash
git --git-dir=.git-local --work-tree=. checkout -b milestone/<date>-<topic>
```

每个里程碑完成时：

- 运行 `make test`
- 运行 `make compile`
- 如果涉及回测、策略或信号输出，运行 `make backtest` 和 `make signal`
- 更新 `project_state.md`
- 提交所有相关变更
- 合并回 `main`
- 如果远程仓库已配置，推送 `main` 和里程碑分支

### P1：真实市场约束

目标：让回测更接近真实可交易结果。

要做：

- 前复权价格生成或读取。
- 停牌日跳过成交。
- 涨停不能买入，跌停不能卖出。
- ST 和退市风险过滤。
- 上市未满 N 日过滤。
- 日均成交额过滤。
- 股票池生成器。

验收标准：

- 回测成交记录能标记未成交原因。
- 策略不会买入明显不可交易标的。

### P2：策略验证框架

目标：避免过拟合，建立可比较的策略迭代流程。

要做：

- 指数基准收益对比。
- 样本内/样本外切分。
- 滚动窗口回测。
- 参数网格搜索，但限制复杂度。
- 增加指标：
  - Calmar
  - 年度收益
  - 月度收益
  - 最大连续亏损
  - 平均持仓天数
  - 换手率

验收标准：

- 每次策略修改都能生成可比较的报告。

### P3：每日运行流程

目标：形成收盘后可执行的固定工作流。

要做：

- 每日更新行情数据。
- 读取真实持仓文件。
- 输出 `manual_orders.csv`。
- 增加人工复核清单：
  - 是否停牌
  - 是否涨跌停
  - 是否有重大公告
  - 是否财报/业绩预告临近
- 支持记录真实成交价。

验收标准：

- 每天收盘后运行一个命令即可生成次日操作清单。

### P4：策略扩展

候选策略方向：

- 趋势突破 + 市场环境过滤
- 中证 500 / 中证 1000 股票池动量轮动
- 低波动趋势跟随
- 回撤后再突破
- 基本面质量过滤 + 技术择时

原则：

- 每个新策略必须和 `TrendBreakoutStrategy` 同框架对比。
- 不允许只根据单次回测收益决定上线。
- 当前资金 10 万，策略应控制换手率和持仓数量。

## 新 session 恢复建议

新 session 开始时，可以直接让 Codex 读取：

```bash
sed -n '1,240p' project_state.md
rg --files
```

然后优先继续：

1. 接入 Tushare 或选定数据源。
2. 实现真实数据缓存。
3. 加入复权、停牌、涨跌停和股票池过滤。
4. 使用真实股票池跑第一轮样本外回测。

## 风险提示

本项目是量化研究和辅助决策工具，不构成投资建议。任何输出的买入/卖出信号都需要人工复核，并结合资金情况、市场环境、公告事件和风险承受能力判断。
