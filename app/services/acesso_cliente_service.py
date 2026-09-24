from app.models.geld_models import create_session, Cliente, StatusEnum
from app.models.cliente_auth_models import create_cliente_session, ClienteAuth


def sincronizar_acessos():
    db_geld = create_session()
    db = create_cliente_session()
    resumo = {'criadas': 0, 'emails_atualizados': 0, 'removidas': 0, 'pulados': []}
    try:
        clientes = {c.id: c for c in db_geld.query(Cliente).all()}
        contas = {c.cliente_geld_id: c for c in db.query(ClienteAuth).all()}

        # quem foi apagado ou ficou inativo perde o acesso
        for cliente_id, conta in contas.items():
            cliente = clientes.get(cliente_id)
            if not cliente or cliente.status != StatusEnum.ativo:
                db.delete(conta)
                resumo['removidas'] += 1

        # clientes ativos: cria conta ou atualiza e-mail
        for cliente in clientes.values():
            if cliente.status != StatusEnum.ativo:
                continue
            email = (cliente.email or '').strip().lower()
            cpf = ''.join(filter(str.isdigit, cliente.cpf or ''))
            if not email or len(cpf) < 6:
                resumo['pulados'].append(cliente.nome)
                continue

            conta = contas.get(cliente.id)
            if conta is None:
                conta = ClienteAuth(cliente_geld_id=cliente.id, email=email)
                conta.definir_senha(cpf[:6])
                db.add(conta)
                resumo['criadas'] += 1
            elif conta.email != email:
                conta.email = email
                resumo['emails_atualizados'] += 1

        db.commit()
        return resumo
    finally:
        db.close()
        db_geld.close()