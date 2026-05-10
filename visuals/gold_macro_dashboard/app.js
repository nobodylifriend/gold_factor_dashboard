const CHART_STROKES = {
  xau: "#f4c55c",
  xau_monthly: "#f7d98e",
  sp500: "#73c6ff",
  nasdaq100: "#6be7c1",
  tips10y: "#73c6ff",
  tips5y: "#8fe1ff",
  tips30y: "#b7c9ff",
  dxy: "#f4c55c",
  nominal10y: "#ff8e8e",
  breakeven10y: "#9dc9ff",
  breakeven5y: "#69d7ff",
  forward5y5y: "#c0d6ff",
  credit_oas_hy: "#f7a35b",
  sofr: "#8be0ff",
  gvz: "#ffb86b",
  gld_holdings: "#d2e277",
  gold_etf_flows: "#87d9a2",
  fedfunds: "#c9a0ff",
  m2: "#6be7c1",
  cpi_yoy: "#ff8e8e",
  core_cpi_yoy: "#ffb5a7",
  pce_yoy: "#73c6ff",
  core_pce_yoy: "#9dc9ff",
};

const QUADRANT_COPY = {
  "top-left": "再分配区：债券偏强，黄金偏强，股票可涨但不稳。",
  "top-right": "紧缩风险区：股票下跌风险高，黄金偏弱，债券偏弱，流动性紧且美元走强。",
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
    const x = geometry.marginLeft + (index / Math.max(points.length - 1, 1)) * geometry.plotWidth;
    const y =
      geometry.marginTop +
      geometry.plotHeight -
      ((point.value - geometry.min) / geometry.ySpan) * geometry.plotHeight;
    return { ...point, x, y };
  });
}

function formatPercent(value) {
  return `${(value * 100).toFixed(2)}%`;
}

