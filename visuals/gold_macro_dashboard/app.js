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
const QUADRANT_POSITIONS = {
  "top-left": { x: "28%", y: "28%" },
  "top-right": { x: "72%", y: "28%" },
  "bottom-left": { x: "28%", y: "72%" },
  "bottom-right": { x: "72%", y: "72%" },
  boundary: { x: "50%", y: "50%" },
};

const DETAIL_SIGNAL_SERIES = ["tips10y", "dxy", "nominal10y", "breakeven10y"];
const HERO_CHART_DIMENSIONS = {
  width: 640,
  height: 164,
  marginTop: 16,
  marginRight: 18,
  marginBottom: 32,
  marginLeft: 56,
};
const DETAIL_CHART_DIMENSIONS = {
  width: 640,
  height: 188,
  marginTop: 18,
  marginRight: 18,
  marginBottom: 34,
  marginLeft: 56,
};

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

function formatAxisDateLabel(isoDate) {
  const [year, month, day] = isoDate.split("-");
  return `${year.slice(2)}/${month}/${day}`;
}

function buildChartGeometry(points, dimensions = DETAIL_CHART_DIMENSIONS) {
  const { width, height, marginTop, marginRight, marginBottom, marginLeft } = dimensions;
  const plotWidth = width - marginLeft - marginRight;
  const plotHeight = height - marginTop - marginBottom;
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const ySpan = max - min || 1;

  return {
    width,
    height,
    marginTop,
    marginRight,
    marginBottom,
    marginLeft,
    plotWidth,
    plotHeight,
    min,
    max,
    ySpan,
  };
}

function getPointCoordinates(points, geometry) {
  return points.map((point, index) => {
    const x =
      geometry.marginLeft +
      (index / Math.max(points.length - 1, 1)) * geometry.plotWidth;
    const y =
      geometry.marginTop +
      geometry.plotHeight -
      ((point.value - geometry.min) / geometry.ySpan) * geometry.plotHeight;
    return { ...point, x, y };
  });
}

