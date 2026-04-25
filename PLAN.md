# 黄金价格预测数据准备一期方案（FRED 子集 + 日更）

## Summary

在当前仓库内落一个纯 Python 的数据采集模块，目标是把《[黄金价格预测.md](/D:/note/pandas_project/gold_price_analysis/黄金价格预测.md)》里**可稳定从 FRED 获取**的指标先工程化实现出来：初始化抓全量历史，之后每日执行增量更新，并按“类别/指标名称”落地为独立 CSV。

一期只做 **FRED 直连指标 + 简单 FRED 派生指标**。文档里依赖 WGC、CFTC、CME、CBOE、Bloomberg、policyuncertainty.com 等外部源的指标，先纳入指标清单但标记 `deferred`，不在本期实现抓取。

## Key Changes

### 1. 项目结构与入口

新增三个核心入口：

- `config/indicators.yml`
- `src/gold_data/cli.py`
- `scripts/run_daily_update.ps1`

命令接口固定为：

```bash
python -m gold_data init
python -m gold_data update
```

行为定义：

- `init`
  - 读取 `.env` 中 `FRED_API_KEY`
  - 遍历 `indicators.yml` 中 `enabled: true` 的指标
  - 从该指标配置的 `start_date` 拉取到今天的全量历史
  - 写入对应 CSV
  - 对派生指标在基础序列拉完后一次性全量计算
- `update`
  - 只更新 `enabled: true` 的指标
  - 对直接 FRED 序列按频率回补最近窗口后 merge 去重
  - 对派生指标基于依赖序列全量重算后覆盖输出
  - 运行应具备幂等性；同一天重复执行不产生重复行

`.env` 使用现有仓库根目录文件；不额外引入配置中心。

### 2. 存储布局与 CSV 规范

存储目录固定为：

```text
data/fred/<类别>/<指标名称>.csv
```

命名规则：

- 类别来自文档一级分类，路径内将 `/` 替换为 `_`
  - 例如：`通胀_通胀预期`、`名义利率`、`真实利率`
- 指标名称使用中文名，去掉不安全字符
  - 例如：`CPI.csv`、`核心CPI.csv`、`10年期美债收益率.csv`

每个 CSV 列结构固定为：

```csv
date,value
```

规则：

- `date` 为 ISO 日期 `YYYY-MM-DD`
- `value` 为数值；FRED 的 `.` 和空值丢弃
- 文件按 `date` 升序
- 每个指标一个文件，不混放多个 series

同时生成一个清单文件：

```text
data/fred/_catalog.csv
```

列为：

```csv
category,indicator_name,source,series_id,frequency,units,enabled,status,file_path
```

用途是给训练/特征工程阶段做统一发现，不把元数据重复写进每个指标 CSV。

### 3. 指标清单设计

`config/indicators.yml` 作为唯一事实源，字段固定为：

- `category`
- `indicator_name`
- `source: fred`
- `series_id`
- `series_type: direct | derived`
- `frequency: d | w | m | q`
- `start_date`
- `enabled`
- `status: active | deferred`
- `update_window_days`
- `formula`（仅派生指标）
- `dependencies`（仅派生指标）

一期启用的 direct/derived 指标固定如下。

**通胀_通胀预期**
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

**名义利率**
- `联邦基金利率` -> `FEDFUNDS`
- `SOFR` -> `SOFR`
- `3个月美债收益率` -> `TB3MS`
- `10年期美债收益率` -> `DGS10`

**真实利率**
- `10年期TIPS实际收益率` -> `DFII10`

**汇率**
- `美元广义贸易加权指数` -> `DTWEXBGS`

**货币供应量指标**
- `M1` -> `M1SL`
- `M2` -> `M2SL`
- `货币基础` -> `BOGMBASE`

**就业指标**
- `非农就业人数` -> `PAYEMS`
- `失业率` -> `UNRATE`

**信用利差**
- `投资级信用利差_OAS` -> `BAMLC0A0CM`
- `高收益信用利差_OAS` -> `BAMLH0A0HYM2`
- `TED利差` -> `TEDRATE`

**金融压力**
- `圣路易斯金融压力指数` -> `STLFSI4`

**油价指标**
- `WTI原油现货价` -> `DCOILWTICO`
- `Brent原油现货价` -> `DCOILBRENTEU`

**工业金属**
- `铜价` -> `PCOPPUSDM`

**派生指标**
- `10年期通胀预期_名义减实际` = `DGS10 - DFII10`
  - 依赖：`10年期美债收益率`、`10年期TIPS实际收益率`
  - 目录：`通胀_通胀预期/10年期通胀预期_名义减实际.csv`

本期在 `indicators.yml` 中保留但 `enabled: false, status: deferred` 的典型项：
- SPF、COT、GLD/IAU 持仓、WGC ETF flows、GVZ/VIX/MOVE、GPR、FX 具体货币对、央行购金、黄金期货/期权数据等

### 4. 更新策略与调度

更新窗口按频率固定，不做动态判断：

- 日频：回补最近 `30` 天
- 周频：回补最近 `90` 天
- 月频：回补最近 `540` 天
- 季频：回补最近 `720` 天

原因是月度/季度宏观数据有修订，日更时必须容忍历史回修。

实现流程：

1. 读取本地 CSV 最后日期
2. 根据 `update_window_days` 计算本次重抓起点
3. 从 FRED 拉该窗口数据
4. 与本地数据按 `date` 去重合并，保留最新值
5. 重写单个 CSV
6. 所有 direct 指标更新完成后，重算全部 derived 指标

调度方式固定为系统计划任务，不做常驻调度器：

- `scripts/run_daily_update.ps1` 只负责切到仓库目录并执行 `python -m gold_data update`
- README 中给出 Windows Task Scheduler / `schtasks` 示例
- 默认每日执行时间写成 `08:00` 本地时间；这只是文档默认值，不写死在代码里

## Test Plan

必须覆盖以下场景：

1. `indicators.yml` 校验
   - direct 指标必须有 `series_id`
   - derived 指标必须有 `dependencies` 和 `formula`
   - 输出路径唯一，不允许两个指标写同一文件

2. `init`
   - 空目录下成功生成全部 enabled 指标 CSV 和 `_catalog.csv`
   - 每个 CSV 只有 `date,value`
   - 日期升序、无重复日期

3. `update`
   - 已有历史数据时只回补窗口数据并合并
   - 重复执行两次结果不变
   - FRED 返回缺失值 `.` 时不会污染 CSV

4. 派生指标
   - `10年期通胀预期_名义减实际` 结果与依赖日期对齐
   - 任一依赖缺失时该日期不输出

5. 容错
   - 缺少 `FRED_API_KEY` 时明确报错并退出非零
   - 单个 series 请求失败时记录日志并继续其他指标，最终退出码非零
   - 网络超时会有限次重试，不无限循环

## Assumptions

- 一期范围严格限定为 FRED 可直接获取或由 FRED 基础序列直接计算的指标。
- 当前仓库没有既有代码结构，需要从零搭一个最小可维护脚手架。
- 运行环境使用现有 Python 3.12 + `pandas` + `requests`；不引入数据库。
- CSV 作为原始层存储，不在一期引入 parquet、duckdb 或特征仓库。
- 中文目录名和文件名在当前 Windows 环境可接受；路径统一做字符清洗，避免 `/ \ : * ? " < > |`。
