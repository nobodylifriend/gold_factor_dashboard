const CHART_STROKES = {
  xau: "#f4c55c",
  sp500: "#73c6ff",
  nasdaq100: "#6be7c1",
  tips10y: "#73c6ff",
  dxy: "#f4c55c",
  nominal10y: "#ff8e8e",
  breakeven10y: "#9dc9ff",
  credit_oas_hy: "#f7a35b",
  sofr: "#8be0ff",
};

const QUADRANT_COPY = {
  "top-left": "再分配区：债券偏弱，黄金偏弱，股票可涨但不稳。",
  "top-right": "紧缩风险区：股票下跌风险高，黄金偏弱，债券偏弱，流动性紧缩且美元走强。",
  "bottom-left": "全面宽松区：股票、黄金、债券同步受益。",
  "bottom-right": "美元避险区：股票不稳，黄金偏中性，债券走强，避险资金流入美元。",
  boundary: "当前处于边界状态，至少一个核心轴仍在横盘，信号还未完成明确归类。",
};

const DETAIL_SIGNAL_SERIES = ["tips10y", "dxy", "nominal10y", "breakeven10y"];

function classifyTrend(startValue, endValue, threshold) {
  const delta = endValue - startValue;
  if (Math.abs(delta) < threshold) {
    return "横盘";
  }
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

  if (isConfirm && sp500Return <= -0.02) {
    return "错配";
  }
  if (isConfirm) {
    return "确认";
  }
  if (recentTurnsNegative && !(trends.tips10y === "下降" && trends.dxy === "下降")) {
    return "预测";
  }
  return "观察";
}

function computeQuadrantState(dxyTrend, tipsTrend) {
  if (dxyTrend === "横盘" || tipsTrend === "横盘") {
    return { key: "boundary", label: "边界状态" };
  }
  if (dxyTrend === "下降" && tipsTrend === "上升") {
    return { key: "top-left", label: "再分配区" };
  }
  if (dxyTrend === "上升" && tipsTrend === "上升") {
    return { key: "top-right", label: "紧缩风险区" };
  }
  if (dxyTrend === "下降" && tipsTrend === "下降") {
    return { key: "bottom-left", label: "全面宽松区" };
  }
  return { key: "bottom-right", label: "美元避险区" };
}

function buildSvgLineChart(points, stroke) {
  if (!points.length) {
    return '<p class="empty-state">当前时间窗内无有效数据。</p>';
  }

  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 640;
  const height = 180;
  const ySpan = max - min || 1;
  const path = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width;
      const y = height - ((point.value - min) / ySpan) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  return `<svg viewBox="0 0 ${width} ${height}" class="sparkline" role="img" aria-label="折线图"><path d="${path}" fill="none" stroke="${stroke}" stroke-width="3" stroke-linecap="round"/></svg>`;
}

async function loadDashboardData() {
  const response = await fetch("./data/dashboard_data.json");
  if (!response.ok) {
    throw new Error(`加载数据失败：${response.status}`);
  }
  return response.json();
}

function slicePointsInRange(points, start, end) {
  return points.filter((point) => point.date >= start && point.date <= end);
}

function summarizeWindow(points) {
  if (!points.length) {
    return null;
  }
  return {
    start: points[0].value,
    end: points[points.length - 1].value,
    returnRate:
      points[0].value === 0 ? 0 : (points[points.length - 1].value - points[0].value) / points[0].value,
    startDate: points[0].date,
    endDate: points[points.length - 1].date,
  };
}

function recentTurnNegative(points) {
  const tail = points.slice(-5);
  if (tail.length < 5) {
    return false;
  }
  return tail[tail.length - 1].value - tail[0].value < 0;
}

function formatPercent(value) {
  return `${(value * 100).toFixed(2)}%`;
}

function formatValue(value, precision = 2) {
  return Number(value).toFixed(precision);
}

