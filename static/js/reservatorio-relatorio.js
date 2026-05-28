function initReportPrintButton() {
    const printButton = document.querySelector("[data-print-report]");
    if (!printButton) {
        return;
    }

    printButton.addEventListener("click", () => {
        window.print();
    });
}

function initAutoPrintReport() {
    const reportRoot = document.querySelector("[data-auto-print-report]");
    if (!reportRoot || reportRoot.dataset.autoPrintReport !== "true") {
        return;
    }

    let alreadyPrinted = false;
    const triggerPrint = () => {
        if (alreadyPrinted) {
            return;
        }
        alreadyPrinted = true;
        window.setTimeout(() => {
            window.print();
        }, 180);
    };

    document.addEventListener("reservatorio:charts-rendered", triggerPrint, { once: true });
}

document.addEventListener("DOMContentLoaded", () => {
    initReportPrintButton();
    initAutoPrintReport();
});
