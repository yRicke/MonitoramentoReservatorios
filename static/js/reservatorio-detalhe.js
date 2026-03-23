function loadJsonScript(id) {
    const element = document.getElementById(id);
    if (!element) {
        return [];
    }
    return JSON.parse(element.textContent);
}

function normalizeSeriesPoints(seriesRaw) {
    if (!Array.isArray(seriesRaw)) {
        return [];
    }

    const points = [];
    for (const point of seriesRaw) {
        if (!point || typeof point !== "object") {
            continue;
        }

        const x = String(point.x || "-");
        const yNumber = Number(point.y);
        if (!Number.isFinite(yNumber)) {
            continue;
        }

        points.push({ x: x, y: Number(yNumber.toFixed(2)) });
    }
    return points;
}

function renderApexChart(config) {
    const chartElement = document.getElementById(config.chartId);
    const empty = document.getElementById(config.emptyId);
    if (!chartElement || !empty) {
        return;
    }

    const seriesAntes = normalizeSeriesPoints(loadJsonScript(config.seriesAntesId));
    const seriesDepois = normalizeSeriesPoints(loadJsonScript(config.seriesDepoisId));

    if (!seriesAntes.length && !seriesDepois.length) {
        chartElement.hidden = true;
        empty.hidden = false;
        return;
    }

    chartElement.hidden = false;
    empty.hidden = true;

    if (chartElement._apexChartInstance) {
        chartElement._apexChartInstance.destroy();
        chartElement._apexChartInstance = null;
    }

    const options = {
        chart: {
            type: "line",
            height: 260,
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
            },
            animations: {
                enabled: true,
                speed: 350,
            },
        },
        series: [
            {
                name: "Antes do tratamento",
                data: seriesAntes,
            },
            {
                name: "Depois do tratamento",
                data: seriesDepois,
            },
        ],
        stroke: {
            curve: "smooth",
            width: 3,
        },
        colors: [config.colorAntes, config.colorDepois],
        markers: {
            size: 3,
            hover: {
                size: 5,
            },
        },
        grid: {
            borderColor: "#e5e7eb",
        },
        xaxis: {
            type: "category",
            labels: {
                rotate: -20,
                style: {
                    fontSize: "11px",
                },
            },
            title: {
                text: "Data/Hora",
            },
        },
        yaxis: {
            title: {
                text: config.yLabel,
            },
            labels: {
                formatter: function (value) {
                    return Number(value).toFixed(2);
                },
            },
        },
        tooltip: {
            shared: false,
            intersect: true,
            x: {
                show: true,
            },
            y: {
                formatter: function (value) {
                    return Number(value).toFixed(2) + " " + config.ySuffix;
                },
            },
        },
        noData: {
            text: "Sem dados",
        },
    };

    const chart = new ApexCharts(chartElement, options);
    chart.render();
    chartElement._apexChartInstance = chart;
}

function renderAllCharts() {
    const chartsConfig = [
        {
            chartId: "chartTDS",
            emptyId: "emptyTDS",
            seriesAntesId: "tds-series-antes-data",
            seriesDepoisId: "tds-series-depois-data",
            yLabel: "ppm",
            ySuffix: "ppm",
            colorAntes: "#7f4df5",
            colorDepois: "#00be6f",
        },
        {
            chartId: "chartTemperatura",
            emptyId: "emptyTemperatura",
            seriesAntesId: "temperatura-series-antes-data",
            seriesDepoisId: "temperatura-series-depois-data",
            yLabel: "celsius",
            ySuffix: "celsius",
            colorAntes: "#ff7a00",
            colorDepois: "#16a34a",
        },
        {
            chartId: "chartTurbidez",
            emptyId: "emptyTurbidez",
            seriesAntesId: "turbidez-series-antes-data",
            seriesDepoisId: "turbidez-series-depois-data",
            yLabel: "ntu",
            ySuffix: "ntu",
            colorAntes: "#3b82f6",
            colorDepois: "#9333ea",
        },
    ];

    if (typeof ApexCharts === "undefined") {
        chartsConfig.forEach((config) => {
            const chartElement = document.getElementById(config.chartId);
            const empty = document.getElementById(config.emptyId);
            if (chartElement) {
                chartElement.hidden = true;
            }
            if (empty) {
                empty.hidden = false;
            }
        });
        return;
    }

    chartsConfig.forEach(renderApexChart);
}

document.addEventListener("DOMContentLoaded", renderAllCharts);