function formatDateValue(date) {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function parseIsoDate(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function shiftIsoDateByDays(isoDate, days) {
  const date = parseIsoDate(isoDate);
  date.setDate(date.getDate() + days);
  return formatDateValue(date);
}

function shiftIsoDateByMonths(isoDate, months) {
  const date = parseIsoDate(isoDate);
  date.setMonth(date.getMonth() + months);
  return formatDateValue(date);
}

function clampIsoDate(isoDate, minDate, maxDate) {
  if (isoDate < minDate) {
    return minDate;
  }
  if (isoDate > maxDate) {
    return maxDate;
  }
  return isoDate;
}

function computeDefaultDateRange(minDate, maxDate, referenceDate = new Date()) {
  const yesterday = new Date(referenceDate);
  yesterday.setDate(yesterday.getDate() - 1);
  const preferredEnd = formatDateValue(yesterday);
  const end = clampIsoDate(preferredEnd, minDate, maxDate);
  const preferredStart = shiftIsoDateByMonths(end, -1);
  const start = clampIsoDate(preferredStart, minDate, end);
  return { start, end };
}

function buildChartMarkup(seriesId, series, points) {
  const precision = series.value_precision ?? 2;
  const summary = summarizeWindow(points);
  const footer = summary
    ? `<p class="chart-note">${summary.startDate} → ${summary.endDate} ｜ ${formatValue(summary.start, precision)} → ${formatValue(summary.end, precision)}</p>`
    : '<p class="chart-note">当前筛选区间没有可用数据。</p>';

  return `${buildSvgLineChart(points, CHART_STROKES[seriesId] || "#73c6ff")}${footer}`;
}

function renderCharts(data, filteredSeries) {
  data.metadata.hero_chart_ids.forEach((seriesId) => {
    const target = document.getElementById(`chart-${seriesId}`);
    if (!target) {
      return;
    }
    target.innerHTML = buildChartMarkup(seriesId, data.series[seriesId], filteredSeries[seriesId]);
  });

  const detailContainer = document.getElementById("detail-charts");
  if (!detailContainer) {
    return;
  }

  detailContainer.innerHTML = data.metadata.detail_chart_ids
    .map((seriesId) => {
      const series = data.series[seriesId];
      return `
        <article class="chart-card">
          <h2>${series.label}</h2>
          <div id="detail-chart-${seriesId}">
            ${buildChartMarkup(seriesId, series, filteredSeries[seriesId])}
          </div>
        </article>
      `;
    })
    .join("");
}

function computeDashboardState(data, filteredSeries) {
  const thresholds = data.metadata.trend_thresholds || {};
  const seriesSummary = {};

  Object.entries(filteredSeries).forEach(([seriesId, points]) => {
    seriesSummary[seriesId] = summarizeWindow(points);
  });

  const trends = {};
  DETAIL_SIGNAL_SERIES.forEach((seriesId) => {
    const summary = seriesSummary[seriesId];
    trends[seriesId] = summary
      ? classifyTrend(summary.start, summary.end, thresholds[seriesId] || 0)
      : "数据不足";
  });

  const canEvaluateBinary = seriesSummary.xau && seriesSummary.credit_oas_hy && seriesSummary.nominal10y;
  const binarySignals = canEvaluateBinary
    ? computeBinarySignals({
        xau: seriesSummary.xau,
        credit_oas_hy: seriesSummary.credit_oas_hy,
        nominal10y: seriesSummary.nominal10y,
      })
    : {
        goldUp: false,
        creditTightening: false,
        bondYieldDown: false,
      };

  const recentTurnsNegativeFlag =
    recentTurnNegative(filteredSeries.tips10y || []) && recentTurnNegative(filteredSeries.dxy || []);
  const sp500Return = seriesSummary.sp500 ? seriesSummary.sp500.returnRate : 0;
  const entryType =
    trends.tips10y && trends.dxy && trends.nominal10y
      ? computeEntryType({
          trends,
          recentTurnsNegative: recentTurnsNegativeFlag,
          binarySignals,
          sp500Return,
        })
      : "观察";
  const quadrant = computeQuadrantState(trends.dxy, trends.tips10y);

  return {
    trends,
    binarySignals,
    recentTurnsNegative: recentTurnsNegativeFlag,
    sp500Return,
    entryType,
    quadrant,
    seriesSummary,
  };
}

function renderHeroSummary(state) {
  const entryNode = document.getElementById("hero-entry-type");
  const summaryNode = document.getElementById("hero-summary");
  if (entryNode) {
    entryNode.textContent = state.entryType;
  }
  if (summaryNode) {
    const parts = [
      `TIPS ${state.trends.tips10y}`,
      `DXY ${state.trends.dxy}`,
      `名义利率 ${state.trends.nominal10y}`,
      `标普500区间回报 ${formatPercent(state.sp500Return)}`,
    ];
    if (state.recentTurnsNegative) {
      parts.push("近 5 个有效点 TIPS 与 DXY 同步走弱");
    }
    summaryNode.textContent = parts.join("，");
  }
}

function renderSignalChecklist(state) {
  const checklist = document.getElementById("signal-checklist");
  if (!checklist) {
    return;
  }

  const boolText = (value) => (value ? "是" : "否");
  checklist.innerHTML = `
    <h2>信号判断清单</h2>
    <div class="signal-grid">
      <article class="signal-item">TIPS：${state.trends.tips10y}</article>
      <article class="signal-item">DXY：${state.trends.dxy}</article>
      <article class="signal-item">名义利率：${state.trends.nominal10y}</article>
      <article class="signal-item">实际利率：${state.trends.breakeven10y}</article>
      <article class="signal-item">黄金价格是否上涨：${boolText(state.binarySignals.goldUp)}</article>
      <article class="signal-item">信用价差是否收窄：${boolText(state.binarySignals.creditTightening)}</article>
      <article class="signal-item">债券利率是否下降：${boolText(state.binarySignals.bondYieldDown)}</article>
      <article class="signal-item">近 5 个有效点 TIPS 与 DXY 是否同步转弱：${boolText(state.recentTurnsNegative)}</article>
      <article class="signal-item">标普500区间回报：${formatPercent(state.sp500Return)}</article>
      <article class="signal-item">入场类型：${state.entryType}</article>
    </div>
  `;
}

function renderQuadrant(panel, quadrant) {
  if (!panel) {
    return;
  }

  panel.innerHTML = `
    <h2>四象限定性</h2>
    <p class="quadrant-status">${quadrant.label}</p>
    <p class="quadrant-copy">${QUADRANT_COPY[quadrant.key]}</p>
    <div class="quadrant-axes">
      <div>DXY：左侧下降，右侧上升</div>
      <div>TIPS：上方上升，下方下降</div>
    </div>
    <div class="quadrant-star">★ 当前象限：${quadrant.label}</div>
  `;
}

function getAvailableDateBounds(data) {
  const allPoints = Object.values(data.series).flatMap((series) => series.points);
  const dates = allPoints.map((point) => point.date).sort();
  return {
    min: dates[0],
    max: dates[dates.length - 1],
  };
}

function normalizeRange(startValue, endValue, fallbackRange) {
  const start = startValue || fallbackRange.start;
  const end = endValue || fallbackRange.end;
  if (start <= end) {
    return { start, end };
  }
  return { start: end, end: start };
}

function filterSeriesForRange(data, start, end) {
  return Object.fromEntries(
    Object.entries(data.series).map(([seriesId, series]) => [seriesId, slicePointsInRange(series.points, start, end)]),
  );
}

function renderDashboard(data, range) {
  const filteredSeries = filterSeriesForRange(data, range.start, range.end);
  const state = computeDashboardState(data, filteredSeries);

  renderHeroSummary(state);
  renderCharts(data, filteredSeries);
  renderSignalChecklist(state);
  renderQuadrant(document.getElementById("quadrant-panel"), state.quadrant);
}

function updateDateDisplay(displayNode, value) {
  if (displayNode) {
    displayNode.textContent = value;
  }
}

function openDatePicker(input) {
  if (!input) {
    return;
  }
  if (typeof input.showPicker === "function") {
    input.showPicker();
    return;
  }
  input.focus();
  input.click();
}

async function initDashboard() {
  const startInput = document.getElementById("start-date");
  const endInput = document.getElementById("end-date");
  const startDisplay = document.getElementById("start-date-display");
  const endDisplay = document.getElementById("end-date-display");
  const applyButton = document.getElementById("apply-filters");
  if (!startInput || !endInput || !startDisplay || !endDisplay || !applyButton) {
    return;
  }

  try {
    const data = await loadDashboardData();
    const bounds = getAvailableDateBounds(data);
    const fallbackRange = computeDefaultDateRange(bounds.min, bounds.max);

    startInput.min = bounds.min;
    startInput.max = bounds.max;
    endInput.min = bounds.min;
    endInput.max = bounds.max;
    startInput.value = fallbackRange.start;
    endInput.value = fallbackRange.end;
    updateDateDisplay(startDisplay, startInput.value);
    updateDateDisplay(endDisplay, endInput.value);

    startDisplay.addEventListener("click", () => openDatePicker(startInput));
    endDisplay.addEventListener("click", () => openDatePicker(endInput));

    startInput.addEventListener("change", () => {
      updateDateDisplay(startDisplay, startInput.value || fallbackRange.start);
    });
    endInput.addEventListener("change", () => {
      updateDateDisplay(endDisplay, endInput.value || fallbackRange.end);
    });

    applyButton.addEventListener("click", () => {
      const range = normalizeRange(startInput.value, endInput.value, fallbackRange);
      startInput.value = range.start;
      endInput.value = range.end;
      updateDateDisplay(startDisplay, range.start);
      updateDateDisplay(endDisplay, range.end);
      renderDashboard(data, range);
    });

    renderDashboard(data, fallbackRange);
  } catch (error) {
    const summaryNode = document.getElementById("hero-summary");
    const detailContainer = document.getElementById("detail-charts");
    const signalChecklist = document.getElementById("signal-checklist");
    const quadrantPanel = document.getElementById("quadrant-panel");
    const message = error instanceof Error ? error.message : "加载数据失败";

    if (summaryNode) {
      summaryNode.textContent = message;
    }
    if (detailContainer) {
      detailContainer.innerHTML = `<p class="empty-state">${message}</p>`;
    }
    if (signalChecklist) {
      signalChecklist.innerHTML = `<h2>信号判断清单</h2><p class="empty-state">${message}</p>`;
    }
    if (quadrantPanel) {
      quadrantPanel.innerHTML = `<h2>四象限定性</h2><p class="empty-state">${message}</p>`;
    }
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    initDashboard();
  });
}

if (typeof module !== "undefined") {
  module.exports = {
    classifyTrend,
    computeBinarySignals,
    computeEntryType,
    computeQuadrantState,
    buildSvgLineChart,
    loadDashboardData,
    slicePointsInRange,
    summarizeWindow,
    recentTurnNegative,
    computeDashboardState,
    computeDefaultDateRange,
    normalizeRange,
  };
}
