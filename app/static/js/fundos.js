function toggleSelectAll(checkbox) {
    document.querySelectorAll('.fundo-checkbox').forEach(function(cb) {
        const row = cb.closest('tr');
        if (row.style.display !== 'none') cb.checked = checkbox.checked;
    });
    updateCounter();
}

function updateCounter() {
    const checked = document.querySelectorAll('.fundo-checkbox:checked');
    const counter = document.getElementById('contador-selecionados');
    const count = checked.length;
    counter.textContent = count + ' selecionado' + (count !== 1 ? 's' : '');

    const selectAll = document.getElementById('select-all');
    const allCbs = document.querySelectorAll('.fundo-checkbox');
    const visible = Array.from(allCbs).filter(cb => cb.closest('tr').style.display !== 'none');
    if (selectAll && visible.length > 0) {
        const checkedVisible = visible.filter(cb => cb.checked).length;
        selectAll.checked = checkedVisible === visible.length && checkedVisible > 0;
    }
}

function aplicarFiltros() {
    const filtroClasse = document.getElementById('filtro-classe').value.toLowerCase();
    const filtroRisco  = document.getElementById('filtro-risco').value.toLowerCase();
    const filtroStatus = document.getElementById('filtro-status').value.toLowerCase();

    sessionStorage.setItem('geld_filtro_classe', filtroClasse);
    sessionStorage.setItem('geld_filtro_risco',  filtroRisco);
    sessionStorage.setItem('geld_filtro_status', filtroStatus);

    document.querySelectorAll('#tabela-fundos tbody tr').forEach(function(row) {
        const classe = row.getAttribute('data-classe').toLowerCase();
        const risco  = row.getAttribute('data-risco').toLowerCase();
        const status = row.getAttribute('data-status').toLowerCase();

        const ok = (!filtroClasse || classe.includes(filtroClasse))
                && (!filtroRisco  || risco === filtroRisco)
                && (!filtroStatus || status === filtroStatus);

        row.style.display = ok ? '' : 'none';
        if (!ok) {
            const cb = row.querySelector('.fundo-checkbox');
            if (cb) cb.checked = false;
        }
    });

    updateCounter();
}

function limparFiltros() {
    document.getElementById('filtro-classe').value = '';
    document.getElementById('filtro-risco').value  = '';
    document.getElementById('filtro-status').value = '';
    sessionStorage.removeItem('geld_filtro_classe');
    sessionStorage.removeItem('geld_filtro_risco');
    sessionStorage.removeItem('geld_filtro_status');
    aplicarFiltros();
}

function popularFiltroClasse() {
    const filtroClasse = document.getElementById('filtro-classe');
    const classes = new Set();
    document.querySelectorAll('#tabela-fundos tbody tr').forEach(function(row) {
        const classe = row.getAttribute('data-classe');
        if (classe) classes.add(classe.split(' ').slice(0, 2).join(' '));
    });
    Array.from(classes).sort().forEach(function(classe) {
        const opt = document.createElement('option');
        opt.value = classe;
        opt.textContent = classe;
        filtroClasse.appendChild(opt);
    });
}

function deletarSelecionados() {
    const checkboxes = document.querySelectorAll('.fundo-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('Selecione pelo menos um fundo para deletar.');
        return;
    }
    const count = checkboxes.length;
    if (!confirm('Tem certeza que deseja deletar ' + count + ' fundo' + (count !== 1 ? 's' : '') + '?')) return;

    const form = document.createElement('form');
    form.method = 'POST';
    form.action = document.getElementById('url-delete-multiple').value;
    Array.from(checkboxes).forEach(function(cb) {
        const input = document.createElement('input');
        input.type  = 'hidden';
        input.name  = 'fundo_ids';
        input.value = cb.value;
        form.appendChild(input);
    });
    document.body.appendChild(form);
    form.submit();
}

document.addEventListener('DOMContentLoaded', function() {
    // Ordenar tabela por nome do fundo (alfabético)
    const tbody = document.querySelector('#tabela-fundos tbody');
    if (tbody) {
        const rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort(function(a, b) {
            const nA = (a.querySelector('td:nth-child(2)')?.textContent || '').trim().toLowerCase();
            const nB = (b.querySelector('td:nth-child(2)')?.textContent || '').trim().toLowerCase();
            return nA.localeCompare(nB, 'pt-BR');
        });
        rows.forEach(row => tbody.appendChild(row));
    }

    popularFiltroClasse();
    initBusca('tabela-fundos', 'busca-fundos');

    // Restaurar filtros da sessão
    const classe = sessionStorage.getItem('geld_filtro_classe') || '';
    const risco  = sessionStorage.getItem('geld_filtro_risco')  || '';
    const status = sessionStorage.getItem('geld_filtro_status') || '';
    if (classe || risco || status) {
        document.getElementById('filtro-classe').value = classe;
        document.getElementById('filtro-risco').value  = risco;
        document.getElementById('filtro-status').value = status;
        aplicarFiltros();
    }

    // Toggle previdência sem recarregar página
    document.querySelectorAll('.form-toggle-prev').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            ajaxPost(form.action, null, function() {
                const btn = form.querySelector('button');
                btn.classList.toggle('prev-ativo');
                btn.style.color = btn.classList.contains('prev-ativo') ? '' : '#ccc';
                btn.title = btn.classList.contains('prev-ativo') ? 'Remover previdência' : 'Marcar como previdência';
            });
        });
    });

    // Atualizar risco sem recarregar página
    document.querySelectorAll('.form-update-risco').forEach(function(form) {
        const select = form.querySelector('select');
        select.addEventListener('change', function() {
            ajaxPost(form.action, new FormData(form), function() {
                form.closest('tr').setAttribute('data-risco', select.value);
            });
        });
    });
});
