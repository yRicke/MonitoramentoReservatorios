const MAX_POINTS_RENDER = 420;
const INITIAL_ZOOM_POINTS = 80;

const CHARTS_CONFIG = [
    {
        chartId: "chartTemperatura",
        emptyId: "emptyTemperatura",
        seriesAntesId: "temperatura-series-antes-data",
        seriesDepoisId: "temperatura-series-depois-data",
        lastReadingId: "lastReadingTemperatura",
        yLabel: "celsius",
        colorAntes: "#ff7a00",
        colorDepois: "#16a34a",
        decimals: 2,
    },
    {
        chartId: "chartTDS",
        emptyId: "emptyTDS",
        seriesAntesId: "tds-series-antes-data",
        seriesDepoisId: "tds-series-depois-data",
        lastReadingId: "lastReadingTDS",
        yLabel: "ppm",
        colorAntes: "#7f4df5",
        colorDepois: "#00be6f",
        decimals: 2,
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
        decimals: 3,
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
        decimals: 2,
    },
];

const chartInstances = new Map();

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

        const xRaw = item.x;
        const y = Number(item.y);
        if (!Number.isFinite(y)) {
            continue;
        }

        let xValue = null;
        let label = "-";
        if (typeof xRaw === "number" && Number.isFinite(xRaw)) {
            xValue = xRaw;
        } else if (typeof xRaw === "string" && xRaw.trim()) {
            const parsed = Date.parse(xRaw);
            xValue = Number.isFinite(parsed) ? parsed : xRaw.trim();
        }

        if (xValue === null) {
            continue;
        }

        if (typeof xValue === "number") {
            label = typeof item.label === "string" && item.label.trim()
                ? item.label.trim()
                : formatDateLabel(xValue);
        } else {
            label = xValue;
        }

        points.push({ x: xValue, y: Number(y.toFixed(4)), label });
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

    for (let i = 1; i < series.length; i += 1) {
        const point = series[i];
        if (point.x === currentLabel) {
            sum += point.y;
            count += 1;
            continue;
        }

        merged.push({
            x: currentLabel,
            y: Number((sum / count).toFixed(4)),
        });

        currentLabel = point.x;
        sum = point.y;
        count = 1;
    }

    merged.push({
        x: currentLabel,
        y: Number((sum / count).toFixed(4)),
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

    for (let i = 1; i <= middleTarget; i += 1) {
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

function updateLastReadingText(config, seriesAntes, seriesDepois) {
    const target = document.getElementById(config.lastReadingId);
    if (!target) {
        return;
    }

    if (!seriesAntes.length && !seriesDepois.length) {
        target.textContent = "Ultima leitura: --";
        return;
    }

    const pontoAntes = seriesAntes.length ? seriesAntes[seriesAntes.length - 1] : null;
    const pontoDepois = seriesDepois.length ? seriesDepois[seriesDepois.length - 1] : null;
    const leituraAntes = pontoAntes
        ? `${pontoAntes.y.toFixed(config.decimals)} ${config.yLabel} em ${pontoAntes.label || pontoAntes.x}`
        : "--";
    const leituraDepois = pontoDepois
        ? `${pontoDepois.y.toFixed(config.decimals)} ${config.yLabel} em ${pontoDepois.label || pontoDepois.x}`
        : "--";

    target.textContent = `Ultima leitura | Antes: ${leituraAntes} | Depois: ${leituraDepois}`;
}

function formatDateLabel(timestampMs) {
    const date = new Date(timestampMs);
    if (Number.isNaN(date.getTime())) {
        return "-";
    }

    const dd = String(date.getDate()).padStart(2, "0");
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const yyyy = date.getFullYear();
    const hh = String(date.getHours()).padStart(2, "0");
    const mi = String(date.getMinutes()).padStart(2, "0");
    const ss = String(date.getSeconds()).padStart(2, "0");
    return `${dd}/${mm}/${yyyy} ${hh}:${mi}:${ss}`;
}

function getXAxisConfig(seriesAntes, seriesDepois) {
    const allPoints = [...seriesAntes, ...seriesDepois];
    const isDatetime = allPoints.length > 0 && allPoints.every((point) => typeof point.x === "number");

    if (!isDatetime) {
        return {
            isDatetime: false,
            config: {
                type: "category",
                labels: {
                    rotate: -28,
                    trim: true,
                    hideOverlappingLabels: true,
                    style: {
                        colors: "#60756d",
                        fontSize: "11px",
                    },
                },
                axisBorder: {
                    color: "#d7e2de",
                },
            },
        };
    }

    const sortedX = allPoints
        .map((point) => point.x)
        .sort((a, b) => a - b);
    const oldest = sortedX[0];
    const newest = sortedX[sortedX.length - 1];
    const zoomStartIndex = Math.max(0, sortedX.length - INITIAL_ZOOM_POINTS);
    const zoomStart = sortedX[zoomStartIndex];

    return {
        isDatetime: true,
        oldest,
        newest,
        zoomStart,
        config: {
            type: "datetime",
            min: oldest,
            max: newest,
            labels: {
                datetimeUTC: false,
                style: {
                    colors: "#60756d",
                    fontSize: "11px",
                },
            },
            axisBorder: {
                color: "#d7e2de",
            },
        },
    };
}

function createApexOptions(config, seriesAntes, seriesDepois) {
    const xAxisMeta = getXAxisConfig(seriesAntes, seriesDepois);
    const isDatetime = xAxisMeta.isDatetime;
    const xAxis = xAxisMeta.config;
    const chartEvents = {};

    if (isDatetime) {
        const oldest = xAxisMeta.oldest;
        const newest = xAxisMeta.newest;
        const zoomStart = xAxisMeta.zoomStart;

        chartEvents.beforeZoom = (_ctx, payload) => {
            const minRaw = payload?.xaxis?.min;
            const maxRaw = payload?.xaxis?.max;
            const min = Number.isFinite(minRaw) ? Math.max(oldest, minRaw) : oldest;
            const max = Number.isFinite(maxRaw) ? Math.min(newest, maxRaw) : newest;
            if (max <= min) {
                return { xaxis: { min: oldest, max: newest } };
            }
            return { xaxis: { min, max } };
        };
        chartEvents.beforeResetZoom = () => ({
            xaxis: { min: zoomStart, max: newest },
        });
        chartEvents.mounted = (chartCtx) => {
            if (zoomStart > oldest && newest > oldest) {
                chartCtx.zoomX(zoomStart, newest);
            }
        };
    }

    return {
        chart: {
            type: "line",
            height: 320,
            events: chartEvents,
            toolbar: {
                show: true,
                tools: {
                    download: true,
                    selection: true,
                    zoom: true,
                    zoomin: true,
                    zoomout: true,
                    pan: true,
                    reset: true,
                },
            },
            zoom: {
                enabled: true,
                autoScaleYaxis: true,
            },
            animations: {
                enabled: true,
                easing: "easeinout",
                speed: 450,
            },
            fontFamily: "Manrope, sans-serif",
        },
        series: [
            { name: "Antes", data: seriesAntes },
            { name: "Depois", data: seriesDepois },
        ],
        colors: [config.colorAntes, config.colorDepois],
        stroke: {
            curve: "smooth",
            width: 2.6,
        },
        markers: {
            size: 3.2,
            strokeWidth: 0.8,
            hover: {
                size: 5,
            },
        },
        dataLabels: {
            enabled: false,
        },
        legend: {
            show: true,
            position: "top",
            horizontalAlign: "left",
            fontWeight: 700,
        },
        grid: {
            borderColor: "#e4ece9",
            strokeDashArray: 3,
        },
        xaxis: xAxis,
        yaxis: {
            title: {
                text: config.yLabel,
                style: {
                    color: "#476157",
                    fontWeight: 700,
                },
            },
            labels: {
                formatter: (value) => Number(value).toFixed(config.decimals),
                style: {
                    colors: "#60756d",
                    fontSize: "11px",
                },
            },
        },
        tooltip: {
            shared: false,
            x: {
                show: true,
                format: isDatetime ? "dd/MM/yyyy HH:mm:ss" : undefined,
            },
            y: {
                formatter: (value) => `${Number(value).toFixed(config.decimals)} ${config.yLabel}`,
            },
        },
        noData: {
            text: "Sem dados",
        },
    };
}

function destroyChartIfExists(chartId) {
    const chart = chartInstances.get(chartId);
    if (chart) {
        chart.destroy();
        chartInstances.delete(chartId);
    }
}

function renderChart(config) {
    const chartElement = document.getElementById(config.chartId);
    const emptyElement = document.getElementById(config.emptyId);
    if (!chartElement || !emptyElement) {
        return;
    }

    const { antes, depois } = prepareSeries(config);
    updateLastReadingText(config, antes, depois);

    if (!antes.length && !depois.length) {
        destroyChartIfExists(config.chartId);
        chartElement.hidden = true;
        emptyElement.hidden = false;
        return;
    }

    if (typeof window.ApexCharts !== "function") {
        destroyChartIfExists(config.chartId);
        chartElement.hidden = true;
        emptyElement.hidden = false;
        emptyElement.textContent = "ApexCharts nao carregado.";
        return;
    }

    chartElement.hidden = false;
    emptyElement.hidden = true;
    emptyElement.textContent = "Sem leituras";

    destroyChartIfExists(config.chartId);
    chartElement.innerHTML = "";

    const options = createApexOptions(config, antes, depois);
    const chart = new window.ApexCharts(chartElement, options);
    chart.render();
    chartInstances.set(config.chartId, chart);
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
    resizeTimer = setTimeout(renderAllCharts, 140);
}

function initPage() {
    renderAllCharts();
    initTopToggle();
    initCalibrationToggle();
}

document.addEventListener("DOMContentLoaded", initPage);
window.addEventListener("resize", handleResize);
