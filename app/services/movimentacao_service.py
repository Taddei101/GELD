from app.models.cliente_auth_models import Movimentacao, create_cliente_session


def registrar_movimentacao(cliente_id, data, valor, objetivo_id=None):
    sessao = create_cliente_session()
    try:
        mov = Movimentacao(cliente_geld_id=cliente_id, objetivo_id=objetivo_id, data=data, valor=valor)
        sessao.add(mov)
        sessao.commit()
        return mov.id
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()

def listar_movimentacoes(cliente_id):
    sessao = create_cliente_session()
    try:
        movs = (sessao.query(Movimentacao)
                .filter_by(cliente_geld_id=cliente_id)
                .order_by(Movimentacao.data.desc())
                .all())
        return [{'id': m.id, 'data': m.data, 'valor': float(m.valor)} for m in movs]
    finally:
        sessao.close()

def excluir_movimentacao(cliente_id, movimentacao_id):
    sessao = create_cliente_session()
    try:
        apagadas = (sessao.query(Movimentacao)
                    .filter_by(id=movimentacao_id, cliente_geld_id=cliente_id)
                    .delete())
        sessao.commit()
        return apagadas > 0
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()