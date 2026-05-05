# 黄金宏观分析台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个中文金融科技风格的黄金宏观分析台，基于本地数据生成独立页面，支持日期筛选、主图、四象限、信号判断和文档入口。

**Architecture:** 使用一个 Python 数据整理脚本把目标指标统一为前端可消费的 `dashboard_data.json`，再由一个纯静态前端页面读取并渲染。信号判断的纯函数放在浏览器脚本中，同时导出给 Node 测试使用，确保日期筛选后的规则判断可自动验证。

**Tech Stack:** Python 3.12, pandas, pytest, 原生 HTML/CSS/JavaScript, Node.js 内置 `node:test`

---

## File Structure

### New files

- `scripts/build_gold_macro_dashboard_data.py`
  负责读取本地 CSV、规范化字段、生成前端数据载荷。
- `visuals/gold_macro_dashboard/index.html`
  页面骨架，包含首屏结构、文档入口和脚本样式引用。
- `visuals/gold_macro_dashboard/styles.css`
  金融科技风格样式与响应式布局。
- `visuals/gold_macro_dashboard/app.js`
  数据加载、日期筛选、信号判断、四象限定位、SVG 图表渲染。
- `visuals/gold_macro_dashboard/data/dashboard_data.json`
  前端消费用整理数据产物。
- `tests/test_gold_macro_dashboard_data.py`
  Python 侧数据整理和输出结构测试。
- `tests/dashboard_app.test.cjs`
  Node 侧规则函数测试。
- `tests/test_gold_macro_dashboard_assets.py`
  页面静态结构检查。

### Modified files

- `四象限.md`
  增加页面入口、用途和数据来源说明。

## Rule Decisions Locked In

这些规则在实现中直接固定，不再讨论：

- `横盘` 阈值
  - `TIPS / 10年期美债 / 10年盈亏平衡通胀率 / 高收益信用利差 / SOFR`：区间终值与起值绝对差 `< 0.03`
  - `DXY`：区间终值与起值绝对差 `< 0.20`
- `预测`
  - 不满足 `确认`
  - 最近 5 个有效点内 `TIPS` 和 `DXY` 的净变化都为负
  - 且两者全区间趋势不同时为 `下降`
- `错配`
  - 已满足 `确认`
  - 且 `SP500` 筛选区间收益率 `<= -2.0%`
- `四象限边界状态`
  - 若 `DXY` 或 `TIPS` 为 `横盘`，不强行归类到四象限，显示 `边界状态`

### Task 1: 建立数据整理测试与脚本骨架

**Files:**
- Create: `tests/test_gold_macro_dashboard_data.py`
- Create: `scripts/build_gold_macro_dashboard_data.py`

- [ ] **Step 1: Write the failing Python tests**

```python
from pathlib import Path

from scripts.build_gold_macro_dashboard_data import (
    DASHBOARD_SERIES,
    build_dashboard_payload,
    compute_trend_label,
    load_series_frame,
)


def test_compute_trend_label_respects_per_series_thresholds():
    assert compute_trend_label("tips10y", 1.50, 1.52) == "横盘"
    assert compute_trend_label("tips10y", 1.50, 1.56) == "上升"
    assert compute_trend_label("dxy", 103.0, 102.85) == "横盘"
    assert compute_trend_label("dxy", 103.0, 102.6) == "下降"


def test_load_series_frame_normalizes_close_and_value_columns():
    xau = load_series_frame(Path("data/xau/xau_usd_daily_ohlc.csv"), value_column="close")
    spx = load_series_frame(Path("data/stock_index/SP500.csv"), value_column="value")

    assert list(xau.columns) == ["date", "value"]
    assert list(spx.columns) == ["date", "value"]
    assert xau["date"].is_monotonic_increasing
    assert spx["date"].is_monotonic_increasing


def test_build_dashboard_payload_contains_all_required_sections():
    payload = build_dashboard_payload()

    assert sorted(payload.keys()) == ["generated_at", "metadata", "series"]
    assert sorted(payload["series"].keys()) == sorted(DASHBOARD_SERIES.keys())
    assert payload["metadata"]["hero_chart_ids"] == ["xau", "sp500", "nasdaq100"]
    assert payload["metadata"]["detail_chart_ids"] == [
        "tips10y",
        "dxy",
        "nominal10y",
        "breakeven10y",
        "credit_oas_hy",
        "sofr",
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_gold_macro_dashboard_data.py -v`

