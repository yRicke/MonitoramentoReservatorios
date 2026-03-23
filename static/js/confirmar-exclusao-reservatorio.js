function confirmarExclusaoReservatorio(event) {
    const form = event.currentTarget;
    const nomeReservatorio = form.dataset.reservatorioNome || "este reservatorio";
    const mensagem = `Deseja excluir "${nomeReservatorio}"?`;

    if (!window.confirm(mensagem)) {
        event.preventDefault();
    }
}

function configurarConfirmacaoExclusaoReservatorio() {
    if (typeof window.confirm !== "function") {
        return;
    }

    const forms = document.querySelectorAll("form[data-confirm-delete-reservatorio]");
    forms.forEach((form) => {
        form.addEventListener("submit", confirmarExclusaoReservatorio);
    });
}

document.addEventListener("DOMContentLoaded", configurarConfirmacaoExclusaoReservatorio);
