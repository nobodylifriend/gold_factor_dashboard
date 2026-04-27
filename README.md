# gold_price_analysis

这个仓库当前已经实现了两条数据准备链路：

1. `FRED` 宏观与金融指标抓取、初始化和日更
2. `XAU/USD` 黄金价格数据补充抓取和日更

目标是为《[黄金价格预测.md](/D:/note/pandas_project/gold_price_analysis/黄金价格预测.md)》里的黄金价格预测做一期可复用的数据准备。

## 当前项目结构

```text
gold_price_analysis/
├─ .env
├─ README.md
├─ 黄金价格预测.md
├─ config/
│  └─ indicators.yml
├─ gold_data/
│  ├─ __init__.py
│  └─ __main__.py
├─ src/
│  └─ gold_data/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ fred.py
│     ├─ pipeline.py
│     └─ storage.py
├─ scripts/
│  ├─ run_daily_update.ps1
│  └─ fetch_xau_data.py
├─ data/
│  ├─ fred/
│  │  ├─ _catalog.csv
│  │  └─ <类别>/<指标名>.csv
│  └─ xau/
│     ├─ xau_usd_daily_ohlc.csv
│     ├─ xau_usd_monthly_close.csv
│     └─ manifest.json
└─ tests/
   └─ test_pipeline.py
```

## 环境约定

- Python: `3.12`
- 已使用依赖：
  - `pandas`
  - `requests`
  - `PyYAML`
- FRED key 存放在根目录 `.env`

`.env` 最少需要：

```env
FRED_API_KEY=你的_fred_api_key
```

## FRED 数据链路

### 命令入口

初始化历史数据：

```powershell
python -m gold_data init
```

日更：

```powershell
python -m gold_data update
```

CLI 实现在：
- [gold_data/__main__.py](/D:/note/pandas_project/gold_price_analysis/gold_data/__main__.py)
- [src/gold_data/cli.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/cli.py)

### 配置文件

FRED 指标配置唯一事实源：

- [config/indicators.yml](/D:/note/pandas_project/gold_price_analysis/config/indicators.yml)

字段约定：

- `category`
- `indicator_name`
- `source`
- `series_id`
- `series_type`
- `frequency`
- `start_date`
- `enabled`
- `status`
- `update_window_days`
- `formula`（仅派生指标）
- `dependencies`（仅派生指标）

### 当前 FRED 已启用指标

#### 通胀 / 通胀预期

- `CPI` -> `CPIAUCSL`
- `核心CPI` -> `CPILFESL`
- `PCE` -> `PCEPI`
- `核心PCE` -> `PCEPILFE`
- `PPI` -> `PPIACO`
- `GDP平减指数` -> `GDPDEF`
- `密歇根大学1年通胀预期` -> `MICH`
- `5年盈亏平衡通胀率` -> `T5YIE`
- `10年盈亏平衡通胀率` -> `T10YIE`
- `5年期5年期前瞻通胀预期` -> `T5YIFR`
- 派生：`10年期通胀预期_名义减实际` = `DGS10 - DFII10`

#### 名义利率

- `联邦基金利率` -> `FEDFUNDS`
- `SOFR` -> `SOFR`
- `3个月美债收益率` -> `TB3MS`
- `10年期美债收益率` -> `DGS10`
- `5年期TIPS实际收益率` -> `DFII5`
- `10年期TIPS实际收益率` -> `DFII10`
- `30年期TIPS实际收益率` -> `DFII30`

#### 真实利率

- 当前未单独维护分类；TIPS 实际收益率序列按项目口径统一归入 `名义利率`

#### 汇率

- `美元广义贸易加权指数` -> `DTWEXBGS`

#### 货币供应量指标

- `M1` -> `M1SL`
- `M2` -> `M2SL`
- `货币基础` -> `BOGMBASE`

#### 就业指标

- `非农就业人数` -> `PAYEMS`
- `失业率` -> `UNRATE`

#### 信用利差

- `投资级信用利差_OAS` -> `BAMLC0A0CM`
- `高收益信用利差_OAS` -> `BAMLH0A0HYM2`
- `TED利差` -> `TEDRATE`