Expected: `FAIL` with import errors because `build_dashboard_payload`, `compute_trend_label`, and `load_series_frame` do not exist yet.

- [ ] **Step 3: Write the minimal script skeleton**

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "visuals" / "gold_macro_dashboard" / "data" / "dashboard_data.json"

DASHBOARD_SERIES = {
    "xau": {"path": ROOT / "data" / "xau" / "xau_usd_daily_ohlc.csv", "value_column": "close", "label": "黄金价格走势"},
    "sp500": {"path": ROOT / "data" / "stock_index" / "SP500.csv", "value_column": "value", "label": "标普500价格走势"},
    "nasdaq100": {"path": ROOT / "data" / "stock_index" / "NASDAQ100.csv", "value_column": "value", "label": "纳斯达克100价格走势"},
    "tips10y": {"path": ROOT / "data" / "fred" / "名义利率" / "10年期TIPS实际收益率.csv", "value_column": "value", "label": "10年期TIPS实际收益率"},
    "dxy": {"path": ROOT / "data" / "fx" / "DXY.csv", "value_column": "value", "label": "DXY"},
    "nominal10y": {"path": ROOT / "data" / "fred" / "名义利率" / "10年期美债收益率.csv", "value_column": "value", "label": "10年期美债收益率"},
    "breakeven10y": {"path": ROOT / "data" / "fred" / "通胀_通胀预期" / "10年盈亏平衡通胀率.csv", "value_column": "value", "label": "10年盈亏平衡通胀率"},
    "credit_oas_hy": {"path": ROOT / "data" / "fred" / "信用利差" / "高收益信用利差_OAS.csv", "value_column": "value", "label": "高收益信用利差_OAS"},
    "sofr": {"path": ROOT / "data" / "fred" / "名义利率" / "SOFR.csv", "value_column": "value", "label": "SOFR"},
}

TREND_THRESHOLDS = {
    "tips10y": 0.03,
    "nominal10y": 0.03,
    "breakeven10y": 0.03,
    "credit_oas_hy": 0.03,
    "sofr": 0.03,
    "dxy": 0.20,
}


def compute_trend_label(series_id: str, start_value: float, end_value: float) -> str:
    delta = end_value - start_value
    threshold = TREND_THRESHOLDS.get(series_id, 0.0)
    if abs(delta) < threshold:
        return "横盘"
    return "上升" if delta > 0 else "下降"


def load_series_frame(path: Path, value_column: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    normalized = frame.loc[:, ["date", value_column]].rename(columns={value_column: "value"}).copy()
    normalized["date"] = pd.to_datetime(normalized["date"], utc=False).dt.strftime("%Y-%m-%d")
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    normalized = normalized.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)
    return normalized


def build_dashboard_payload() -> dict:
    series = {}
    for series_id, spec in DASHBOARD_SERIES.items():
        frame = load_series_frame(spec["path"], spec["value_column"])
        series[series_id] = {
            "label": spec["label"],
            "points": frame.to_dict(orient="records"),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "hero_chart_ids": ["xau", "sp500", "nasdaq100"],
            "detail_chart_ids": ["tips10y", "dxy", "nominal10y", "breakeven10y", "credit_oas_hy", "sofr"],
        },
        "series": series,
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_dashboard_payload(), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_gold_macro_dashboard_data.py -v`

Expected: `PASS` for the three tests above.

- [ ] **Step 5: Commit**

```bash
git add tests/test_gold_macro_dashboard_data.py scripts/build_gold_macro_dashboard_data.py
git commit -m "feat: scaffold gold macro dashboard data builder"
```

### Task 2: 完成数据载荷结构与输出文件生成

**Files:**
- Modify: `scripts/build_gold_macro_dashboard_data.py`
- Modify: `tests/test_gold_macro_dashboard_data.py`
- Create: `visuals/gold_macro_dashboard/data/dashboard_data.json`

- [ ] **Step 1: Extend the failing tests for metadata and date-range support**

```python
import json

from scripts.build_gold_macro_dashboard_data import OUTPUT, build_dashboard_payload, main


def test_build_dashboard_payload_exposes_default_date_bounds():
    payload = build_dashboard_payload()

    assert payload["metadata"]["default_range"]["start"]
    assert payload["metadata"]["default_range"]["end"]
    assert payload["metadata"]["series_order"] == [
        "xau",
        "sp500",
        "nasdaq100",
        "tips10y",
        "dxy",
        "nominal10y",
        "breakeven10y",
        "credit_oas_hy",
        "sofr",
    ]


