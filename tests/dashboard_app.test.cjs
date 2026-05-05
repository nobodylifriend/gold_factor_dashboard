const test = require("node:test");
const assert = require("node:assert/strict");

const {
  classifyTrend,
  computeBinarySignals,
  computeEntryType,
  computeQuadrantState,
  computeDefaultDateRange,
  normalizeRange,
  buildSvgLineChart,
  formatAxisDateLabel,
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

test("computeDefaultDateRange prefers yesterday and one month earlier", () => {
  const range = computeDefaultDateRange("2024-01-01", "2026-05-04", new Date(2026, 4, 5));
  assert.deepEqual(range, {
    start: "2026-04-04",
    end: "2026-05-04",
  });
});

test("normalizeRange swaps invalid user ranges", () => {
  assert.deepEqual(
    normalizeRange("2026-05-04", "2026-04-04", { start: "2026-04-04", end: "2026-05-04" }),
    { start: "2026-04-04", end: "2026-05-04" },
  );
});

test("formatAxisDateLabel renders short visible date label", () => {
  assert.equal(formatAxisDateLabel("2026-05-05"), "26/05/05");
});

test("buildSvgLineChart includes axes, labels and hover layers", () => {
  const markup = buildSvgLineChart(
    [
      { date: "2026-05-01", value: 100 },
      { date: "2026-05-02", value: 105 },
      { date: "2026-05-05", value: 110 },
    ],
    "#73c6ff",
    2,
  );

  assert.match(markup, /chart-axis-label-x/);
  assert.match(markup, /chart-axis-label-y/);
  assert.match(markup, /chart-hover-line/);
  assert.match(markup, /chart-tooltip/);
});
