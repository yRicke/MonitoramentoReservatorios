(function () {
    const panel = document.getElementById("calibrationLivePanel");
    if (!panel) {
        return;
    }

    const statusUrl = panel.dataset.statusUrl;
    const sensor = panel.dataset.sensor || "";
    if (!statusUrl || !sensor) {
        return;
    }

    const refs = {
        status: panel.querySelector("[data-live-status]"),
        count: panel.querySelector("[data-live-count]"),
        lastValue: panel.querySelector("[data-live-last-value]"),
        lastMeta: panel.querySelector("[data-live-last-meta]"),
        avgValue: panel.querySelector("[data-live-avg-value]"),
        avgMeta: panel.querySelector("[data-live-avg-meta]"),
        sensorStability: panel.querySelector("[data-live-stability-sensor]"),
        sensorStabilityMeta: panel.querySelector("[data-live-stability-sensor-meta]"),
        tempCard: panel.querySelector("[data-live-temp-card]"),
        tempStability: panel.querySelector("[data-live-stability-temp]"),
        tempStabilityMeta: panel.querySelector("[data-live-stability-temp-meta]"),
        confirmButtons: Array.from(document.querySelectorAll("[data-confirm-button]")),
        confirmHints: Array.from(document.querySelectorAll("[data-confirm-hint]")),
        captureButton: document.querySelector("[data-capture-point1-button]"),
        captureHint: document.querySelector("[data-capture-point1-hint]"),
    };

    function formatNumber(value, digits) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) {
            return "--";
        }
        return Number(value).toFixed(digits);
    }

    function renderStability(target, metaTarget, payload, unit) {
        if (!payload || !payload.disponivel) {
            target.textContent = "--";
            metaTarget.textContent = "Sem dados suficientes";
            return;
        }

        target.textContent = payload.estavel ? "Estável" : "Instável";
        const desvio = payload.desvio_exibicao !== null && payload.desvio_exibicao !== undefined
            ? payload.desvio_exibicao
            : payload.desvio;
        const unidadeFinal = payload.unidade || unit || "";
        metaTarget.textContent = "Desvio " + formatNumber(desvio, 2) + (unidadeFinal ? " " + unidadeFinal : "");
    }

    function shouldRequireTemperatureStability() {
        return sensor === "tds";
    }

    function updateButtons(data) {
        const sensorStable = !!(data.estabilidade_sensor && data.estabilidade_sensor.estavel);
        const tempStable = !shouldRequireTemperatureStability()
            || !!(data.estabilidade_temperatura && data.estabilidade_temperatura.estavel);
        const ready = data.ativa && sensorStable && tempStable;

        if (refs.captureButton && refs.captureHint) {
            refs.captureButton.disabled = !ready;
            refs.captureHint.textContent = ready
                ? "Sessão pronta para capturar o ponto 1."
                : "Aguardando estabilidade do sensor e da temperatura.";
        }

        refs.confirmButtons.forEach((button) => {
            if (button === refs.captureButton) {
                return;
            }
            button.disabled = !ready;
        });

        refs.confirmHints.forEach((hint) => {
            hint.textContent = ready
                ? "Sessão pronta para confirmar a calibração."
                : (shouldRequireTemperatureStability()
                    ? "Aguardando estabilidade do sensor e da temperatura."
                    : "Aguardando estabilidade do sensor.");
        });
    }

    function render(data) {
        refs.status.textContent = data.ativa ? "Ativa" : "Inativa";
        refs.count.textContent = data.ativa
            ? data.amostras + " amostras recebidas"
            : "Aguardando início da sessão";

        const ultima = data.ultima_amostra || null;
        if (sensor === "temperatura") {
            refs.lastValue.textContent = ultima && ultima.temperatura_calibrada !== null && ultima.temperatura_calibrada !== undefined
                ? formatNumber(ultima.temperatura_calibrada, 2) + " C"
                : "--";
            refs.lastMeta.textContent = ultima
                ? "Temperatura bruta " + formatNumber(ultima.temperatura_bruta, 2) + " C"
                : "Sem amostras recentes";
            refs.avgValue.textContent = data.medias && data.medias.temperatura_calibrada !== undefined
                ? formatNumber(data.medias.temperatura_calibrada, 2) + " C"
                : "--";
            refs.avgMeta.textContent = data.medias
                ? "Média da temperatura bruta " + formatNumber(data.medias.temperatura_bruta, 2) + " C"
                : "Sem dados suficientes";
        } else {
            const digits = sensor === "turbidez" ? 3 : 2;
            const unit = sensor === "turbidez" ? " NTU" : (sensor === "tds" ? " ppm" : (sensor === "ph" ? " pH" : ""));

            if (sensor === "ph") {
                refs.lastValue.textContent = ultima && ultima.tensao !== null && ultima.tensao !== undefined
                    ? formatNumber(ultima.tensao, 3) + " V"
                    : "--";
                refs.lastMeta.textContent = ultima
                    ? "ADC " + (ultima.adc ?? "--")
                        + (ultima.valor_calibrado !== null && ultima.valor_calibrado !== undefined
                            ? " | pH traduzido " + formatNumber(ultima.valor_calibrado, 2)
                            : "")
                    : "Sem amostras recentes";
                refs.avgValue.textContent = data.medias && data.medias.tensao !== undefined
                    ? formatNumber(data.medias.tensao, 3) + " V"
                    : "--";
                refs.avgMeta.textContent = data.medias
                    ? "ADC médio " + formatNumber(data.medias.adc, 0)
                        + (data.medias.valor_calibrado !== null && data.medias.valor_calibrado !== undefined
                            ? " | pH médio " + formatNumber(data.medias.valor_calibrado, 2)
                            : "")
                    : "Sem dados suficientes";
            } else {
                refs.lastValue.textContent = ultima && ultima.valor_calibrado !== null && ultima.valor_calibrado !== undefined
                    ? formatNumber(ultima.valor_calibrado, digits) + unit
                    : "--";

                if (sensor === "tds") {
                    refs.lastMeta.textContent = ultima
                        ? "ADC " + (ultima.adc ?? "--")
                            + (ultima.tensao !== null && ultima.tensao !== undefined ? " | Tensão " + formatNumber(ultima.tensao, 3) + " V" : "")
                            + (ultima.temperatura_calibrada !== null && ultima.temperatura_calibrada !== undefined ? " | Temp " + formatNumber(ultima.temperatura_calibrada, 2) + " C" : "")
                        : "Sem amostras recentes";
                } else {
                    refs.lastMeta.textContent = ultima
                        ? "ADC " + (ultima.adc ?? "--") + (ultima.tensao !== null && ultima.tensao !== undefined ? " | Tensão " + formatNumber(ultima.tensao, 3) + " V" : "")
                        : "Sem amostras recentes";
                }

                refs.avgValue.textContent = data.medias && data.medias.valor_calibrado !== undefined
                    ? formatNumber(data.medias.valor_calibrado, digits) + unit
                    : "--";

                if (sensor === "tds") {
                    refs.avgMeta.textContent = data.medias
                        ? "Média nas últimas amostras | Temp " + formatNumber(data.medias.temperatura_calibrada, 2) + " C"
                        : "Sem dados suficientes";
                } else {
                    refs.avgMeta.textContent = data.medias
                        ? "Média do valor convertido nas últimas amostras"
                        : "Sem dados suficientes";
                }
            }
        }

        renderStability(refs.sensorStability, refs.sensorStabilityMeta, data.estabilidade_sensor, sensor === "temperatura" ? "C" : "");
        if (refs.tempCard) {
            if (
                sensor === "temperatura" ||
                sensor === "turbidez" ||
                sensor === "ph" ||
                !data.estabilidade_temperatura ||
                !data.estabilidade_temperatura.limite
            ) {
                refs.tempCard.classList.add("is-hidden");
            } else {
                refs.tempCard.classList.remove("is-hidden");
                renderStability(refs.tempStability, refs.tempStabilityMeta, data.estabilidade_temperatura, "C");
            }
        }

        updateButtons(data);
    }

    async function loadStatus() {
        try {
            const response = await fetch(statusUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!response.ok) {
                return;
            }

            const data = await response.json();
            render(data);
        } catch (error) {
            // Mantém o último estado visível se o polling falhar.
        }
    }

    loadStatus();
    window.setInterval(loadStatus, 5000);
})();