#### 金融压力

- `圣路易斯金融压力指数` -> `STLFSI4`

#### 油价指标

- `WTI原油现货价` -> `DCOILWTICO`
- `Brent原油现货价` -> `DCOILBRENTEU`

#### 工业金属

- `铜价` -> `PCOPPUSDM`

### 当前 FRED 已延后但保留在配置中的典型指标

这些指标已在 `indicators.yml` 中保留，但当前为 `enabled: false, status: deferred`：

- SPF 通胀预期
- GLD 持仓
- COT 黄金净多头
- GVZ
- GPR Index

### FRED 存储约定

输出目录：

```text
data/fred/<类别>/<指标名称>.csv
```

示例：

- [data/fred/通胀_通胀预期/CPI.csv](/D:/note/pandas_project/gold_price_analysis/data/fred/通胀_通胀预期/CPI.csv)
- [data/fred/名义利率/10年期美债收益率.csv](/D:/note/pandas_project/gold_price_analysis/data/fred/名义利率/10年期美债收益率.csv)

每个 CSV 结构固定为：

```csv
date,value
```

清单文件：

- [data/fred/_catalog.csv](/D:/note/pandas_project/gold_price_analysis/data/fred/_catalog.csv)

字段：

```csv
category,indicator_name,source,series_id,frequency,units,enabled,status,file_path
```

### FRED 更新策略

当前统一按回补窗口增量更新：

- 日频：`30` 天
- 周频：`90` 天
- 月频：`540` 天
- 季频：`720` 天

原因：允许 FRED 历史值修订后在日更中被覆盖。

### FRED 抓取实现位置

- 配置解析与校验：
  - [src/gold_data/config.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/config.py)
- FRED HTTP 客户端：
  - [src/gold_data/fred.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/fred.py)
- init / update 主流程：
  - [src/gold_data/pipeline.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/pipeline.py)
- CSV 读写与 merge：
  - [src/gold_data/storage.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/storage.py)

## XAU/USD 数据链路

### 脚本入口

- [scripts/fetch_xau_data.py](/D:/note/pandas_project/gold_price_analysis/scripts/fetch_xau_data.py)

手动执行：

```powershell
python .\scripts\fetch_xau_data.py
```

### XAU 输出目录

- [data/xau/xau_usd_daily_ohlc.csv](/D:/note/pandas_project/gold_price_analysis/data/xau/xau_usd_daily_ohlc.csv)
- [data/xau/xau_usd_monthly_close.csv](/D:/note/pandas_project/gold_price_analysis/data/xau/xau_usd_monthly_close.csv)
- [data/xau/manifest.json](/D:/note/pandas_project/gold_price_analysis/data/xau/manifest.json)

### XAU 当前数据覆盖

#### 日线 OHLC

- 文件：`xau_usd_daily_ohlc.csv`
- 覆盖：`2006-04-25` 到 `2026-04-24`
- 列：

```csv
date,open,high,low,close,volume,source
```

#### 月度收盘价

- 文件：`xau_usd_monthly_close.csv`
- 覆盖：`2006-05-01` 到 `2026-04-01`
- 列：

```csv
date,close,source
```

#### Manifest

- 文件：`manifest.json`
- 用来记录生成时间、覆盖区间、行数、来源说明

### XAU 数据来源与合并逻辑

当前 `XAU/USD` 免费公开数据源不够干净，因此采用多源拼接：

1. `huggingface:kafka7:1d`
   - `XAU_1d_data.jsonl`
   - 提供历史主干日线

2. `huggingface:fokan:DAT_MT_XAUUSD_M1_2025.csv`
   - 分钟线聚合成日线

3. `huggingface:fokan:DAT_MT_XAUUSD_M1_202601.csv`
   - 2026 年 1 月分钟线聚合成日线

4. `investing:next-data:recent-window`
   - 使用 `https://www.investing.com/_next/data/.../xau-usd-historical-data.json`
   - 提供最近窗口日线

5. `macrotrends:monthly`
   - 使用 `https://www.macrotrends.net/economic-data/1333/5/D`
   - 提供月度收盘价序列

合并规则：

