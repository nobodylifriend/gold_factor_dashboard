const test = require("node:test");
const assert = require("node:assert/strict");

const {
  classifyTrend,
  computeBinarySignals,
  computeEntryType,
  computeQuadrantState,
  computeDefaultDateRange,
  normalizeRange,
  buildSeriesWindow,
  slicePointsInRange,
  buildSvgLineChart,
  formatAxisDateLabel,
  buildExportFileName,
  buildTabButtonMarkup,
  buildTopicSummaryMarkup,
  computeTabInsightItems,
  buildInsightStripMarkup,
  buildSeriesMetaText,
  buildSeriesTitleMarkup,
  computeFreshnessStatus,
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

test("buildSeriesWindow marks fallback when the selected range has too few points", () => {
  const points = Array.from({ length: 12 }, (_, index) => ({
    date: `2026-0${Math.floor(index / 3) + 1}-${String((index % 3) + 1).padStart(2, "0")}`,
    value: index + 1,
  }));
  const densePoints = Array.from({ length: 14 }, (_, index) => ({
    date: `2026-05-${String(index + 1).padStart(2, "0")}`,
    value: index + 1,
  }));

  const fallback = buildSeriesWindow(points, "2026-05-01", "2026-05-31");
  const sparse = buildSeriesWindow(points, "2026-04-01", "2026-04-30");
  const direct = buildSeriesWindow(densePoints, "2026-05-01", "2026-05-12");

  assert.equal(fallback.isFallback, true);
  assert.equal(sparse.isFallback, true);
  assert.equal(direct.isFallback, false);
  assert.equal(fallback.inRangeCount, 0);
  assert.equal(sparse.inRangeCount, 3);
  assert.equal(direct.inRangeCount, 12);
  assert.equal(fallback.points.length, 10);
  assert.equal(sparse.points.length, 10);
  assert.equal(direct.points.length, 12);
  assert.deepEqual(fallback.points.map((point) => point.value), [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  assert.deepEqual(sparse.points.map((point) => point.value), [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  assert.deepEqual(direct.points.map((point) => point.value), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
});

test("slicePointsInRange keeps returning points only for compatibility", () => {
  const points = [
    { date: "2026-01-01", value: 1 },
    { date: "2026-02-01", value: 2 },
    { date: "2026-03-01", value: 3 },
  ];

  assert.deepEqual(slicePointsInRange(points, "2026-02-01", "2026-02-28"), points);
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

test("buildExportFileName includes current date range", () => {
  assert.equal(
    buildExportFileName({ start: "2026-04-04", end: "2026-05-04" }),
    "gold-macro-dashboard-2026-04-04_to_2026-05-04.png",
  );
});

test("buildTabButtonMarkup marks the active tab", () => {
  const markup = buildTabButtonMarkup(
    { id: "gold", label: "黄金本体", description: "价格与资金" },
    "gold",
  );

  assert.match(markup, /data-tab-id="gold"/);
  assert.match(markup, /aria-selected="true"/);
  assert.match(markup, /黄金本体/);
});

test("buildTopicSummaryMarkup renders compact cards", () => {
  const markup = buildTopicSummaryMarkup([
    { key: "gold_summary", label: "黄金本体", value: "价格上行，ETF回流", tone: "positive" },
    { key: "rates_summary", label: "利率流动性", value: "实际利率回落", tone: "positive" },
  ]);

  assert.match(markup, /topic-summary-grid/);
  assert.match(markup, /黄金本体/);
  assert.match(markup, /实际利率回落/);
});

test("computeTabInsightItems turns configured series into insight cards", () => {
  const items = computeTabInsightItems(
    {
      insights: [
        {
          key: "usd_direction",
          label: "美元总方向",
          series_id: "dxy",
          up_text: "美元走强",
          down_text: "美元走弱",
          flat_text: "美元横盘",
          up_tone: "negative",
          down_tone: "positive",
          flat_tone: "neutral",
        },
      ],
    },
    {
      dxy: { start: 100, end: 98.5 },
    },
  );

  assert.deepEqual(items, [
    {
      key: "usd_direction",
      label: "美元总方向",
      value: "美元走弱",
      tone: "positive",
    },
  ]);
});

test("buildInsightStripMarkup renders tab insight cards", () => {
  const markup = buildInsightStripMarkup("专题结论", [
    { key: "vix", label: "波动率", value: "波动率回落", tone: "positive" },
    { key: "stress", label: "金融压力", value: "压力缓和", tone: "positive" },
  ]);

  assert.match(markup, /tab-insight-grid/);
  assert.match(markup, /专题结论/);
  assert.match(markup, /波动率回落/);
});

test("buildSeriesMetaText renders frequency and latest date", () => {
  const meta = buildSeriesMetaText({
    frequency_label: "季频",
    latest_date: "2026-03-31",
  });

  assert.match(meta, /季频/);
  assert.match(meta, /2026-03-31/);
});

test("computeFreshnessStatus flags stale series against selected range end", () => {
  assert.deepEqual(
    computeFreshnessStatus(
      { frequency_label: "月频", latest_date: "2026-02-01" },
      "2026-05-08",
    ),
    { level: "warning", label: "更新偏旧" },
  );

  assert.equal(
    computeFreshnessStatus(
      { frequency_label: "季频", latest_date: "2026-03-31" },
      "2026-05-08",
    ),
    null,
  );
});

test("buildSeriesTitleMarkup renders a help trigger when description exists", () => {
  const markup = buildSeriesTitleMarkup({
    label: "美元指数 DXY",
    description_zh: "美元对主要可兑换货币的狭义指数，用来观察美元强弱。",
  });

  assert.match(markup, /chart-title-row/);
  assert.match(markup, /chart-info-button/);
  assert.match(markup, /title="美元对主要可兑换货币的狭义指数，用来观察美元强弱。"/);
  assert.match(markup, /aria-label="查看 美元指数 DXY 指标定义"/);
});