function formatValue(value, precision = 2) {
  return Number(value).toFixed(precision);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildSvgLineChart(points, stroke, precision = 2, dimensions = DETAIL_CHART_DIMENSIONS) {
  if (!points.length) {
    return '<p class="empty-state">当前时间窗内无有效数据。</p>';
  }

  const geometry = buildChartGeometry(points, dimensions);
  const coordinates = getPointCoordinates(points, geometry);
  const path = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");
  const xTickIndexes = Array.from(new Set([0, Math.floor((points.length - 1) / 2), Math.max(points.length - 1, 0)]));
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

function buildSeriesWindow(points, start, end) {
  const minVisiblePoints = Math.min(10, points.length);
  const inRangePoints = points.filter((point) => point.date >= start && point.date <= end);
  const isFallback = inRangePoints.length < minVisiblePoints;
  return {
    points: isFallback ? points.slice(-minVisiblePoints) : inRangePoints,
    isFallback,
    inRangeCount: inRangePoints.length,
  };
}

function slicePointsInRange(points, start, end) {
  return buildSeriesWindow(points, start, end).points;
}

function summarizeWindow(points) {
  if (!points.length) {
    return null;
  }
  return {
    start: points[0].value,
    end: points[points.length - 1].value,
    returnRate: points[0].value === 0 ? 0 : (points[points.length - 1].value - points[0].value) / points[0].value,
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

function buildExportFileName(range) {
  return `gold-macro-dashboard-${range.start}_to_${range.end}.png`;
}

function setExportButtonState(button, isExporting) {
  if (!button) {
    return;
  }
  button.disabled = isExporting;
  button.textContent = isExporting ? "导出中..." : "导出图片";
}

function triggerImageDownload(dataUrl, fileName) {
  const anchor = document.createElement("a");
  anchor.href = dataUrl;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

async function exportDashboardImage(range, button) {
  const shell = document.querySelector(".page-shell");
  const exporter = typeof window !== "undefined" ? window.htmlToImage : null;
  if (!shell || !exporter || typeof exporter.toPng !== "function") {
    throw new Error("导出组件加载失败，请刷新页面后重试");
  }

  document.body.classList.add("is-exporting-image");
  setExportButtonState(button, true);

  try {
    await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
    const dataUrl = await exporter.toPng(shell, {
      cacheBust: true,
      backgroundColor: "#07111f",
      pixelRatio: Math.max(window.devicePixelRatio || 1, 2),
    });
    triggerImageDownload(dataUrl, buildExportFileName(range));
  } finally {
    document.body.classList.remove("is-exporting-image");
    setExportButtonState(button, false);
  }
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

function buildChartMarkup(seriesId, series, seriesWindow, dimensions = DETAIL_CHART_DIMENSIONS) {
  const points = seriesWindow?.points || [];
  const precision = series.value_precision ?? 2;
  const summary = summarizeWindow(points);
  if (summary && seriesWindow?.isFallback) {
    return `${buildSvgLineChart(points, CHART_STROKES[seriesId] || "#73c6ff", precision, dimensions)}<p class="chart-note">${summary.startDate} 鑷?${summary.endDate} 路 ${formatValue(summary.start, precision)} 鈫?${formatValue(summary.end, precision)}</p><p class="chart-note chart-note-warning">当前区间数据不足 10 个点，已回退显示最近 10 个数据点。</p>`;
  }
  const footer = summary
    ? `<p class="chart-note">${summary.startDate} 至 ${summary.endDate} · ${formatValue(summary.start, precision)} → ${formatValue(summary.end, precision)}</p>`
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
    const relativeX = Math.max(0, Math.min(pointerX - geometry.marginLeft, geometry.plotWidth));
    const step = geometry.plotWidth / Math.max(points.length - 1, 1);
    const index = Math.max(0, Math.min(points.length - 1, Math.round(step === 0 ? 0 : relativeX / step)));
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
    const left = Math.min(wrapperRect.width - 120, Math.max(8, event.clientX - wrapperRect.left + 12));
    const top = Math.max(8, event.clientY - wrapperRect.top - 44);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  };

  wrapper.addEventListener("mouseleave", hideTooltip);
  wrapper.addEventListener("mousemove", showTooltip);
}

function buildTabButtonMarkup(tab, activeTabId) {
  const isActive = tab.id === activeTabId;
  return `
    <button
      class="tab-button"
      type="button"
      role="tab"
      data-tab-id="${tab.id}"
      aria-selected="${isActive ? "true" : "false"}"
    >
      <span class="tab-button-label">${tab.label}</span>
      <span class="tab-button-description">${tab.description}</span>
    </button>
  `;
}

function buildTopicSummaryMarkup(items) {
  return `
    <h2>专题速览</h2>
    <p class="topic-summary-caption">只保留最重要的三条判断，引导你进入对应专题继续看。</p>
    <div class="topic-summary-grid">
      ${items
        .map(
          (item) => `
            <article class="topic-summary-card tone-${item.tone}" data-summary-key="${item.key}">
              <span class="topic-summary-label">${item.label}</span>
              <strong class="topic-summary-value">${item.value}</strong>
            </article>
      `,
        )
        .join("")}
    </div>
  `;
}

function computeTabInsightItems(layout, seriesSummary) {
  if (!layout?.insights?.length) {
    return [];
  }

  return layout.insights.map((insight) => {
    const summary = seriesSummary?.[insight.series_id];
    if (!summary) {
      return {
        key: insight.key,
        label: insight.label,
        value: "数据不足",
        tone: "muted",
      };
    }

    if (summary.end > summary.start) {
      return {
        key: insight.key,
        label: insight.label,
        value: insight.up_text,
        tone: insight.up_tone || "positive",
      };
    }

    if (summary.end < summary.start) {
      return {
        key: insight.key,
        label: insight.label,
        value: insight.down_text,
        tone: insight.down_tone || "negative",
      };
    }

    return {
      key: insight.key,
      label: insight.label,
      value: insight.flat_text || "横盘",
      tone: insight.flat_tone || "neutral",
    };
  });
}

function buildInsightStripMarkup(title, items) {
  return `
    <section class="tab-insight-strip">
      <h3 class="tab-section-title">${title}</h3>
      <div class="tab-insight-grid">
        ${items
          .map(
            (item) => `
              <article class="tab-insight-card tone-${item.tone}" data-insight-key="${item.key}">
                <span class="tab-insight-label">${item.label}</span>
                <strong class="tab-insight-value">${item.value}</strong>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function diffDays(startIsoDate, endIsoDate) {
  const start = parseIsoDate(startIsoDate);
  const end = parseIsoDate(endIsoDate);
  return Math.floor((end - start) / 86400000);
}

function computeFreshnessStatus(series, rangeEnd) {
  if (!series?.frequency_label || !series?.latest_date || !rangeEnd) {
    return null;
  }

  const thresholds = {
    "日频": 10,
    "周频": 21,
    "月频": 45,
    "季频": 120,
    "年频": 400,
  };
  const threshold = thresholds[series.frequency_label];
  if (!threshold) {
    return null;
  }

  const lagDays = diffDays(series.latest_date, rangeEnd);
  if (lagDays > threshold) {
    return { level: "warning", label: "更新偏旧" };
  }
  return null;
}

function buildSeriesMetaText(series) {
  const parts = [];
  if (series?.frequency_label) {
    parts.push(series.frequency_label);
  }
  if (series?.latest_date) {
    parts.push(`最新 ${series.latest_date}`);
  }
  return parts.join(" · ");
}

function buildSeriesTitleMarkup(series) {
  if (!series?.description_zh) {
    return `<h2>${series.label}</h2>`;
  }

  const escapedLabel = escapeHtml(series.label);
  const escapedDescription = escapeHtml(series.description_zh);
  return `
    <div class="chart-title-row">
      <h2>${escapedLabel}</h2>
      <button
        type="button"
        class="chart-info-button"
        aria-label="查看 ${escapedLabel} 指标定义"
        title="${escapedDescription}"
        data-tooltip="${escapedDescription}"
      >?</button>
    </div>
  `;
}

function buildChartCardMarkup(seriesId, series, seriesWindow, rangeEnd) {
  const freshness = computeFreshnessStatus(series, rangeEnd);
  return `
    <article class="chart-card">
      ${buildSeriesTitleMarkup(series)}
      <p class="chart-meta">
        ${buildSeriesMetaText(series)}
        ${freshness ? `<span class="chart-meta-warning">${freshness.label}</span>` : ""}
      </p>
      <div id="series-${seriesId}">
        ${buildChartMarkup(seriesId, series, seriesWindow, DETAIL_CHART_DIMENSIONS)}
      </div>
    </article>
  `;
}

function buildSectionMarkup(section, data, filteredSeries, rangeEnd) {
  return `
    <section class="tab-section">
      <div class="tab-section-header">
        <h3 class="tab-section-title">${section.title}</h3>
        <p class="tab-section-copy">${section.description}</p>
      </div>
      <div class="tab-section-grid">
        ${section.series_ids
          .map((seriesId) => buildChartCardMarkup(seriesId, data.series[seriesId], filteredSeries[seriesId] || [], rangeEnd))
          .join("")}
      </div>
    </section>
  `;
}

function getSummaryTone(summary) {
  if (!summary) {
    return "muted";
  }
  return summary.end >= summary.start ? "positive" : "negative";
}

function buildOverviewSummaryItems(state, seriesSummary) {
  const goldHoldings = seriesSummary.gld_holdings;
  const cpi = seriesSummary.cpi_yoy;

  return [
    {
      key: "gold_summary",
      label: "黄金本体",
      tone: getSummaryTone(seriesSummary.xau),
      value: goldHoldings
        ? `价格${state.seriesSummary.xau.end >= state.seriesSummary.xau.start ? "上行" : "回落"}，GLD${goldHoldings.end >= goldHoldings.start ? "回流" : "减仓"}`
        : `价格${state.seriesSummary.xau.end >= state.seriesSummary.xau.start ? "上行" : "回落"}`,
    },
    {
      key: "rates_summary",
      label: "利率流动性",
      tone: getTrendTone(state.trends.tips10y),
      value: `10Y TIPS ${state.trends.tips10y}，名义利率${state.trends.nominal10y}`,
    },
    {
      key: "inflation_summary",
      label: "通胀预期",
      tone: getTrendTone(state.trends.breakeven10y),
      value: cpi
        ? `盈亏平衡通胀${state.trends.breakeven10y}，CPI 同比 ${formatValue(cpi.end, 2)}`
        : `盈亏平衡通胀${state.trends.breakeven10y}`,
    },
  ];
}

function computeDashboardState(data, filteredSeries) {
  const thresholds = data.metadata.trend_thresholds || {};
  const seriesSummary = {};

  Object.entries(filteredSeries).forEach(([seriesId, seriesWindow]) => {
    seriesSummary[seriesId] = summarizeWindow(seriesWindow.points || []);
  });

  const trends = {};
  DETAIL_SIGNAL_SERIES.forEach((seriesId) => {
    const summary = seriesSummary[seriesId];
    trends[seriesId] = summary ? classifyTrend(summary.start, summary.end, thresholds[seriesId] || 0) : "数据不足";
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
    recentTurnNegative(filteredSeries.tips10y?.points || []) && recentTurnNegative(filteredSeries.dxy?.points || []);
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

function renderHeroCharts(data, filteredSeries, heroChartIds, rangeEnd) {
  const container = document.querySelector(".hero-charts");
  if (!container) {
    return;
  }

  container.innerHTML = heroChartIds
    .map((seriesId) => {
      const freshness = computeFreshnessStatus(data.series[seriesId], rangeEnd);
      return `
        <article class="chart-card">
          ${buildSeriesTitleMarkup(data.series[seriesId])}
          <p class="chart-meta">
            ${buildSeriesMetaText(data.series[seriesId])}
            ${freshness ? `<span class="chart-meta-warning">${freshness.label}</span>` : ""}
          </p>
          <div id="chart-${seriesId}">
            ${buildChartMarkup(seriesId, data.series[seriesId], filteredSeries[seriesId], HERO_CHART_DIMENSIONS)}
          </div>
        </article>
      `;
    })
    .join("");

  heroChartIds.forEach((seriesId) => {
    const target = document.getElementById(`chart-${seriesId}`);
    attachChartInteractions(
      target,
      filteredSeries[seriesId]?.points || [],
      data.series[seriesId].value_precision ?? 2,
      HERO_CHART_DIMENSIONS,
    );
  });
}

function renderDetailCharts(data, filteredSeries, detailChartIds, rangeEnd) {
  const detailContainer = document.getElementById("detail-charts");
  if (!detailContainer) {
    return;
  }

  detailContainer.innerHTML = detailChartIds
    .map((seriesId) => buildChartCardMarkup(seriesId, data.series[seriesId], filteredSeries[seriesId], rangeEnd))
    .join("");

  detailChartIds.forEach((seriesId) => {
    const target = document.getElementById(`series-${seriesId}`);
    attachChartInteractions(
      target,
      filteredSeries[seriesId]?.points || [],
      data.series[seriesId].value_precision ?? 2,
      DETAIL_CHART_DIMENSIONS,
    );
  });
}

function renderSignalChecklist(state) {
  const checklist = document.getElementById("signal-checklist");
  if (!checklist) {
    return;
  }

  const boolText = (value) => (value ? "是" : "否");
  const items = [
    { label: "TIPS", value: state.trends.tips10y, hint: "10年期 TIPS 实际收益率" },
    { label: "DXY", value: state.trends.dxy, hint: "美元指数方向" },
    { label: "名义利率", value: state.trends.nominal10y, hint: "10年期美债收益率" },
    { label: "通胀补偿", value: state.trends.breakeven10y, hint: "10年盈亏平衡通胀率" },
    { label: "黄金上涨", value: boolText(state.binarySignals.goldUp), hint: "确认信号" },
    { label: "信用收窄", value: boolText(state.binarySignals.creditTightening), hint: "高收益信用利差 OAS" },
    { label: "债券利率下降", value: boolText(state.binarySignals.bondYieldDown), hint: "确认信号" },
    { label: "近端转弱", value: boolText(state.recentTurnsNegative), hint: "TIPS 与 DXY 同步转弱" },
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
      <div class="quadrant-cell">
        <strong>再分配区</strong>
        <span>债券偏强，黄金偏强，股票可涨但不稳。</span>
      </div>
      <div class="quadrant-cell">
        <strong>紧缩风险区</strong>
        <span>股票下跌风险高，黄金偏弱，债券偏弱。</span>
      </div>
      <div class="quadrant-cell">
        <strong>全面宽松区</strong>
        <span>股票、黄金、债券同步受益。</span>
      </div>
      <div class="quadrant-cell">
        <strong>美元避险区</strong>
        <span>股票不稳，黄金偏中性，债券偏强。</span>
      </div>
      <div class="quadrant-star-marker" style="left:${star.x};top:${star.y};">★</div>
    </div>
    <div class="quadrant-star">当前位置：${quadrant.label}</div>
  `;
}

function renderOverviewTab(data, filteredSeries, state, range) {
  const overviewLayout = data.tab_layouts.overview;
  const overviewPanel = document.getElementById("overview-panel");
  const topicSummaryPanel = document.getElementById("topic-summary-panel");
  const tabPanels = document.getElementById("tab-panels");

  if (overviewPanel) {
    overviewPanel.classList.remove("is-hidden");
  }
  if (topicSummaryPanel) {
    topicSummaryPanel.classList.remove("is-hidden");
    topicSummaryPanel.innerHTML = buildTopicSummaryMarkup(buildOverviewSummaryItems(state, state.seriesSummary));
  }
  if (tabPanels) {
    tabPanels.classList.add("is-hidden");
    tabPanels.classList.remove("is-active");
    tabPanels.innerHTML = "";
  }

  renderHeroCharts(data, filteredSeries, overviewLayout.hero_chart_ids, range.end);
  renderSignalChecklist(state);
  renderDetailCharts(data, filteredSeries, overviewLayout.detail_chart_ids, range.end);
  renderQuadrant(document.getElementById("quadrant-panel"), state.quadrant);
}

function renderSectionTab(data, filteredSeries, activeTabId, range) {
  const overviewPanel = document.getElementById("overview-panel");
  const topicSummaryPanel = document.getElementById("topic-summary-panel");
  const tabPanels = document.getElementById("tab-panels");
  const layout = data.tab_layouts[activeTabId];
  const tabMeta = data.metadata.tabs.find((tab) => tab.id === activeTabId);
  const seriesSummary = Object.fromEntries(
    Object.entries(filteredSeries).map(([seriesId, seriesWindow]) => [seriesId, summarizeWindow(seriesWindow.points || [])]),
  );
  if (!tabPanels || !layout || !tabMeta) {
    return;
  }

  if (overviewPanel) {
    overviewPanel.classList.add("is-hidden");
  }
  if (topicSummaryPanel) {
    topicSummaryPanel.classList.add("is-hidden");
  }

  tabPanels.classList.remove("is-hidden");
  tabPanels.classList.add("is-active");
  tabPanels.innerHTML = `
    <article class="tab-panel">
      <header class="tab-panel-header">
        <h2 class="tab-panel-title">${tabMeta.label}</h2>
        <p class="tab-panel-copy">${layout.description}</p>
      </header>
      ${buildInsightStripMarkup("专题结论", computeTabInsightItems(layout, seriesSummary))}
      <div class="tab-panel-grid">
        ${layout.sections.map((section) => buildSectionMarkup(section, data, filteredSeries, range.end)).join("")}
      </div>
    </article>
  `;

  layout.sections.forEach((section) => {
    section.series_ids.forEach((seriesId) => {
      const target = document.getElementById(`series-${seriesId}`);
      attachChartInteractions(
        target,
        filteredSeries[seriesId]?.points || [],
        data.series[seriesId].value_precision ?? 2,
        DETAIL_CHART_DIMENSIONS,
      );
    });
  });
}

function renderTabNavigation(data, activeTabId, onSelect) {
  const navigation = document.getElementById("tab-navigation");
  if (!navigation) {
    return;
  }

  navigation.innerHTML = data.metadata.tabs.map((tab) => buildTabButtonMarkup(tab, activeTabId)).join("");
  navigation.querySelectorAll("[data-tab-id]").forEach((button) => {
    button.addEventListener("click", () => {
      onSelect(button.getAttribute("data-tab-id"));
    });
  });
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
    Object.entries(data.series).map(([seriesId, series]) => [seriesId, buildSeriesWindow(series.points, start, end)]),
  );
}

function renderDashboard(data, range, activeTabId, onSelectTab) {
  const filteredSeries = filterSeriesForRange(data, range.start, range.end);
  const state = computeDashboardState(data, filteredSeries);

  renderHeroSummary(state);
  renderTabNavigation(data, activeTabId, onSelectTab);
  if (activeTabId === "overview") {
    renderOverviewTab(data, filteredSeries, state, range);
  } else {
    renderSectionTab(data, filteredSeries, activeTabId, range);
  }
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
  const exportButton = document.getElementById("export-image");
  if (!startInput || !endInput || !startDisplay || !endDisplay || !applyButton || !exportButton) {
    return;
  }

  try {
    const data = await loadDashboardData();
    const bounds = getAvailableDateBounds(data);
    const fallbackRange = computeDefaultDateRange(bounds.min, bounds.max);
    let activeTabId = data.metadata.tab_order?.[0] || "overview";

    startInput.min = bounds.min;
    startInput.max = bounds.max;
    endInput.min = bounds.min;
    endInput.max = bounds.max;
    startInput.value = fallbackRange.start;
    endInput.value = fallbackRange.end;
    updateDateDisplay(startDisplay, startInput.value);
    updateDateDisplay(endDisplay, endInput.value);

    const rerender = () => {
      const range = normalizeRange(startInput.value, endInput.value, fallbackRange);
      startInput.value = range.start;
      endInput.value = range.end;
      updateDateDisplay(startDisplay, range.start);
      updateDateDisplay(endDisplay, range.end);
      renderDashboard(data, range, activeTabId, (nextTabId) => {
        activeTabId = nextTabId;
        rerender();
      });
    };

    startDisplay.addEventListener("click", () => openDatePicker(startInput));
    endDisplay.addEventListener("click", () => openDatePicker(endInput));

    startInput.addEventListener("change", () => updateDateDisplay(startDisplay, startInput.value || fallbackRange.start));
    endInput.addEventListener("change", () => updateDateDisplay(endDisplay, endInput.value || fallbackRange.end));

    applyButton.addEventListener("click", rerender);

    exportButton.addEventListener("click", async () => {
      rerender();
      try {
        await exportDashboardImage(normalizeRange(startInput.value, endInput.value, fallbackRange), exportButton);
      } catch (error) {
        const message = error instanceof Error ? error.message : "导出图片失败";
        window.alert(message);
      }
    });

    rerender();
  } catch (error) {
    const summaryNode = document.getElementById("hero-summary");
    const detailContainer = document.getElementById("detail-charts");
    const signalChecklist = document.getElementById("signal-checklist");
    const quadrantPanel = document.getElementById("quadrant-panel");
    const topicSummaryPanel = document.getElementById("topic-summary-panel");
    const tabPanels = document.getElementById("tab-panels");
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
    if (topicSummaryPanel) {
      topicSummaryPanel.innerHTML = `<h2>专题速览</h2><p class="empty-state">${message}</p>`;
    }
    if (tabPanels) {
      tabPanels.innerHTML = `<article class="tab-panel"><p class="empty-state">${message}</p></article>`;
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
    buildSeriesWindow,
    slicePointsInRange,
    summarizeWindow,
    recentTurnNegative,
    computeDashboardState,
    computeDefaultDateRange,
    normalizeRange,
    buildChartGeometry,
    formatAxisDateLabel,
    buildExportFileName,
    buildTabButtonMarkup,
    buildTopicSummaryMarkup,
    computeTabInsightItems,
    buildInsightStripMarkup,
    buildSeriesMetaText,
    buildSeriesTitleMarkup,
    computeFreshnessStatus,
    HERO_CHART_DIMENSIONS,
    DETAIL_CHART_DIMENSIONS,
  };
}
