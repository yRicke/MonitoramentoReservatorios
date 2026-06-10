(function () {
    const button = document.querySelector("[data-alerta-teste-button]");
    if (!button) {
        return;
    }

    const defaultLabel = button.dataset.alertaTesteDefaultLabel || "Testar alerta sonoro";
    const busyLabel = button.dataset.alertaTesteBusyLabel || "Testando alerta sonoro...";
    let resetTimer = null;

    function applyIdleState() {
        button.disabled = false;
        button.classList.remove("is-busy");
        button.textContent = defaultLabel;
        delete button.dataset.alertaTesteRestanteMs;
    }

    function applyBusyState(durationMs) {
        button.disabled = true;
        button.classList.add("is-busy");
        button.textContent = busyLabel;

        if (resetTimer !== null) {
            window.clearTimeout(resetTimer);
        }

        const safeDurationMs = Math.max(0, Number(durationMs) || 0);
        resetTimer = window.setTimeout(applyIdleState, safeDurationMs);
    }

    button.form?.addEventListener("submit", function () {
        applyBusyState(5000);
    });

    const restanteMs = Number(button.dataset.alertaTesteRestanteMs || 0);
    if (restanteMs > 0) {
        applyBusyState(restanteMs);
    }
})();
