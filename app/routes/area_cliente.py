from datetime import datetime, timedelta, timezone
import jwt
from flask import Blueprint, request, jsonify, current_app
from app.models.cliente_auth_models import create_cliente_session, ClienteAuth
from app.models.geld_models import create_session, Cliente

area_cliente_bp = Blueprint('area_cliente', __name__, url_prefix='/api/cliente')

@area_cliente_bp.route('/login', methods=['POST'])
def login():
    dados = request.get_json(silent=True) or {}
    email = (dados.get('email') or '').strip().lower()
    senha = dados.get('senha') or ''

    db = create_cliente_session()
    try:
        conta = db.query(ClienteAuth).filter_by(email=email).first()
        if not conta or not conta.conferir_senha(senha):
            return jsonify({'erro': 'E-mail ou senha inválidos'}), 401

        conta.ultimo_login = datetime.now()
        db.commit()

        token = jwt.encode(
            {'sub': str(conta.cliente_geld_id), 'exp': datetime.now(timezone.utc) + timedelta(hours=2)},
            current_app.secret_key,
            algorithm='HS256',
        )
        return jsonify({'token': token, 'precisa_trocar_senha': conta.precisa_trocar_senha})
    finally:
        db.close()

def cliente_id_do_token():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        dados = jwt.decode(auth[7:], current_app.secret_key, algorithms=['HS256'])
        return int(dados['sub'])
    except jwt.InvalidTokenError:
        return None


@area_cliente_bp.route('/me', methods=['GET'])
def me():
    cliente_id = cliente_id_do_token()
    if not cliente_id:
        return jsonify({'erro': 'Não autenticado'}), 401

    db_geld = create_session()
    try:
        cliente = db_geld.get(Cliente, cliente_id)
        if not cliente:
            return jsonify({'erro': 'Cliente não encontrado'}), 404
        return jsonify({'nome': cliente.nome})
    finally:
        db_geld.close()