const CHART_HEIGHT = 280;
const MAX_POINTS_RENDER = 280;
const Y_TICKS = 5;
const X_TICKS = 6;

const CHARTS_CONFIG = [
    {
        chartId: "chartTDS",
        emptyId: "emptyTDS",
        seriesAntesId: "tds-series-antes-data",
        seriesDepoisId: "tds-series-depois-data",
        lastReadingId: "lastReadingTDS",
        yLabel: "ppm",
        colorAntes: "#7f4df5",
        colorDepois: "#00be6f",
    },
    {
        chartId: "chartTemperatura",
        emptyId: "emptyTemperatura",
        seriesAntesId: "temperatura-series-antes-data",
        seriesDepoisId: "temperatura-series-depois-data",
        lastReadingId: "lastReadingTemperatura",
        yLabel: "celsius",
        colorAntes: "#ff7a00",
        colorDepois: "#16a34a",
    },
    {
        chartId: "chartTurbidez",
        emptyId: "emptyTurbidez",
        seriesAntesId: "turbidez-series-antes-data",
        seriesDepoisId: "turbidez-series-depois-data",
        lastReadingId: "lastReadingTurbidez",
        yLabel: "ntu",
        colorAntes: "#3b82f6",
        colorDepois: "#9333ea",
    },
    {
        chartId: "chartPH",
        emptyId: "emptyPH",
        seriesAntesId: "ph-series-antes-data",
        seriesDepoisId: "ph-series-depois-data",
        lastReadingId: "lastReadingPH",
        yLabel: "pH",
        colorAntes: "#0ea5e9",
        colorDepois: "#10b981",
    },
];

function getJsonScriptData(id) {
    const element = document.getElementById(id);
    if (!element) {
        return [];
    }

    try {
        return JSON.parse(element.textContent);
    } catch (error) {
        console.error(`Falha ao parsear ${id}`, error);
        return [];
    }
}

function normalizePoints(rawSeries) {
    if (!Array.isArray(rawSeries)) {
        return [];
    }

    const points = [];
    for (const item of rawSeries) {
        if (!item || typeof item !== "object") {
            continue;
        }

        const x = String(item.x || "-");
        const y = Number(item.y);
        if (!Number.isFinite(y)) {
            continue;
        }

        points.push({ x, y: Number(y.toFixed(2)) });
    }

    return points;
}

function mergeAdjacentEqualLabels(series) {
    if (!series.length) {
        return [];
    }

    const merged = [];
    let currentLabel = series[0].x;
    let sum = series[0].y;
    let count = 1;

    for (let i = 1; i < series.length; i++) {
        const point = series[i];
        if (point.x === currentLabel) {
            sum += point.y;
            count += 1;
            continue;
        }

        merged.push({
            x: currentLabel,
            y: Number((sum / count).toFixed(2)),
        });

        currentLabel = point.x;
        sum = point.y;
        count = 1;
    }

    merged.push({
        x: currentLabel,
        y: Number((sum / count).toFixed(2)),
    });

    return merged;
}

function downsampleEvenly(series, maxPoints = MAX_POINTS_RENDER) {
    if (series.length <= maxPoints) {
        return series;
    }

    const sampled = [series[0]];
    const lastIndex = series.length - 1;
    const middleTarget = maxPoints - 2;
    const step = (series.length - 2) / middleTarget;
    let lastPushedIndex = 0;

    for (let i = 1; i <= middleTarget; i++) {
        const idx = Math.min(
            lastIndex - 1,
            Math.max(1, Math.round(i * step)),
        );
        if (idx === lastPushedIndex) {
            continue;
        }
        sampled.push(series[idx]);
        lastPushedIndex = idx;
    }

    sampled.push(series[lastIndex]);
    return sampled;
}

function optimizeSeries(series) {
    const merged = mergeAdjacentEqualLabels(series);
    return downsampleEvenly(merged, MAX_POINTS_RENDER);
}