- 按 `date` 去重
- 同一天多来源冲突时保留后写入来源
- 最终保留 `source` 列，方便回溯

### XAU 已知边界

当前免费源组合下，`XAU/USD` 的完整 20 年日线仍然不是单一官方源。

当前版本的特点：

- `2006-04-25` 到 `2026-04-24` 已有一份可直接使用的日线文件
- `manifest.json` 明确写了覆盖说明
- 如果后续要直接用于严格日频建模，建议补一轮：
  - 交易日完整性检查
  - 缺口报告
  - 来源冲突比对

## 每日调度

统一调度脚本：

- [scripts/run_daily_update.ps1](/D:/note/pandas_project/gold_price_analysis/scripts/run_daily_update.ps1)

当前脚本行为：

1. 切到项目根目录
2. 设置代理
3. 执行 `python -m gold_data update`
4. 若成功，继续执行 `python .\scripts\fetch_xau_data.py`
5. 任一步失败则退出非零

脚本内容核心如下：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:4780"
$env:HTTPS_PROXY = "http://127.0.0.1:4780"
$env:http_proxy = "http://127.0.0.1:4780"
$env:https_proxy = "http://127.0.0.1:4780"
python -m gold_data update
python .\scripts\fetch_xau_data.py
```

手动运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_update.ps1
```

Windows 计划任务示例：

```powershell
schtasks /Create /SC DAILY /ST 08:00 /TN "gold-price-fred-update" /TR "powershell -ExecutionPolicy Bypass -File D:\note\pandas_project\gold_price_analysis\scripts\run_daily_update.ps1"
```

## 代理约定

当前项目默认通过本地代理联网：

```powershell
set proxy http://127.0.0.1:4780
set https-proxy http://127.0.0.1:4780
```

在 PowerShell 中实际使用的是：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:4780"
$env:HTTPS_PROXY = "http://127.0.0.1:4780"
$env:http_proxy = "http://127.0.0.1:4780"
$env:https_proxy = "http://127.0.0.1:4780"
```

如果后续新对话里下载失败，优先检查是不是没有带上这组代理环境变量。

## 当前历史范围

本仓库当前数据初始化基准范围是：

- 开始日期：`2006-04-25`
- 设计目标：过去 20 年

这个起点已经同步到：

- `config/indicators.yml`
- `scripts/fetch_xau_data.py`
- `data/xau/manifest.json`

## 测试

已写单元测试：

- [tests/test_pipeline.py](/D:/note/pandas_project/gold_price_analysis/tests/test_pipeline.py)

执行：

```powershell
python -m unittest discover -s tests -v
```

覆盖内容：

- `indicators.yml` 校验
- `init` 输出 CSV 和 catalog
- `update` 幂等
- 派生指标生成
- 缺失 `FRED_API_KEY`
- 单个 series 失败但其他继续执行

## 如果下次开新对话，建议直接这样说

可以直接贴这段，让新对话快速接手：

```text
请先阅读 README.md。这个项目已经有：
1. FRED 指标抓取链路（python -m gold_data init/update）
2. XAU/USD 抓取脚本（scripts/fetch_xau_data.py）
3. 每日调度脚本（scripts/run_daily_update.ps1）

代理固定用 http://127.0.0.1:4780。
请基于现有结构继续，不要重做脚手架。
```

## 下一步最合理的工作

如果继续做黄金预测数据准备，优先级建议是：

1. 给 `XAU/USD` 日线做交易日完整性检查和缺口报告
2. 把 `XAU/USD` 也纳入统一 catalog
3. 给 FRED 和 XAU 增加统一的数据质量检查脚本
4. 再扩到 deferred 指标，比如 GLD、COT、GVZ、GPR

## Unified indicator access

The repo now has a unified indicator registry and query layer for both `FRED` and `XAU/USD`.

### Generated files

- [data/indicator_catalog.csv](/D:/note/pandas_project/gold_price_analysis/data/indicator_catalog.csv)
- [data/indicator_catalog.md](/D:/note/pandas_project/gold_price_analysis/data/indicator_catalog.md)

`data/indicator_catalog.csv` includes:

```csv
indicator_id,category,indicator_name,english_code,source,frequency,file_path,definition,status,enabled
```

It is generated from:

- `config/indicators.yml`
- `data/fred/_catalog.csv`
- `data/xau/manifest.json`

### Refresh catalog

```powershell
python -m gold_data catalog
```

The catalog is also refreshed automatically after:

- `python -m gold_data init`
- `python -m gold_data update`
- `python .\scripts\fetch_xau_data.py`

### Query API

Code location:

- [src/gold_data/access.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/access.py)
- [src/gold_data/catalog.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/catalog.py)
- [src/gold_data/metadata.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/metadata.py)

Usage:

```python
from pathlib import Path

