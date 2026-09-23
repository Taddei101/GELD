from app.models.geld_models import create_session, Cliente, StatusEnum
from app.models.cliente_auth_models import init_cliente_db, create_cliente_session, ClienteAuth

init_cliente_db()
db_geld = create_session()
db = create_cliente_session()

clientes = db_geld.query(Cliente).filter(Cliente.status == StatusEnum.ativo).all()

criados = 0
for cliente in clientes:
    ja_existe = db.query(ClienteAuth).filter_by(cliente_geld_id=cliente.id).first()
    if ja_existe:
        print(f'Pulando {cliente.nome}: já tem conta')
        continue

    cpf_digitos = ''.join(filter(str.isdigit, cliente.cpf))
    conta = ClienteAuth(cliente_geld_id=cliente.id, email=cliente.email.strip().lower())
    conta.definir_senha(cpf_digitos[:6])
    db.add(conta)
    criados += 1
    print(f'Criando conta: {cliente.nome}')

db.commit()
print(f'{criados} contas criadas de {len(clientes)} clientes ativos')

db.close()
db_geld.close()