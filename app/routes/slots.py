"""
Rota para visualizar a distribuição por slot (Geld 2.0).

Só leitura: não recalcula nem altera o balanceamento existente.
"""

from flask import Blueprint, render_template, flash, redirect, url_for

from app.models.geld_models import Cliente, create_session
from app.services.global_services import login_required
from app.services.slot_service import calcular_compra_venda_por_slot

slots_bp = Blueprint('slots', __name__, url_prefix='/slots')


@slots_bp.route('/<int:cliente_id>', methods=['GET'])
@login_required
def visualizar(cliente_id):
    """Mostra a distribuição por slot do balanceamento pendente do cliente."""
    db = create_session()

    try:
        cliente = db.query(Cliente).get(cliente_id)
        if not cliente:
            flash('Cliente não encontrado', 'error')
            return redirect(url_for('dashboard.index'))

        if not cliente.balanceamento_pendente_json:
            flash('Calcule o balanceamento antes de ver a distribuição por slot.', 'warning')
            return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))

        distribuicao = calcular_compra_venda_por_slot(cliente, db)

        return render_template(
            'slots/visualizar.html',
            cliente=cliente,
            distribuicao=distribuicao,
        )

    finally:
        db.close()