function prepareSeries(config) {
    const antes = optimizeSeries(
        normalizePoints(getJsonScriptData(config.seriesAntesId)),
    );
    const depois = optimizeSeries(
        normalizePoints(getJsonScriptData(config.seriesDepoisId)),
    );

    return { antes, depois };
}

function createSvgElement(tagName) {
    return document.createElementNS("http://www.w3.org/2000/svg", tagName);
}

function getUniqueLabels(...seriesList) {
    const labels = [];
    const seen = new Set();

    seriesList.forEach((series) => {
        series.forEach((point) => {
            if (!seen.has(point.x)) {
                seen.add(point.x);
                labels.push(point.x);
            }
        });
    });

    return labels;
}

function createYScaleBounds(seriesAntes, seriesDepois) {
    const values = [...seriesAntes, ...seriesDepois].map((p) => p.y);
    let min = Math.min(...values);
    let max = Math.max(...values);

    if (min === max) {
        min -= 1;
        max += 1;
    }

    const padding = (max - min) * 0.08;
    return {
        min: min - padding,
        max: max + padding,
    };
}

function renderGrid(svg, dims) {
    const { left, top, width, height } = dims;

    for (let i = 0; i <= Y_TICKS; i++) {
        const y = top + (i / Y_TICKS) * height;

        const gridLine = createSvgElement("line");
        gridLine.setAttribute("x1", String(left));
        gridLine.setAttribute("x2", String(left + width));
        gridLine.setAttribute("y1", String(y));
        gridLine.setAttribute("y2", String(y));
        gridLine.setAttribute("stroke", "#edf1f7");
        gridLine.setAttribute("stroke-width", "1");
        svg.appendChild(gridLine);
    }

    const axisX = createSvgElement("line");
    axisX.setAttribute("x1", String(left));
    axisX.setAttribute("x2", String(left + width));
    axisX.setAttribute("y1", String(top + height));
    axisX.setAttribute("y2", String(top + height));
    axisX.setAttribute("stroke", "#9aa3b2");
    axisX.setAttribute("stroke-width", "1.1");
    svg.appendChild(axisX);

    const axisY = createSvgElement("line");
    axisY.setAttribute("x1", String(left));
    axisY.setAttribute("x2", String(left));
    axisY.setAttribute("y1", String(top));
    axisY.setAttribute("y2", String(top + height));
    axisY.setAttribute("stroke", "#9aa3b2");
    axisY.setAttribute("stroke-width", "1.1");
    svg.appendChild(axisY);
}

function renderYTicks(svg, dims, yBounds, yLabel) {
    const { left, top, height } = dims;

    for (let i = 0; i <= Y_TICKS; i++) {
        const ratio = i / Y_TICKS;
        const y = top + ratio * height;
        const value = yBounds.max - ratio * (yBounds.max - yBounds.min);

        const text = createSvgElement("text");
        text.setAttribute("x", String(left - 8));
        text.setAttribute("y", String(y + 4));
        text.setAttribute("text-anchor", "end");
        text.setAttribute("font-size", "11");
        text.setAttribute("fill", "#667085");
        text.textContent = value.toFixed(2);
        svg.appendChild(text);
    }

    const axisLabel = createSvgElement("text");
    axisLabel.setAttribute("x", "14");
    axisLabel.setAttribute("y", String(top - 8));
    axisLabel.setAttribute("font-size", "11");
    axisLabel.setAttribute("fill", "#667085");
    axisLabel.textContent = yLabel;
    svg.appendChild(axisLabel);
}

function renderXTicks(svg, dims, labels) {
    const { left, top, width, height } = dims;
    if (!labels.length) {
        return;
    }

    const tickCount = Math.min(X_TICKS, labels.length);
    const step = labels.length > 1 ? (labels.length - 1) / (tickCount - 1 || 1) : 1;

    for (let i = 0; i < tickCount; i++) {
        const labelIndex = Math.min(
            labels.length - 1,
            Math.round(i * step),
        );
        const x = labels.length <= 1
            ? left + width / 2
            : left + (labelIndex / (labels.length - 1)) * width;
        const y = top + height + 16;

        const tickText = createSvgElement("text");
        tickText.setAttribute("x", String(x));
        tickText.setAttribute("y", String(y));
        tickText.setAttribute("text-anchor", "middle");
        tickText.setAttribute("font-size", "10");
        tickText.setAttribute("fill", "#667085");
        tickText.textContent = labels[labelIndex];
        svg.appendChild(tickText);
    }
}

