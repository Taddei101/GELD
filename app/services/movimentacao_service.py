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