def test_main_writes_dashboard_json_file():
    main()

    assert OUTPUT.exists()
    data = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert data["series"]["xau"]["label"] == "黄金价格走势"
    assert data["metadata"]["quadrant_axes"] == {"x": "dxy", "y": "tips10y"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_gold_macro_dashboard_data.py -v`

Expected: `FAIL` because `default_range`, `series_order`, and `quadrant_axes` are not present yet.

- [ ] **Step 3: Implement the final payload shape**

```python
def build_dashboard_payload() -> dict:
    series = {}
    all_dates: list[str] = []
    series_order = list(DASHBOARD_SERIES.keys())

    for series_id, spec in DASHBOARD_SERIES.items():
        frame = load_series_frame(spec["path"], spec["value_column"])
        points = frame.to_dict(orient="records")
        series[series_id] = {
            "label": spec["label"],
            "points": points,
            "value_precision": 2,
        }
        all_dates.extend(point["date"] for point in points)

    unique_dates = sorted(set(all_dates))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "title": "黄金 / 美元 / 利率 信号矩阵",
            "hero_chart_ids": ["xau", "sp500", "nasdaq100"],
            "detail_chart_ids": ["tips10y", "dxy", "nominal10y", "breakeven10y", "credit_oas_hy", "sofr"],
            "series_order": series_order,
            "quadrant_axes": {"x": "dxy", "y": "tips10y"},
            "default_range": {"start": unique_dates[-252], "end": unique_dates[-1]},
            "trend_thresholds": TREND_THRESHOLDS,
        },
        "series": series,
    }
```

- [ ] **Step 4: Generate the dashboard JSON and rerun tests**

Run:

```bash
python scripts/build_gold_macro_dashboard_data.py
pytest tests/test_gold_macro_dashboard_data.py -v
```

Expected:

- `visuals/gold_macro_dashboard/data/dashboard_data.json` exists
- pytest reports `PASS`

- [ ] **Step 5: Commit**

```bash
git add scripts/build_gold_macro_dashboard_data.py tests/test_gold_macro_dashboard_data.py visuals/gold_macro_dashboard/data/dashboard_data.json
git commit -m "feat: generate dashboard data payload"
```

### Task 3: 实现前端规则函数并用 Node 自动测试

**Files:**
- Create: `visuals/gold_macro_dashboard/app.js`
- Create: `tests/dashboard_app.test.cjs`

- [ ] **Step 1: Write the failing Node tests for rule functions**

```javascript
const test = require("node:test");
const assert = require("node:assert/strict");

const {
  classifyTrend,
  computeBinarySignals,
  computeEntryType,
  computeQuadrantState,
} = require("../visuals/gold_macro_dashboard/app.js");

test("classifyTrend returns flat inside threshold", () => {
  assert.equal(classifyTrend(1.5, 1.52, 0.03), "横盘");
  assert.equal(classifyTrend(103.0, 102.5, 0.2), "下降");
});

test("computeBinarySignals returns expected booleans", () => {
  const signals = computeBinarySignals({
    xau: { start: 2000, end: 2050 },
    credit_oas_hy: { start: 4.2, end: 4.0 },
    nominal10y: { start: 4.5, end: 4.3 },
  });

  assert.deepEqual(signals, {
    goldUp: true,
    creditTightening: true,
    bondYieldDown: true,
  });
});

test("computeEntryType distinguishes 预测, 确认, 错配", () => {
  assert.equal(
    computeEntryType({
      trends: { tips10y: "下降", dxy: "下降", nominal10y: "横盘" },
      recentTurnsNegative: false,
      binarySignals: { goldUp: true, creditTightening: true, bondYieldDown: false },
      sp500Return: 0.01,
    }),
    "确认",
  );

  assert.equal(
    computeEntryType({
      trends: { tips10y: "横盘", dxy: "上升", nominal10y: "上升" },
      recentTurnsNegative: true,
      binarySignals: { goldUp: false, creditTightening: false, bondYieldDown: false },
      sp500Return: 0.0,
    }),
    "预测",
  );

  assert.equal(
    computeEntryType({
      trends: { tips10y: "下降", dxy: "下降", nominal10y: "横盘" },
      recentTurnsNegative: false,
      binarySignals: { goldUp: true, creditTightening: true, bondYieldDown: false },
      sp500Return: -0.03,
    }),
    "错配",
  );
});