function renderLineSeries(svg, series, color, mapX, mapY, drawMarkers) {
    if (!series.length) {
        return;
    }

    let pathData = "";
    for (let i = 0; i < series.length; i++) {
        const point = series[i];
        const cmd = i === 0 ? "M" : "L";
        pathData += `${cmd}${mapX(point.x)} ${mapY(point.y)} `;
    }

    const path = createSvgElement("path");
    path.setAttribute("d", pathData.trim());
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", color);
    path.setAttribute("stroke-width", "1.8");
    path.setAttribute("stroke-opacity", "0.8");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.appendChild(path);

    if (drawMarkers) {
        series.forEach((point) => {
            const circle = createSvgElement("circle");
            circle.setAttribute("cx", String(mapX(point.x)));
            circle.setAttribute("cy", String(mapY(point.y)));
            circle.setAttribute("r", "2.8");
            circle.setAttribute("fill", color);
            circle.setAttribute("stroke", "#ffffff");
            circle.setAttribute("stroke-width", "0.8");
            svg.appendChild(circle);
        });
    }
}

function updateLastReadingText(config, labels, seriesAntes, seriesDepois) {
    const target = document.getElementById(config.lastReadingId);
    if (!target) {
        return;
    }

    if (!labels.length) {
        target.textContent = "Ultima leitura: --";
        return;
    }

    const ultimaHora = labels[labels.length - 1];
    const ultimaAntes = seriesAntes.length
        ? `${seriesAntes[seriesAntes.length - 1].y.toFixed(2)} ${config.yLabel}`
        : "--";
    const ultimaDepois = seriesDepois.length
        ? `${seriesDepois[seriesDepois.length - 1].y.toFixed(2)} ${config.yLabel}`
        : "--";

    target.textContent = `Ultima leitura (${ultimaHora}) | Antes: ${ultimaAntes} | Depois: ${ultimaDepois}`;
}

function renderLegend(target, config, seriesAntes, seriesDepois) {
    const latestAntes = seriesAntes.length ? seriesAntes[seriesAntes.length - 1].y : null;
    const latestDepois = seriesDepois.length ? seriesDepois[seriesDepois.length - 1].y : null;

    const legend = document.createElement("div");
    legend.className = "timeseries-legend";

    const itemAntes = document.createElement("div");
    itemAntes.className = "timeseries-legend-item";
    itemAntes.innerHTML = `
        <span class="timeseries-dot" style="background:${config.colorAntes}"></span>
        <span>Antes do tratamento</span>
        <strong>${latestAntes === null ? "--" : latestAntes.toFixed(2)}</strong>
    `;
    legend.appendChild(itemAntes);

    const itemDepois = document.createElement("div");
    itemDepois.className = "timeseries-legend-item";
    itemDepois.innerHTML = `
        <span class="timeseries-dot" style="background:${config.colorDepois}"></span>
        <span>Depois do tratamento</span>
        <strong>${latestDepois === null ? "--" : latestDepois.toFixed(2)}</strong>
    `;
    legend.appendChild(itemDepois);

    target.appendChild(legend);
}

