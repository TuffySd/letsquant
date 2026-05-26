# 数据源规划

最近核对日期：2026-05-26。数据服务的价格、权限、限流和字段覆盖变化较快，采购前需要以官方页面为准。

## 第一阶段：本地 CSV

当前项目先支持本地 CSV，适合验证回测框架、策略逻辑、成本模型和信号输出。

## 第二阶段：Tushare Pro

建议优先考虑 Tushare Pro，原因是 A 股日线、复权因子、基础资料、停复牌、财务数据等接口比较贴近个人量化研究。项目已经预留 `TushareDailySource` 骨架。

官方文档：https://tushare.pro/document/2

当前已支持同步日线 CSV：

```bash
pip install '.[tushare]'
export TUSHARE_TOKEN=你的_tushare_token
PYTHONPATH=src python -m letsquant.cli data sync \
  --provider tushare \
  --symbols 000001.SZ,000002.SZ \
  --start-date 2020-01-01 \
  --end-date 2024-12-31 \
  --cache-dir data/daily
```

配置约定：

- token 通过 `TUSHARE_TOKEN` 环境变量读取，不写入配置文件。
- 输出仍是每只股票一个 CSV，字段兼容当前 `CsvBarSource`。
- `--config` 可复用配置文件中的 `data_dir`、`symbols`、`start_date` 和 `end_date`。

需要的数据：

- 日线行情：open、high、low、close、vol、amount。
- 复权因子：用于生成前复权价格。
- 股票基础信息：上市日期、市场、名称、是否退市。
- 停复牌、涨跌停、ST 状态。
- 指数行情：沪深 300、中证 500、中证 1000 等基准。

## 备选数据源

- AkShare：免费，适合探索和临时补数，但生产稳定性、字段一致性和限流需要额外验证；当前官方仓库要求 Python 3.9+，本项目运行环境是 Python 3.8，接入前需要升级环境。
- 聚宽 JQData：研究环境友好，适合策略研究和因子数据，但需要确认本地化、导出和授权方式。
- AShareHub：REST API 形态简单，覆盖日线、复权因子、涨跌停、交易日历、财务等接口，可作为轻量备选。
- Wind / Choice：机构级，质量强但成本高，当前资金阶段通常不优先。

参考链接：

- AkShare：https://github.com/akfamily/akshare
- 聚宽数据：https://www.joinquant.com/data
- AShareHub：https://asharehub.com/zh/docs

## 最小采购建议

如果只采购一项，先采购能稳定提供以下能力的数据源：

- A 股日线历史数据，至少 10 年。
- 前复权或复权因子。
- 停复牌和涨跌停状态。
- 基础股票列表和上市日期。
- 可通过 Python API 自动拉取并缓存。

有了这些，策略验证质量会显著高于只用裸 K 线。

## 暂不需要的基础设施

- Redis：当前是日线级研究和收盘后人工交易信号，本地 CSV 缓存更容易审计，也足够支撑下一阶段验证。
- 数据库：股票池扩大后可以再引入 SQLite/PostgreSQL；在复权、停复牌、涨跌停等字段稳定前，先不要过早增加存储复杂度。
- 任务队列：每日收盘后同步可以先用手工命令或 cron，等流程稳定后再评估 Celery/RQ 等。
