function confirmarExclusaoReservatorio(event) {
    const form = event.currentTarget;
    const nomeReservatorio = form.dataset.reservatorioNome || "este reservatorio";
    const mensagem = `Para excluir, digite exatamente o nome do reservatorio: ${nomeReservatorio}`;
    const entradaUsuario = window.prompt(mensagem, "");

    if (entradaUsuario === null) {
        event.preventDefault();
        return;
    }

    if (entradaUsuario.trim() !== nomeReservatorio) {
        window.alert("Nome diferente. Exclusao cancelada.");
        event.preventDefault();
    }
}

function configurarConfirmacaoExclusaoReservatorio() {
    if (typeof window.prompt !== "function") {
        return;
    }

    const forms = document.querySelectorAll("form[data-confirm-delete-reservatorio]");
    forms.forEach((form) => {
        form.addEventListener("submit", confirmarExclusaoReservatorio);
    });
}

document.addEventListener("DOMContentLoaded", configurarConfirmacaoExclusaoReservatorio);
