"""
Distribuição por slot (Geld 2.0).

Lê o resultado do balanceamento já calculado (operacoes_liquidas, salvo em
cliente.balanceamento_pendente_json) e diz, por classe de risco, quanto
comprar ou vender em cada slot — com os fundos que o cliente já tem ali.

Só 3 classes usam slot (A/B/C/D): baixo_rfx, moderado, alto — dentro delas
os fundos têm perfis diferentes (volatilidade, liquidez, indexador). O alvo
da classe (atual + delta do balanceamento) é dividido em partes iguais entre
os slots que têm algum fundo cadastrado — isso prioriza comprar nos slots
zerados/defasados até nivelar todos, em vez de manter a proporção antiga de
percentual_ideal. Slots sem nenhum fundo cadastrado ficam fora da divisão
(não dá pra comprar ali). As outras 6 classes (baixo_di, ouro, dolar,
cripto, internacional, fii) não têm slot: qualquer fundo da classe serve,
então a classe inteira é um grupo só.

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


def calcular_compra_venda_por_slot(cliente, db, operacoes=None):
    """
    Retorna, por classe de risco com operação pendente:
      [{fundo_nomes: [...], atual, alvo, delta}, ...]

    Para classes com slot, cada linha é um slot (fundos do cliente ali,
    valores somados). Para classes sem slot, é uma linha só para a classe
    inteira.

    Por padrão lê cliente.balanceamento_pendente_json['operacoes_liquidas'].
    Passe `operacoes` (mesmo formato: {classe: {tipo, valor}}) para ratear
    outro conjunto de operações pelos mesmos slots — ex: operacoes_sem_prev.
    """
    if operacoes is None:
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

    fundos_por_slot = {slot.id: _fundos_do_cliente_no_slot(cliente_id, slot.id, db) for slot in slots}
    tem_fundo_por_slot = {
        slot.id: db.query(InfoFundo.id).filter_by(subtipo_ativo_id=slot.id).first() is not None
        for slot in slots
    }

    atual_por_slot = {slot.id: sum(atual for _, atual in fundos_por_slot[slot.id]) for slot in slots}
    total_atual_classe = sum(atual_por_slot.values())
    total_alvo_classe = total_atual_classe + delta_classe

    n_slots_com_fundo = sum(1 for slot in slots if tem_fundo_por_slot[slot.id])
    alvo_por_slot = (total_alvo_classe / n_slots_com_fundo) if n_slots_com_fundo else 0.0

    linhas = []
    for slot in slots:
        alvo_slot = alvo_por_slot if tem_fundo_por_slot[slot.id] else 0.0
        fatia_slot = alvo_slot - atual_por_slot[slot.id]
        linhas.append(_linha_do_grupo(fundos_por_slot[slot.id], fatia_slot))

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
