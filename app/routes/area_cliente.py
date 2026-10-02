from datetime import datetime, timedelta, timezone
import jwt
from flask import Blueprint, request, jsonify, current_app
from app.models.cliente_auth_models import create_cliente_session, ClienteAuth, SnapshotObjetivo
from app.models.geld_models import create_session, Cliente, Objetivo

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

@area_cliente_bp.route('/trocar-senha', methods=['POST'])
def trocar_senha():
    cliente_id = cliente_id_do_token()
    if not cliente_id:
        return jsonify({'erro': 'Não autenticado'}), 401

    dados = request.get_json(silent=True) or {}
    senha_atual = dados.get('senha_atual') or ''
    nova_senha = dados.get('nova_senha') or ''

    if len(nova_senha) < 8:
        return jsonify({'erro': 'A nova senha precisa ter pelo menos 8 caracteres'}), 400

    db = create_cliente_session()
    try:
        conta = db.query(ClienteAuth).filter_by(cliente_geld_id=cliente_id).first()
        if not conta or not conta.conferir_senha(senha_atual):
            return jsonify({'erro': 'Senha atual incorreta'}), 401
        if conta.conferir_senha(nova_senha):
            return jsonify({'erro': 'A nova senha precisa ser diferente da atual'}), 400

        conta.definir_senha(nova_senha)
        conta.precisa_trocar_senha = False
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()

@area_cliente_bp.route('/snapshots', methods=['GET'])
def snapshots():
    cliente_id = cliente_id_do_token()
    if not cliente_id:
        return jsonify({'erro': 'Não autenticado'}), 401

    db_geld = create_session()
    db = create_cliente_session()
    try:
        objetivos = db_geld.query(Objetivo).filter_by(cliente_id=cliente_id).order_by(
            Objetivo.prioridade.is_(None), Objetivo.prioridade, Objetivo.data_final
        ).all()
        linhas = db.query(SnapshotObjetivo).filter_by(cliente_geld_id=cliente_id).order_by(SnapshotObjetivo.data).all()

        pontos = {}
        for s in linhas:
            pontos.setdefault(s.objetivo_id, []).append({'data': s.data.date().isoformat(), 'valor': float(s.valor)})

        resultado = []
        for o in objetivos:
            if o.id not in pontos:
                continue
            resultado.append({
                'nome': o.nome_objetivo.strip(),
                'valor_alvo': float(o.valor_final) if o.valor_final is not None else None,
                'data_alvo': o.data_final.date().isoformat() if o.data_final else None,
                'prioridade': o.prioridade,
                'pontos': pontos[o.id],
            })

        return jsonify({'objetivos': resultado})
    finally:
        db.close()
        db_geld.close()