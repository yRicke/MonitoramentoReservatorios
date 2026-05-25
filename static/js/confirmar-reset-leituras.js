function confirmarResetLeituras(event) {
    const form = event.currentTarget;
    const nomeReservatorio = form.dataset.reservatorioNome || "este reservatorio";
    const mensagem = `Tem certeza que deseja resetar todas as leituras de ${nomeReservatorio}?`;
    const confirmou = window.confirm(mensagem);

    if (!confirmou) {
        event.preventDefault();
    }
}

function configurarConfirmacaoResetLeituras() {
    if (typeof window.confirm !== "function") {
        return;
    }

    const forms = document.querySelectorAll("form[data-confirm-reset-leituras]");
    forms.forEach((form) => {
        form.addEventListener("submit", confirmarResetLeituras);
    });
}

document.addEventListener("DOMContentLoaded", configurarConfirmacaoResetLeituras);