function renderChart(config) {
    const chartElement = document.getElementById(config.chartId);
    const emptyElement = document.getElementById(config.emptyId);
    if (!chartElement || !emptyElement) {
        return;
    }

    const { antes, depois } = prepareSeries(config);
    if (!antes.length && !depois.length) {
        chartElement.hidden = true;
        emptyElement.hidden = false;
        updateLastReadingText(config, [], [], []);
        return;
    }

    chartElement.hidden = false;
    emptyElement.hidden = true;
    chartElement.innerHTML = "";

    const width = Math.max(chartElement.clientWidth || 640, 320);
    const height = CHART_HEIGHT;
    const margins = { top: 20, right: 12, bottom: 38, left: 52 };
    const dims = {
        left: margins.left,
        top: margins.top,
        width: width - margins.left - margins.right,
        height: height - margins.top - margins.bottom,
    };

    const labels = getUniqueLabels(antes, depois);
    const labelToIndex = new Map(labels.map((label, index) => [label, index]));
    const yBounds = createYScaleBounds(antes, depois);
    const drawMarkers = true;

    const mapX = (label) => {
        if (labels.length <= 1) {
            return dims.left + dims.width / 2;
        }
        const idx = labelToIndex.get(label) || 0;
        return dims.left + (idx / (labels.length - 1)) * dims.width;
    };

    const mapY = (value) => {
        const ratio = (value - yBounds.min) / (yBounds.max - yBounds.min);
        return dims.top + dims.height - ratio * dims.height;
    };

    const root = document.createElement("div");
    root.className = "timeseries-root";

    const svg = createSvgElement("svg");
    svg.classList.add("timeseries-svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", String(height));

    renderGrid(svg, dims);
    renderYTicks(svg, dims, yBounds, config.yLabel);
    renderXTicks(svg, dims, labels);
    renderLineSeries(svg, antes, config.colorAntes, mapX, mapY, drawMarkers);
    renderLineSeries(svg, depois, config.colorDepois, mapX, mapY, drawMarkers);

    root.appendChild(svg);
    renderLegend(root, config, antes, depois);
    chartElement.appendChild(root);
    updateLastReadingText(config, labels, antes, depois);
}

function renderAllCharts() {
    CHARTS_CONFIG.forEach(renderChart);
}

function initTopToggle() {
    const toggleButtons = document.querySelectorAll("[data-toggle-target]");
    toggleButtons.forEach((button) => {
        const targetId = button.getAttribute("data-toggle-target");
        if (!targetId) {
            return;
        }

        const panel = document.getElementById(targetId);
        if (!panel) {
            return;
        }

        const openLabel = "Fechar edicao do reservatorio";
        const closedLabel = "Editar reservatorio";

        const updateState = (isOpen) => {
            panel.hidden = !isOpen;
            button.classList.toggle("is-open", isOpen);
            button.setAttribute("aria-expanded", isOpen ? "true" : "false");
            button.textContent = isOpen ? openLabel : closedLabel;
        };

        updateState(false);
        button.addEventListener("click", () => {
            const isOpen = button.getAttribute("aria-expanded") === "true";
            updateState(!isOpen);
        });
    });
}

function initCalibrationToggle() {
    const buttons = Array.from(document.querySelectorAll(".calibration-toggle-btn"));
    const panels = Array.from(document.querySelectorAll(".calibration-toggle-panel"));
    if (!buttons.length || !panels.length) {
        return;
    }

    const activate = (targetId) => {
        buttons.forEach((button) => {
            const isActive = button.getAttribute("data-calib-target") === targetId;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-selected", isActive ? "true" : "false");
        });

        panels.forEach((panel) => {
            const isActive = panel.id === targetId;
            panel.hidden = !isActive;
            panel.classList.toggle("is-active", isActive);
        });
    };

    const defaultButton = buttons.find((button) => button.classList.contains("is-active")) || buttons[0];
    activate(defaultButton.getAttribute("data-calib-target"));

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            const targetId = button.getAttribute("data-calib-target");
            if (!targetId) {
                return;
            }
            activate(targetId);
        });
    });
}

let resizeTimer = null;
function handleResize() {
    if (resizeTimer) {
        clearTimeout(resizeTimer);
    }
    resizeTimer = setTimeout(renderAllCharts, 120);
}

function initPage() {
    renderAllCharts();
    initTopToggle();
    initCalibrationToggle();
}

document.addEventListener("DOMContentLoaded", initPage);
window.addEventListener("resize", handleResize);
