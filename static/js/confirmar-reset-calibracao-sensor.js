function confirmarResetCalibracaoSensor(event) {
    const form = event.currentTarget;
    const sensorNome = form.dataset.sensorNome || "sensor";
    const pontoNome = form.dataset.pontoNome || "ponto";
    const mensagem = `Tem certeza que deseja resetar os dados de calibracao de ${sensorNome} em ${pontoNome}?`;
    const confirmou = window.confirm(mensagem);

    if (!confirmou) {
        event.preventDefault();
    }
}

function configurarConfirmacaoResetCalibracaoSensor() {
    if (typeof window.confirm !== "function") {
        return;
    }

    const forms = document.querySelectorAll("form[data-confirm-reset-calibracao-sensor]");
    forms.forEach((form) => {
        form.addEventListener("submit", confirmarResetCalibracaoSensor);
    });
}

document.addEventListener("DOMContentLoaded", configurarConfirmacaoResetCalibracaoSensor);