from src.gold_data.access import IndicatorStore

store = IndicatorStore(Path(r"D:\note\pandas_project\gold_price_analysis"))

# 1) query metadata
items = store.list_indicators(
    indicator_id="DGS10",
    category="名义利率",
    name="美债收益率",
    frequency="d",
)

# 2) get one indicator
frame = store.get_one(
    indicator_id="DGS10",
    start_date="2020-01-01",
    end_date="2024-12-31",
)

# 3) get multiple indicators
result = store.get_data(
    category="通胀 / 通胀预期",
    frequency="d",
    start_date="2024-01-01",
    end_date="2024-12-31",
)
```

Filter behavior:

- `indicator_id`: exact match, case-insensitive
- `category`: exact match
- `name`: substring match against `indicator_name` and `english_code`
- `frequency`: exact match, case-insensitive
- `start_date` / `end_date`: applied on the `date` column

Return behavior:

- `get_one(...)` returns a single `pandas.DataFrame`
- `get_data(...)` returns `dict[indicator_id, pandas.DataFrame]`
- by default returned frames include:
  - `indicator_id`
  - `category`
  - `indicator_name`
  - `frequency`
  - `source`

### Current unified IDs

Examples:

- `DGS10`
- `DFII10`
- `CPIAUCSL`
- `T10YIE`
- `XAU_USD_DAILY_OHLC`
- `XAU_USD_MONTHLY_CLOSE`
- `DERIVED__10年期通胀预期_名义减实际`

## Inflation rate transforms

The raw price-index series are still stored, but the pipeline now also generates rate-based derived indicators for:

- `CPI`
- `核心CPI`
- `PCE`
- `核心PCE`
- `PPI`
- `GDP平减指数`

For each of these series, the project now writes:

- `同比`
- `环比`
- `环比年化`

Examples:

- `CPIAUCSL_YOY`
- `CPIAUCSL_MOM`
- `CPIAUCSL_MOM_ANNUALIZED`
- `GDPDEF_YOY`
- `GDPDEF_QOQ`
- `GDPDEF_QOQ_ANNUALIZED`

Implementation notes:

- Derived-series engine: [src/gold_data/derived.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/derived.py)
- Config model: [src/gold_data/config.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/config.py)
- Pipeline orchestration: [src/gold_data/pipeline.py](/D:/note/pandas_project/gold_price_analysis/src/gold_data/pipeline.py)

Configuration pattern for extensibility:

- keep the raw source series as `series_type: direct`
- add a derived entry with `series_type: derived`
- set `derivation_method`
- set `dependencies`
- set `transform_params`

Supported derived methods right now:

- `expression`: multi-series arithmetic such as `DGS10 - DFII10`
- `pct_change`: single-series rate transforms such as YoY / MoM / annualized MoM

`pct_change` fields:

```yaml
series_type: derived
derivation_method: pct_change
dependencies:
  - CPI
transform_params:
  periods: 12
  annualize: false
```

Behavior:

- monthly YoY: `periods: 12`
- monthly MoM: `periods: 1`
- monthly annualized MoM: `periods: 1`, `annualize: true`
- quarterly YoY: `periods: 4`
- quarterly QoQ: `periods: 1`
- quarterly annualized QoQ: `periods: 1`, `annualize: true`

The daily update flow already rebuilds all derived indicators after refreshing direct FRED series, so no extra scheduler change is required.

For local rebuilds without hitting FRED again, use:

```powershell
python -m gold_data derive
```
