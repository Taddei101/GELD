from datetime import datetime
from app.models.geld_models import Objetivo
from app.models.cliente_auth_models import SnapshotObjetivo, create_cliente_session
from app.services.balance_service import BalanceamentoService


def registrar_snapshot(cliente_id, data_extrato, db):
    data = datetime(data_extrato.year, data_extrato.month, data_extrato.day)

    totais_regular = BalanceamentoService.calcular_totais_por_classe(cliente_id, db, excluir_previdencia=True)
    totais_todos = BalanceamentoService.calcular_totais_por_classe(cliente_id, db)
    valores = BalanceamentoService.calcular_valores_atuais_objetivos(cliente_id, totais_regular, db, totais_todos)

    objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).all()

    sessao = create_cliente_session()
    try:
        for obj in objetivos:
            snap = sessao.query(SnapshotObjetivo).filter_by(
                cliente_geld_id=cliente_id, objetivo_id=obj.id, data=data
            ).first()
            if not snap:
                snap = SnapshotObjetivo(cliente_geld_id=cliente_id, objetivo_id=obj.id, data=data)
                sessao.add(snap)
            snap.nome_objetivo = obj.nome_objetivo
            snap.valor = round(valores.get(obj.id, {}).get('total', 0.0), 2)
            snap.valor_alvo = obj.valor_final
            snap.data_alvo = obj.data_final
        sessao.commit()
        return len(objetivos)
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()