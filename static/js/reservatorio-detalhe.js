const MAX_POINTS_RENDER = 420;
const INITIAL_ZOOM_POINTS = 20;

const CHARTS_CONFIG = [
    {
        chartId: "chartTemperatura",
        emptyId: "emptyTemperatura",
        seriesId: "temperatura-series-data",
        lastReadingId: "lastReadingTemperatura",
        yLabel: "celsius",
        color: "#ff7a00",
        decimals: 2,
    },
    {
        chartId: "chartTDS",
        emptyId: "emptyTDS",
        seriesId: "tds-series-data",
        lastReadingId: "lastReadingTDS",
        yLabel: "ppm",
        color: "#7f4df5",
        decimals: 2,
    },
    {
        chartId: "chartTurbidez",
        emptyId: "emptyTurbidez",
        seriesId: "turbidez-series-data",
        lastReadingId: "lastReadingTurbidez",
        yLabel: "ntu",
        color: "#3b82f6",
        decimals: 3,
        highlightNight: true,
        nightMarkerColor: "#173a63",
    },
    {
        chartId: "chartPH",
        emptyId: "emptyPH",
        seriesId: "ph-series-data",
        lastReadingId: "lastReadingPH",
        yLabel: "pH",
        color: "#0ea5e9",
        decimals: 2,
    },
];

const chartInstances = new Map();
const STATUS_CLASS_POOL = [
    "status-bom",
    "status-atencao",
    "status-perigo",
    "status-sem-dado",
    "status-ignorado-noturno",
];
let resizeTimer = null;

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

function setJsonScriptData(id, value) {
    const element = document.getElementById(id);
    if (!element) {
        return;
    }
    element.textContent = JSON.stringify(value ?? []);
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

        points.push({
            x: xValue,
            y: Number(y.toFixed(4)),
            label,
            night: item.night === true,
        });
    }

    return points;
}

