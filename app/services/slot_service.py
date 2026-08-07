"""
Distribuição por slot (Geld 2.0).

Lê o resultado do balanceamento já calculado (operacoes_liquidas, salvo em
cliente.balanceamento_pendente_json) e diz, por classe de risco, quanto
comprar ou vender em cada slot — com os fundos que o cliente já tem ali.

Só 3 classes usam slot (A/B/C/D): baixo_rfx, moderado, alto — dentro delas
os fundos têm perfis diferentes (volatilidade, liquidez, indexador) e o
valor da classe é dividido entre os slots pelo percentual_ideal de cada um.
As outras 6 classes (baixo_di, ouro, dolar, cripto, internacional, fii) não
têm slot: qualquer fundo da classe serve, então a classe inteira é um grupo
só.

Não recalcula nada do balanceamento e não escreve no banco — só leitura.
"""

import json

from app.models.geld_models import InfoFundo, PosicaoFundo, SubtipoAtivo, SubtipoRiscoEnum

CLASSES_COM_SLOT = {'baixo_rfx', 'moderado', 'alto'}

# Classe "composta" -> (risco no banco, subtipo_risco no banco ou None)
RISCO_E_SUBTIPO = {
    'baixo_di':      ('baixo', SubtipoRiscoEnum.di),
    'baixo_rfx':     ('baixo', SubtipoRiscoEnum.rfx),
    'moderado':      ('moderado', None),
    'alto':          ('alto', None),
    'ouro':          ('ouro', None),
    'dolar':         ('dolar', None),
    'cripto':        ('cripto', None),
    'internacional': ('internacional', None),
    'fii':           ('fii', None),
}


def calcular_compra_venda_por_slot(cliente, db):
    """
    Retorna, por classe de risco com operação pendente:
      [{fundo_nomes: [...], atual, alvo, delta}, ...]

    Para classes com slot, cada linha é um slot (fundos do cliente ali,
    valores somados). Para classes sem slot, é uma linha só para a classe
    inteira.
    """
    resultado_bruto = cliente.balanceamento_pendente_json
    if not resultado_bruto:
        return {}

    operacoes = json.loads(resultado_bruto).get('operacoes_liquidas', {})

    distribuicao = {}
    for classe, operacao in operacoes.items():
        delta_classe = operacao['valor'] if operacao['tipo'] == 'COMPRAR' else -operacao['valor']
        if delta_classe == 0:
            continue

        if classe in CLASSES_COM_SLOT:
            linhas = _linhas_com_slot(cliente.id, classe, delta_classe, db)
        else:
            linhas = _linhas_sem_slot(cliente.id, classe, delta_classe, db)

        if linhas:
            distribuicao[classe] = linhas

    return distribuicao


def _linhas_com_slot(cliente_id, classe, delta_classe, db):
    slots = db.query(SubtipoAtivo).filter_by(classe_risco=RISCO_E_SUBTIPO[classe][0]).all()

    linhas = []
    for slot in slots:
        fundos = _fundos_do_cliente_no_slot(cliente_id, slot.id, db)
        fatia_slot = delta_classe * (slot.percentual_ideal / 100.0)
        linhas.append(_linha_do_grupo(fundos, fatia_slot))

    return linhas


def _linhas_sem_slot(cliente_id, classe, delta_classe, db):
    risco, subtipo_risco = RISCO_E_SUBTIPO[classe]
    fundos = _fundos_do_cliente_na_classe(cliente_id, risco, subtipo_risco, db)
    return [_linha_do_grupo(fundos, delta_classe)]


def _linha_do_grupo(fundos, delta_grupo):
    """Soma o atual de todos os fundos do grupo (slot ou classe) e aplica o delta inteiro."""
    atual_total = sum(atual for _, atual in fundos)
    return {
        'fundo_nomes': [fundo.nome_fundo for fundo, _ in fundos],
        'atual': round(atual_total, 2),
        'alvo': round(atual_total + delta_grupo, 2),
        'delta': round(delta_grupo, 2),
    }


def _fundos_do_cliente_no_slot(cliente_id, subtipo_ativo_id, db):
    return _posicoes_por_fundo(
        db.query(PosicaoFundo)
        .join(InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id)
        .filter(
            PosicaoFundo.cliente_id == cliente_id,
            InfoFundo.subtipo_ativo_id == subtipo_ativo_id,
        )
    )


def _fundos_do_cliente_na_classe(cliente_id, risco, subtipo_risco, db):
    query = (
        db.query(PosicaoFundo)
        .join(InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id)
        .filter(
            PosicaoFundo.cliente_id == cliente_id,
            InfoFundo.risco == risco,
        )
    )
    if subtipo_risco is not None:
        query = query.filter(InfoFundo.subtipo_risco == subtipo_risco)
    return _posicoes_por_fundo(query)


def _posicoes_por_fundo(query):
    """Agrupa posições por fundo, somando cotas * valor_cota de cada uma."""
    valores_por_fundo = {}
    for posicao in query.all():
        fundo = posicao.info_fundo
        valor = float(posicao.cotas) * float(fundo.valor_cota)
        valores_por_fundo[fundo] = valores_por_fundo.get(fundo, 0.0) + valor
    return list(valores_por_fundo.items())