function buildSvgLineChart(points, stroke, precision = 2, dimensions = DETAIL_CHART_DIMENSIONS) {
  if (!points.length) {
    return '<p class="empty-state">当前时间窗内无有效数据。</p>';
  }

  const geometry = buildChartGeometry(points, dimensions);
  const coordinates = getPointCoordinates(points, geometry);
  const path = coordinates
    .map((point, index) => {
      return `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
    })
    .join(" ");
  const xTickIndexes = Array.from(
    new Set([0, Math.floor((points.length - 1) / 2), Math.max(points.length - 1, 0)]),
  );
  const yTicks = [geometry.max, geometry.min + geometry.ySpan / 2, geometry.min];

  const xAxisLabels = xTickIndexes
    .map((index) => {
      const point = coordinates[index];
      return `
        <text class="chart-axis-label chart-axis-label-x" x="${point.x.toFixed(2)}" y="${(geometry.height - 10).toFixed(
          2,
        )}" text-anchor="middle">${formatAxisDateLabel(point.date)}</text>
      `;
    })
    .join("");

  const yAxisLabels = yTicks
    .map((tickValue) => {
      const y =
        geometry.marginTop +
        geometry.plotHeight -
        ((tickValue - geometry.min) / geometry.ySpan) * geometry.plotHeight;
      return `
        <g>
          <line class="chart-grid-line" x1="${geometry.marginLeft}" y1="${y.toFixed(2)}" x2="${(
            geometry.width - geometry.marginRight
          ).toFixed(2)}" y2="${y.toFixed(2)}"></line>
          <text class="chart-axis-label chart-axis-label-y" x="${(geometry.marginLeft - 10).toFixed(
            2,
          )}" y="${(y + 4).toFixed(2)}" text-anchor="end">${formatValue(tickValue, precision)}</text>
        </g>
      `;
    })
    .join("");

  return `
    <div class="chart-interactive">
      <div class="chart-tooltip" hidden></div>
      <svg viewBox="0 0 ${geometry.width} ${geometry.height}" class="sparkline" role="img" aria-label="折线图">
        <line class="chart-axis-line" x1="${geometry.marginLeft}" y1="${geometry.marginTop}" x2="${geometry.marginLeft}" y2="${(
          geometry.height - geometry.marginBottom
        ).toFixed(2)}"></line>
        <line class="chart-axis-line" x1="${geometry.marginLeft}" y1="${(
          geometry.height - geometry.marginBottom
        ).toFixed(2)}" x2="${(geometry.width - geometry.marginRight).toFixed(2)}" y2="${(
          geometry.height - geometry.marginBottom
        ).toFixed(2)}"></line>
        ${yAxisLabels}
        ${xAxisLabels}
        <path d="${path}" fill="none" stroke="${stroke}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
        <line class="chart-hover-line" x1="0" y1="${geometry.marginTop}" x2="0" y2="${(
          geometry.height - geometry.marginBottom
        ).toFixed(2)}" opacity="0"></line>
        <circle class="chart-hover-dot" cx="0" cy="0" r="4.5" fill="${stroke}" opacity="0"></circle>
      </svg>
    </div>
  `;
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

function getTrendTone(value) {
  if (value === "上升" || value === "是" || value === "确认") {
    return "positive";
  }
  if (value === "下降" || value === "否" || value === "错配") {
    return "negative";
  }
  if (value === "预测" || value === "横盘" || value === "观察" || value === "边界状态") {
    return "neutral";
  }
  return "muted";
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

function buildChartMarkup(seriesId, series, points, dimensions = DETAIL_CHART_DIMENSIONS) {
  const precision = series.value_precision ?? 2;
  const summary = summarizeWindow(points);
  const footer = summary
    ? `<p class="chart-note">${summary.startDate} → ${summary.endDate} ｜ ${formatValue(summary.start, precision)} → ${formatValue(summary.end, precision)}</p>`
    : '<p class="chart-note">当前筛选区间没有可用数据。</p>';

  return `${buildSvgLineChart(points, CHART_STROKES[seriesId] || "#73c6ff", precision, dimensions)}${footer}`;
}

function attachChartInteractions(target, points, precision = 2, dimensions = DETAIL_CHART_DIMENSIONS) {
  if (!target || !points.length) {
    return;
  }

  const wrapper = target.querySelector(".chart-interactive");
  const svg = target.querySelector(".sparkline");
  const tooltip = target.querySelector(".chart-tooltip");
  const hoverLine = target.querySelector(".chart-hover-line");
  const hoverDot = target.querySelector(".chart-hover-dot");
  if (!wrapper || !svg || !tooltip || !hoverLine || !hoverDot) {
    return;
  }

  const geometry = buildChartGeometry(points, dimensions);
  const coordinates = getPointCoordinates(points, geometry);

  const hideTooltip = () => {
    tooltip.hidden = true;
    hoverLine.setAttribute("opacity", "0");
    hoverDot.setAttribute("opacity", "0");
  };

  const showTooltip = (event) => {
    const rect = svg.getBoundingClientRect();
    const ratio = geometry.width / rect.width;
    const pointerX = (event.clientX - rect.left) * ratio;
    const relativeX = Math.max(
      0,
      Math.min(pointerX - geometry.marginLeft, geometry.plotWidth),
    );
    const step = geometry.plotWidth / Math.max(points.length - 1, 1);
    const index = Math.max(
      0,
      Math.min(points.length - 1, Math.round(step === 0 ? 0 : relativeX / step)),
    );
    const point = coordinates[index];

    hoverLine.setAttribute("x1", point.x.toFixed(2));
    hoverLine.setAttribute("x2", point.x.toFixed(2));
    hoverLine.setAttribute("opacity", "1");
    hoverDot.setAttribute("cx", point.x.toFixed(2));
    hoverDot.setAttribute("cy", point.y.toFixed(2));
    hoverDot.setAttribute("opacity", "1");

    tooltip.hidden = false;
    tooltip.innerHTML = `
      <div class="chart-tooltip-date">${point.date}</div>
      <div class="chart-tooltip-value">${formatValue(point.value, precision)}</div>
    `;
    const wrapperRect = wrapper.getBoundingClientRect();
    const left = Math.min(
      wrapperRect.width - 120,
      Math.max(8, event.clientX - wrapperRect.left + 12),
    );
    const top = Math.max(8, event.clientY - wrapperRect.top - 44);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  };

  wrapper.addEventListener("mouseleave", hideTooltip);
  wrapper.addEventListener("mousemove", showTooltip);
}

function renderCharts(data, filteredSeries) {
  data.metadata.hero_chart_ids.forEach((seriesId) => {
    const target = document.getElementById(`chart-${seriesId}`);
    if (!target) {
      return;
    }
    target.innerHTML = buildChartMarkup(
      seriesId,
      data.series[seriesId],
      filteredSeries[seriesId],
      HERO_CHART_DIMENSIONS,
    );
    attachChartInteractions(
      target,
      filteredSeries[seriesId],
      data.series[seriesId].value_precision ?? 2,
      HERO_CHART_DIMENSIONS,
    );
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
            ${buildChartMarkup(seriesId, series, filteredSeries[seriesId], DETAIL_CHART_DIMENSIONS)}
          </div>
        </article>
      `;
    })
    .join("");

  data.metadata.detail_chart_ids.forEach((seriesId) => {
    const target = document.getElementById(`detail-chart-${seriesId}`);
    if (!target) {
      return;
    }
    attachChartInteractions(
      target,
      filteredSeries[seriesId],
      data.series[seriesId].value_precision ?? 2,
      DETAIL_CHART_DIMENSIONS,
    );
  });
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
  const items = [
    { label: "TIPS", value: state.trends.tips10y, hint: "10年期TIPS实际收益率" },
    { label: "DXY", value: state.trends.dxy, hint: "美元指数方向" },
    { label: "名义利率", value: state.trends.nominal10y, hint: "10年期美债收益率" },
    { label: "实际利率", value: state.trends.breakeven10y, hint: "10年盈亏平衡通胀率" },
    { label: "黄金上涨", value: boolText(state.binarySignals.goldUp), hint: "确认信号" },
    { label: "信用收窄", value: boolText(state.binarySignals.creditTightening), hint: "高收益信用利差_OAS" },
    { label: "债券利率下降", value: boolText(state.binarySignals.bondYieldDown), hint: "确认信号" },
    { label: "近5点转弱", value: boolText(state.recentTurnsNegative), hint: "TIPS 与 DXY 同步转弱" },
    { label: "标普500回报", value: formatPercent(state.sp500Return), hint: "筛选区间收益率" },
    { label: "入场类型", value: state.entryType, hint: "预测 / 确认 / 错配" },
  ];

  checklist.innerHTML = `
    <h2>信号判断清单</h2>
    <div class="signal-grid">
      ${items
        .map(
          (item) => `
            <article class="signal-item signal-item-${getTrendTone(item.value)}">
              <div class="signal-item-head">
                <span class="signal-item-label">${item.label}</span>
                <span class="signal-item-badge signal-item-badge-${getTrendTone(item.value)}">${item.value}</span>
              </div>
              <p class="signal-item-hint">${item.hint}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderQuadrant(panel, quadrant) {
  if (!panel) {
    return;
  }

  const star = QUADRANT_POSITIONS[quadrant.key] || QUADRANT_POSITIONS.boundary;

  panel.innerHTML = `
    <h2>四象限定性</h2>
    <p class="quadrant-status">${quadrant.label}</p>
    <p class="quadrant-copy">${QUADRANT_COPY[quadrant.key]}</p>
    <div class="quadrant-axes">
      <div>DXY：左侧下降，右侧上升</div>
      <div>TIPS：上方上升，下方下降</div>
    </div>
    <div class="quadrant-matrix" aria-label="四象限图">
      <div class="quadrant-axis quadrant-axis-x">DXY</div>
      <div class="quadrant-axis quadrant-axis-y">TIPS</div>
      <div class="quadrant-direction quadrant-direction-left">下降</div>
      <div class="quadrant-direction quadrant-direction-right">上升</div>
      <div class="quadrant-direction quadrant-direction-top">上升</div>
      <div class="quadrant-direction quadrant-direction-bottom">下降</div>
      <div class="quadrant-cell quadrant-cell-top-left">
        <strong>再分配区</strong>
        <span>债券弱，黄金弱，股票可涨但不稳</span>
      </div>
      <div class="quadrant-cell quadrant-cell-top-right">
        <strong>紧缩风险区</strong>
        <span>股票下跌风险高，黄金弱，债券弱</span>
      </div>
      <div class="quadrant-cell quadrant-cell-bottom-left">
        <strong>全面宽松区</strong>
        <span>股票涨，黄金走强，债券走强</span>
      </div>
      <div class="quadrant-cell quadrant-cell-bottom-right">
        <strong>美元避险区</strong>
        <span>股票不稳，黄金中性，债券走强</span>
      </div>
      <div class="quadrant-star-marker" style="left:${star.x};top:${star.y};">★</div>
    </div>
    <div class="quadrant-star">当前象限：${quadrant.label}</div>
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
    buildChartGeometry,
    formatAxisDateLabel,
    HERO_CHART_DIMENSIONS,
    DETAIL_CHART_DIMENSIONS,
  };
}