function mergeAdjacentEqualLabels(series) {
    if (!series.length) {
        return [];
    }

    const merged = [];
    let currentLabel = series[0].x;
    let currentDateLabel = series[0].label || null;
    let currentNight = series[0].night === true;
    let sum = series[0].y;
    let count = 1;

    for (let i = 1; i < series.length; i += 1) {
        const point = series[i];
        if (point.x === currentLabel) {
            sum += point.y;
            count += 1;
            currentDateLabel = point.label || currentDateLabel;
            currentNight = currentNight || point.night === true;
            continue;
        }

        merged.push({
            x: currentLabel,
            y: Number((sum / count).toFixed(4)),
            label: currentDateLabel,
            night: currentNight,
        });

        currentLabel = point.x;
        currentDateLabel = point.label || null;
        currentNight = point.night === true;
        sum = point.y;
        count = 1;
    }

    merged.push({
        x: currentLabel,
        y: Number((sum / count).toFixed(4)),
        label: currentDateLabel,
        night: currentNight,
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
        const idx = Math.min(lastIndex - 1, Math.max(1, Math.round(i * step)));
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
    return optimizeSeries(normalizePoints(getJsonScriptData(config.seriesId)));
}

function updateLastReadingText(config, series) {
    const target = document.getElementById(config.lastReadingId);
    if (!target) {
        return;
    }

    if (!series.length) {
        target.textContent = "Última leitura: --";
        return;
    }

    const point = series[series.length - 1];
    target.textContent = `Última leitura: ${point.y.toFixed(config.decimals)} ${config.yLabel} em ${formatPointDateLabel(point)}`;
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

function getXAxisConfig(series) {
    const isDatetime = series.length > 0 && series.every((point) => typeof point.x === "number");

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

    const sortedX = series
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

function createApexOptions(config, series) {
    const xAxisMeta = getXAxisConfig(series);
    const xAxis = xAxisMeta.config;
    const chartEvents = {};

    if (xAxisMeta.isDatetime) {
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
            { name: "Valor", data: series },
        ],
        colors: [config.color],
        stroke: {
            curve: "smooth",
            width: 2.6,
        },
        markers: {
            size: 3.2,
            strokeWidth: 0.8,
            discrete: buildDiscreteMarkers(config, series),
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
                formatter: (value, opts) => {
                    const point = opts?.w?.config?.series?.[opts.seriesIndex]?.data?.[opts.dataPointIndex];
                    if (point) {
                        return formatPointDateLabel(point);
                    }
                    if (typeof value === "number" && Number.isFinite(value)) {
                        return formatDateLabel(value);
                    }
                    return String(value ?? "-");
                },
            },
            y: {
                formatter: (value, opts) => {
                    const point = opts?.w?.config?.series?.[opts.seriesIndex]?.data?.[opts.dataPointIndex];
                    const suffix = config.highlightNight && point?.night ? " | Leitura noturna" : "";
                    return `${Number(value).toFixed(config.decimals)} ${config.yLabel}${suffix}`;
                },
            },
        },
        noData: {
            text: "Sem dados",
        },
    };
}

function buildDiscreteMarkers(config, series) {
    if (!config.highlightNight) {
        return [];
    }

    return series
        .map((point, dataPointIndex) => {
            if (!point.night) {
                return null;
            }

            return {
                seriesIndex: 0,
                dataPointIndex,
                size: 4.8,
                fillColor: config.nightMarkerColor,
                strokeColor: "#ffffff",
                shape: "circle",
            };
        })
        .filter(Boolean);
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
        return Promise.resolve();
    }

    const series = prepareSeries(config);
    updateLastReadingText(config, series);

    if (!series.length) {
        destroyChartIfExists(config.chartId);
        chartElement.hidden = true;
        emptyElement.hidden = false;
        return Promise.resolve();
    }

    if (typeof window.ApexCharts !== "function") {
        destroyChartIfExists(config.chartId);
        chartElement.hidden = true;
        emptyElement.hidden = false;
        emptyElement.textContent = "ApexCharts não carregado.";
        return Promise.resolve();
    }

    chartElement.hidden = false;
    emptyElement.hidden = true;
    emptyElement.textContent = "Sem leituras";

    destroyChartIfExists(config.chartId);
    chartElement.innerHTML = "";

    const options = createApexOptions(config, series);
    const chart = new window.ApexCharts(chartElement, options);
    chartInstances.set(config.chartId, chart);
    return Promise.resolve(chart.render()).catch((error) => {
        console.error(`Falha ao renderizar ${config.chartId}`, error);
    });
}

function renderAllCharts() {
    return Promise.all(CHARTS_CONFIG.map((config) => renderChart(config))).then(() => {
        document.dispatchEvent(new CustomEvent("reservatorio:charts-rendered"));
    });
}

function formatPointDateLabel(point) {
    if (!point) {
        return "-";
    }
    if (typeof point.label === "string" && point.label.trim()) {
        return point.label.trim();
    }
    if (typeof point.x === "number" && Number.isFinite(point.x)) {
        return formatDateLabel(point.x);
    }
    return String(point.x ?? "-");
}

function replaceStatusClasses(element, nextClassName) {
    if (!element) {
        return;
    }

    STATUS_CLASS_POOL.forEach((className) => element.classList.remove(className));
    if (nextClassName) {
        element.classList.add(nextClassName);
    }
}

function renderLiveMetricCard(metric) {
    if (!metric || !metric.id) {
        return;
    }

    const card = document.querySelector(`[data-metric-card="${metric.id}"]`);
    if (!card) {
        return;
    }

    const valueEl = card.querySelector("[data-metric-value]");
    const statusEl = card.querySelector("[data-metric-status]");
    const timeEl = card.querySelector("[data-metric-time]");
    const decimals = Number(card.dataset.metricDecimals || 0);
    const unit = card.dataset.metricUnit || "";
    const point = metric.ponto_unico || {};

    if (valueEl) {
        if (point.valor === null || point.valor === undefined || Number.isNaN(Number(point.valor))) {
            valueEl.textContent = "--";
        } else {
            valueEl.textContent = `${Number(point.valor).toFixed(decimals)}${unit ? ` ${unit}` : ""}`;
        }
    }

    if (statusEl) {
        statusEl.textContent = point.status_label || "Sem dado";
        replaceStatusClasses(statusEl, point.status ? `status-${point.status}` : "status-sem-dado");
    }

    if (timeEl) {
        if (point.data_hora) {
            timeEl.hidden = false;
            timeEl.textContent = point.data_hora;
        } else {
            timeEl.hidden = true;
            timeEl.textContent = "";
        }
    }
}

function renderLiveReservatorioPayload(payload) {
    if (!payload || typeof payload !== "object") {
        return;
    }

    const reservatorioStatusEl = document.querySelector("[data-reservatorio-status]");
    if (reservatorioStatusEl && payload.reservatorio) {
        reservatorioStatusEl.textContent = payload.reservatorio.status_label || "Sem dado";
        replaceStatusClasses(
            reservatorioStatusEl,
            payload.reservatorio.status ? `status-${payload.reservatorio.status}` : "status-sem-dado",
        );
    }

    const alertaStatusEl = document.querySelector("[data-alerta-status]");
    if (alertaStatusEl && payload.alerta_sonoro) {
        alertaStatusEl.textContent = payload.alerta_sonoro.rotulo || "Desligado";
        replaceStatusClasses(alertaStatusEl, payload.alerta_sonoro.classe_status || "status-sem-dado");
    }

    if (Array.isArray(payload.metricas_recentes)) {
        payload.metricas_recentes.forEach(renderLiveMetricCard);
    }

    if (payload.series && typeof payload.series === "object") {
        setJsonScriptData("tds-series-data", payload.series.tds);
        setJsonScriptData("temperatura-series-data", payload.series.temperatura);
        setJsonScriptData("turbidez-series-data", payload.series.turbidez);
        setJsonScriptData("ph-series-data", payload.series.ph);
        renderAllCharts();
    }
}

function initDetailLiveUpdates() {
    const panel = document.getElementById("reservatorioLivePanel");
    if (!panel) {
        return;
    }

    const statusUrl = panel.dataset.statusUrl;
    if (!statusUrl) {
        return;
    }

    let statusCursor = panel.dataset.statusCursor || "";
    let pollIntervalMs = Number(panel.dataset.pollIntervalMs || 60000);
    let pollTimer = null;

    function stopPolling() {
        if (pollTimer !== null) {
            window.clearTimeout(pollTimer);
            pollTimer = null;
        }
    }

    function scheduleNextPoll(immediate = false) {
        stopPolling();
        pollTimer = window.setTimeout(loadStatus, immediate ? 0 : Math.max(500, pollIntervalMs));
    }

    async function loadStatus() {
        stopPolling();
        try {
            const requestUrl = new URL(statusUrl, window.location.origin);
            if (statusCursor) {
                requestUrl.searchParams.set("cursor", statusCursor);
                requestUrl.searchParams.set("wait_ms", String(pollIntervalMs));
            }

            const response = await fetch(requestUrl.toString(), {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!response.ok) {
                scheduleNextPoll(false);
                return;
            }

            const payload = await response.json();
            if (payload.cursor) {
                statusCursor = payload.cursor;
                panel.dataset.statusCursor = statusCursor;
            }
            if (
                payload.poll_interval_ms !== null
                && payload.poll_interval_ms !== undefined
                && !Number.isNaN(Number(payload.poll_interval_ms))
            ) {
                pollIntervalMs = Number(payload.poll_interval_ms);
                panel.dataset.pollIntervalMs = String(pollIntervalMs);
            }

            renderLiveReservatorioPayload(payload);
            scheduleNextPoll(true);
        } catch (error) {
            scheduleNextPoll(false);
        }
    }

    loadStatus();
    window.addEventListener("beforeunload", stopPolling);
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

        const openLabel = button.dataset.labelOpen || "Fechar";
        const closedLabel = button.dataset.labelClosed || "Abrir";
        const startsOpen = button.dataset.startsOpen === "true";

        const updateState = (isOpen) => {
            panel.hidden = !isOpen;
            button.classList.toggle("is-open", isOpen);
            button.setAttribute("aria-expanded", isOpen ? "true" : "false");
            button.textContent = isOpen ? openLabel : closedLabel;
        };

        updateState(startsOpen);
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

function handleResize() {
    if (resizeTimer) {
        clearTimeout(resizeTimer);
    }
    resizeTimer = setTimeout(renderAllCharts, 140);
}

function initPage() {
    renderAllCharts();
    initDetailLiveUpdates();
    initTopToggle();
    initCalibrationToggle();
}

document.addEventListener("DOMContentLoaded", initPage);
window.addEventListener("resize", handleResize);
