"""
Rotas de pipelines — sequências de ações do fluxo de trabalho do assessor
encadeadas em um único clique.
"""

from flask import Blueprint, redirect, url_for, flash
from app.models.geld_models import create_session, Objetivo, DistribuicaoObjetivo, TODAS_CLASSES
from app.services.global_services import login_required

pipelines_bp = Blueprint('pipelines', __name__, url_prefix='/pipelines')


@pipelines_bp.route('/rapida/<int:cliente_id>', methods=['POST'])
@login_required
def rapida(cliente_id):
    """Reseta as fatias e aloca 100% no objetivo prioritário, indo para o balanceamento."""
    db = create_session()

    try:
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).order_by(
            Objetivo.prioridade.asc().nulls_last(), Objetivo.data_final.asc()
        ).all()

        if not objetivos:
            flash('Cliente não possui objetivos cadastrados.', 'warning')
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))

        objetivo_prioritario = objetivos[0]

        objetivo_ids = [o.id for o in objetivos]
        db.query(DistribuicaoObjetivo).filter(
            DistribuicaoObjetivo.objetivo_id.in_(objetivo_ids)
        ).delete(synchronize_session=False)
        db.flush()

        dist = DistribuicaoObjetivo(objetivo_id=objetivo_prioritario.id)
        for c in TODAS_CLASSES:
            setattr(dist, f'perc_{c}', 100.0)
        db.add(dist)

        db.commit()
        flash(f'Fatias resetadas e 100% alocado em "{objetivo_prioritario.nome_objetivo}".', 'success')

    except Exception as e:
        db.rollback()
        flash(f'Erro ao executar pipeline rápida: {str(e)}', 'error')
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    finally:
        db.close()

    return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