test("computeQuadrantState returns 边界状态 when any axis is flat", () => {
  assert.deepEqual(computeQuadrantState("横盘", "下降"), { key: "boundary", label: "边界状态" });
  assert.deepEqual(computeQuadrantState("下降", "下降"), { key: "bottom-left", label: "全面宽松区" });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test tests/dashboard_app.test.cjs`

Expected: `FAIL` because `visuals/gold_macro_dashboard/app.js` does not exist yet.

- [ ] **Step 3: Implement the pure rule functions with CommonJS exports**

```javascript
function classifyTrend(startValue, endValue, threshold) {
  const delta = endValue - startValue;
  if (Math.abs(delta) < threshold) return "横盘";
  return delta > 0 ? "上升" : "下降";
}

function computeBinarySignals({ xau, credit_oas_hy, nominal10y }) {
  return {
    goldUp: xau.end > xau.start,
    creditTightening: credit_oas_hy.end < credit_oas_hy.start,
    bondYieldDown: nominal10y.end < nominal10y.start,
  };
}

function computeEntryType({ trends, recentTurnsNegative, binarySignals, sp500Return }) {
  const confirmationCount = [
    binarySignals.goldUp,
    binarySignals.creditTightening,
    binarySignals.bondYieldDown,
  ].filter(Boolean).length;

  const isConfirm =
    trends.tips10y === "下降" &&
    trends.dxy === "下降" &&
    trends.nominal10y !== "上升" &&
    confirmationCount >= 2;

  if (isConfirm && sp500Return <= -0.02) return "错配";
  if (isConfirm) return "确认";
  if (recentTurnsNegative && !(trends.tips10y === "下降" && trends.dxy === "下降")) return "预测";
  return "观察";
}

function computeQuadrantState(dxyTrend, tipsTrend) {
  if (dxyTrend === "横盘" || tipsTrend === "横盘") {
    return { key: "boundary", label: "边界状态" };
  }
  if (dxyTrend === "下降" && tipsTrend === "上升") return { key: "top-left", label: "再分配区" };
  if (dxyTrend === "上升" && tipsTrend === "上升") return { key: "top-right", label: "紧缩风险区" };
  if (dxyTrend === "下降" && tipsTrend === "下降") return { key: "bottom-left", label: "全面宽松区" };
  return { key: "bottom-right", label: "美元避险区" };
}

module.exports = {
  classifyTrend,
  computeBinarySignals,
  computeEntryType,
  computeQuadrantState,
};
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test tests/dashboard_app.test.cjs`

Expected: `PASS` for all four test cases.

- [ ] **Step 5: Commit**

```bash
git add visuals/gold_macro_dashboard/app.js tests/dashboard_app.test.cjs
git commit -m "feat: add dashboard signal evaluation logic"
```

### Task 4: 搭建页面结构、样式和 SVG 图表渲染

**Files:**
- Create: `visuals/gold_macro_dashboard/index.html`
- Create: `visuals/gold_macro_dashboard/styles.css`
- Modify: `visuals/gold_macro_dashboard/app.js`
- Create: `tests/test_gold_macro_dashboard_assets.py`

- [ ] **Step 1: Write the failing asset smoke test**

```python
from pathlib import Path


def test_dashboard_html_contains_required_sections():
    html = Path("visuals/gold_macro_dashboard/index.html").read_text(encoding="utf-8")

    assert "黄金 / 美元 / 利率 信号矩阵" in html
    assert 'id="hero-entry-type"' in html
    assert 'id="quadrant-panel"' in html
    assert 'id="signal-checklist"' in html
    assert 'id="detail-charts"' in html


def test_dashboard_styles_define_fintech_theme_tokens():
    css = Path("visuals/gold_macro_dashboard/styles.css").read_text(encoding="utf-8")

    assert "--bg-base:" in css
    assert "--accent-gold:" in css
    assert ".hero-panel" in css
    assert ".chart-card" in css
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_gold_macro_dashboard_assets.py -v`

Expected: `FAIL` because the HTML and CSS files do not exist yet.

- [ ] **Step 3: Create the page shell and renderer hooks**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>黄金 / 美元 / 利率 信号矩阵</title>
    <link rel="stylesheet" href="./styles.css">
  </head>
  <body>
    <main class="page-shell">
      <section class="hero-panel">
        <div class="hero-copy">
          <p class="eyebrow">黄金宏观分析台</p>
          <h1>黄金 / 美元 / 利率 信号矩阵</h1>
          <p class="hero-summary" id="hero-summary"></p>
        </div>
        <div class="date-controls">
          <label>开始日期<input id="start-date" type="date"></label>
          <label>结束日期<input id="end-date" type="date"></label>
        </div>
        <div class="hero-status">
          <div class="status-chip">
            <span class="status-label">当前入场类型</span>
            <strong id="hero-entry-type">观察</strong>
          </div>
        </div>
      </section>

      <section class="overview-grid">
        <div class="hero-charts">
          <article class="chart-card"><h2>黄金价格走势</h2><div id="chart-xau"></div></article>
          <article class="chart-card"><h2>标普500价格走势</h2><div id="chart-sp500"></div></article>
          <article class="chart-card"><h2>纳斯达克100价格走势</h2><div id="chart-nasdaq100"></div></article>
        </div>
        <aside class="quadrant-card" id="quadrant-panel"></aside>
      </section>

      <section class="signal-panel" id="signal-checklist"></section>
      <section class="detail-grid" id="detail-charts"></section>
      <section class="doc-panel"><a href="../../四象限.md">返回四象限文档说明</a></section>
    </main>
    <script src="./app.js"></script>
  </body>
</html>
```

```css
:root {
  --bg-base: #071018;
  --bg-panel: #0d1a2b;
  --bg-elevated: #12253c;
  --text-main: #e8f0ff;
  --text-dim: #92aac8;
  --accent-blue: #73c6ff;
  --accent-gold: #f4c55c;
  --accent-green: #6be7c1;
  --accent-red: #ff8e8e;
  --border-soft: rgba(125, 168, 214, 0.18);
}

body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(115, 198, 255, 0.16), transparent 22%),
    radial-gradient(circle at top right, rgba(244, 197, 92, 0.12), transparent 18%),
    var(--bg-base);
  color: var(--text-main);
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.page-shell {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

.hero-panel,
.chart-card,
.quadrant-card,
.signal-panel,
.doc-panel {
  border: 1px solid var(--border-soft);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02)), var(--bg-panel);
}
```

```javascript
function buildSvgLineChart(points, stroke) {
  if (!points.length) return '<p class="empty-state">当前时间窗内无有效数据</p>';
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 640;
  const height = 180;
  const ySpan = max - min || 1;
  const path = points.map((point, index) => {
    const x = (index / Math.max(points.length - 1, 1)) * width;
    const y = height - ((point.value - min) / ySpan) * height;
    return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
  return `<svg viewBox="0 0 ${width} ${height}" class="sparkline"><path d="${path}" fill="none" stroke="${stroke}" stroke-width="3" stroke-linecap="round"/></svg>`;
}
```

- [ ] **Step 4: Run the asset test**

Run: `pytest tests/test_gold_macro_dashboard_assets.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add visuals/gold_macro_dashboard/index.html visuals/gold_macro_dashboard/styles.css visuals/gold_macro_dashboard/app.js tests/test_gold_macro_dashboard_assets.py
git commit -m "feat: add dashboard page shell and styles"
```

### Task 5: 接入 JSON 数据、日期筛选、信号清单和四象限渲染

**Files:**
- Modify: `visuals/gold_macro_dashboard/app.js`
- Modify: `visuals/gold_macro_dashboard/index.html`
- Modify: `四象限.md`
- Test: `tests/dashboard_app.test.cjs`
- Test: `tests/test_gold_macro_dashboard_assets.py`

- [ ] **Step 1: Extend the Node tests for recent-turn and filtered metrics**

```javascript
test("computeEntryType only returns 预测 when recent turns are negative without confirmation", () => {
  assert.equal(
    computeEntryType({
      trends: { tips10y: "上升", dxy: "横盘", nominal10y: "上升" },
      recentTurnsNegative: true,
      binarySignals: { goldUp: false, creditTightening: false, bondYieldDown: false },
      sp500Return: -0.01,
    }),
    "预测",
  );
});
```

- [ ] **Step 2: Run tests to verify the new case fails**

Run:

```bash
node --test tests/dashboard_app.test.cjs
pytest tests/test_gold_macro_dashboard_assets.py -v
```

Expected: Node test fails until the page-level filtering helpers and render flow are wired up.

- [ ] **Step 3: Implement data loading, filter application, checklist rendering and quadrant text**

```javascript
async function loadDashboardData() {
  const response = await fetch("./data/dashboard_data.json");
  if (!response.ok) throw new Error(`加载数据失败: ${response.status}`);
  return response.json();
}

function slicePointsInRange(points, start, end) {
  return points.filter((point) => point.date >= start && point.date <= end);
}

function summarizeWindow(points) {
  if (!points.length) return null;
  return {
    start: points[0].value,
    end: points[points.length - 1].value,
    returnRate: points[0].value === 0 ? 0 : (points[points.length - 1].value - points[0].value) / points[0].value,
  };
}

function recentTurnNegative(points) {
  const tail = points.slice(-5);
  if (tail.length < 5) return false;
  return tail[tail.length - 1].value - tail[0].value < 0;
}

function renderSignalChecklist(state) {
  const checklist = document.getElementById("signal-checklist");
  checklist.innerHTML = `
    <h2>信号判断清单</h2>
    <div class="signal-grid">
      <article class="signal-item">TIPS：${state.trends.tips10y}</article>
      <article class="signal-item">DXY：${state.trends.dxy}</article>
      <article class="signal-item">名义利率：${state.trends.nominal10y}</article>
      <article class="signal-item">盈亏平衡通胀率：${state.trends.breakeven10y}</article>
      <article class="signal-item">黄金上涨：${state.binarySignals.goldUp ? "是" : "否"}</article>
      <article class="signal-item">信用利差收窄：${state.binarySignals.creditTightening ? "是" : "否"}</article>
      <article class="signal-item">债券利率下降：${state.binarySignals.bondYieldDown ? "是" : "否"}</article>
      <article class="signal-item">入场类型：${state.entryType}</article>
    </div>
  `;
}

function renderQuadrant(panel, quadrant) {
  panel.innerHTML = `
    <h2>四象限定位</h2>
    <p class="quadrant-status">${quadrant.label}</p>
    <div class="quadrant-copy">${quadrant.key === "boundary" ? "当前处于边界状态，至少一个轴为横盘。" : "当前以五角星标记在对应象限。"}</div>
  `;
}
```

- [ ] **Step 4: Verify the full flow manually and with tests**

Run:

```bash
python scripts/build_gold_macro_dashboard_data.py
node --test tests/dashboard_app.test.cjs
pytest tests/test_gold_macro_dashboard_data.py tests/test_gold_macro_dashboard_assets.py -v
python -m http.server 8765
```

Expected:

- `node --test` reports `PASS`
- `pytest` reports `PASS`
- Open `http://localhost:8765/visuals/gold_macro_dashboard/index.html`
- Change date range and confirm:
  - Hero 入场类型实时变化
  - 三张主图和六张详细图同步更新
  - 四象限和信号清单同步更新
  - 页面全部中文，无英文 UI 文案

- [ ] **Step 5: Update the Markdown entry and commit**

```markdown
## 可视化页面入口

- 页面路径：`visuals/gold_macro_dashboard/index.html`
- 启动方式：在仓库根目录运行 `python -m http.server 8765`，然后打开 `http://localhost:8765/visuals/gold_macro_dashboard/index.html`
- 指标清单来源：[data/indicator_catalog.md](/D:/note/pandas_project/gold_price_analysis/data/indicator_catalog.md)

这个页面用于把黄金、美元、TIPS、名义利率、信用利差和股指的联动关系落成一个可交互分析台。
```

```bash
git add visuals/gold_macro_dashboard/app.js visuals/gold_macro_dashboard/index.html 四象限.md
git commit -m "feat: wire up gold macro dashboard interactions"
```

## Self-Review

### Spec coverage

- 独立页面：Task 4, Task 5
- 数据整理产物：Task 1, Task 2
- 文档入口：Task 5
- 中文金融科技风格：Task 4
- 日期筛选：Task 5
- 三主图：Task 4, Task 5
- 四象限：Task 3, Task 5
- 信号判断清单：Task 3, Task 5
- `预测 / 确认 / 错配` 明确规则：Task 3
- 指标范围：Task 1, Task 2

### Placeholder scan

- 没有 `TBD` / `TODO`
- 所有新增文件和命令均已给出
- 模糊规则已锁定为固定阈值

### Type consistency

- Python 数据键名与前端系列键名统一为：
  - `xau`
  - `sp500`
  - `nasdaq100`
  - `tips10y`
  - `dxy`
  - `nominal10y`
  - `breakeven10y`
  - `credit_oas_hy`
  - `sofr`
- Node 测试与浏览器逻辑公用：
  - `classifyTrend`
  - `computeBinarySignals`
  - `computeEntryType`
  - `computeQuadrantState`

