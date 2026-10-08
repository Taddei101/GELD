from datetime import datetime, timedelta, timezone
import jwt
from flask import Blueprint, request, jsonify, current_app
from app.models.cliente_auth_models import create_cliente_session, ClienteAuth, SnapshotObjetivo, Movimentacao
from app.models.geld_models import create_session, Cliente, Objetivo, IndicadoresEconomicos
from app.services.rentabilidade_service import retorno_acumulado, cdi_acumulado, valores_em_reais

MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
def mes_fechado(d):
    anterior = d - timedelta(days=1)
    return MESES[anterior.month - 1] + '/' + anterior.strftime('%y')

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
    
def valor_futuro(objetivo, ipca_anual):
    if objetivo.valor_final is None or not objetivo.data_inicial or not objetivo.data_final:
        return None
    ipca_mensal = (1 + ipca_anual / 100) ** (1/12) - 1
    meses = ((objetivo.data_final.year - objetivo.data_inicial.year) * 12
             + (objetivo.data_final.month - objetivo.data_inicial.month))
    return round(float(objetivo.valor_final) * (1 + ipca_mensal) ** meses)

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
        ipca = db_geld.query(IndicadoresEconomicos).order_by(
            IndicadoresEconomicos.data_atualizacao.desc()
        ).first()
        ipca_anual = ipca.ipca if ipca else 4.5

        pontos = {}
        for s in linhas:
            pontos.setdefault(s.objetivo_id, []).append({'data': s.data.date().isoformat(), 'valor': float(s.valor)})

        resultado = []
        for o in objetivos:
            if o.id not in pontos:
                continue
            resultado.append({
                'nome': o.nome_objetivo.strip(),
                'valor_alvo': valor_futuro(o, ipca_anual),
                'data_alvo': o.data_final.date().isoformat() if o.data_final else None,
                'prioridade': o.prioridade,
                'pontos': pontos[o.id],
            })

        return jsonify({'objetivos': resultado})
    finally:
        db.close()
        db_geld.close()

@area_cliente_bp.route('/patrimonio', methods=['GET'])
def patrimonio():
    cliente_id = cliente_id_do_token()
    if not cliente_id:
        return jsonify({'erro': 'Não autenticado'}), 401

    db = create_cliente_session()
    try:
        linhas = db.query(SnapshotObjetivo).filter_by(cliente_geld_id=cliente_id).order_by(SnapshotObjetivo.data).all()
        movs = db.query(Movimentacao).filter_by(cliente_geld_id=cliente_id).order_by(Movimentacao.data).all()

        totais = {}
        for s in linhas:
            dia = datetime(s.data.year, s.data.month, s.data.day)
            totais[dia] = totais.get(dia, 0.0) + float(s.valor)
        mensal = {}
        for dia, valor in totais.items():
            mensal[datetime(dia.year, dia.month, 1)] = valor

        pontos = [(d, round(v, 2)) for d, v in mensal.items()]
        fluxos = [(m.data, float(m.valor)) for m in movs]
        cdi = cdi_acumulado([d for d, _ in pontos]) if pontos else []
        investido, cdi_reais = valores_em_reais(pontos, fluxos, cdi) if pontos else ([], [])


        return jsonify({
            'pontos': [{'data': d.date().isoformat(), 'valor': v} for d, v in pontos],
            'meses': [mes_fechado(d) for d, _ in pontos],
            'movimentacoes': [{'data': d.date().isoformat(), 'valor': v} for d, v in fluxos],
            'retorno_carteira': retorno_acumulado(pontos, fluxos) if pontos else [],
            'retorno_cdi': cdi,
            'investido': investido,
            'cdi_reais': cdi_reais,
        })
        
    finally:
        db.close()

@area_cliente_bp.route('/resumo', methods=['GET'])
def resumo():
    cliente_id = cliente_id_do_token()
    if not cliente_id:
        return jsonify({'erro': 'Não autenticado'}), 401

    db = create_cliente_session()
    try:
        linhas = db.query(SnapshotObjetivo).filter_by(cliente_geld_id=cliente_id).all()
        movs = db.query(Movimentacao).filter_by(cliente_geld_id=cliente_id).all()

        total = None
        atualizado_em = None
        if linhas:
            ultimo_dia = max(s.data.date() for s in linhas)
            total = round(sum(float(s.valor) for s in linhas if s.data.date() == ultimo_dia), 2)
            atualizado_em = mes_fechado(datetime(ultimo_dia.year, ultimo_dia.month, 1))

        investido = round(sum(float(m.valor) for m in movs), 2) if movs else None

        return jsonify({'total': total, 'investido': investido, 'atualizado_em': atualizado_em})
    finally:
        db.close()