/**
 * Busca dinâmica genérica para tabelas do Geld.
 * Uso: initBusca('id-da-tabela', 'id-do-input')
 */
function initBusca(tabelaId, inputId) {
    const input = document.getElementById(inputId);
    const tbody = document.querySelector('#' + tabelaId + ' tbody');
    if (!input || !tbody) return;

    input.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        Array.from(tbody.querySelectorAll('tr')).forEach(row => {
            const texto = row.textContent.toLowerCase();
            row.style.display = texto.includes(query) ? '' : 'none';
        });
    });
}
