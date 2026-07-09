from typing import Dict, List
from sqlalchemy.orm import Session

from app.models.geld_models import SubtipoAtivo, InfoFundo, PosicaoFundo, RiscoEnum, SubtipoRiscoEnum, TODAS_CLASSES


CLASSES_PREV = ['ouro', 'dolar', 'cripto', 'internacional', 'fii']


def distribuir_por_ativo(
    cliente_id: int,
    operacoes_liquidas: Dict,
    session: Session
) -> Dict:
    resultado = {}

    for classe_str in TODAS_CLASSES:
        if classe_str in CLASSES_PREV:
            continue

        operacao = operacoes_liquidas.get(classe_str, {})
        if operacao.get('tipo') == 'NEUTRO':
            continue

        classe_enum = _classe_str_para_enum(classe_str)
        if classe_enum is None:
            continue

        valor_operacao = operacao.get('valor', 0.0)
        tipo_operacao = operacao.get('tipo')

        if classe_str == 'baixo_di':
            resultado[classe_str] = _distribuir_di(cliente_id, valor_operacao, tipo_operacao, session)
        else:
            subtipo_risco = SubtipoRiscoEnum.rfx if classe_str == 'baixo_rfx' else None
            entry = _distribuir_por_slots(cliente_id, classe_enum, subtipo_risco, valor_operacao, tipo_operacao, session)
            if entry:
                resultado[classe_str] = entry

    # Agregar as 5 classes de hedge/previdência numa entrada única
    entry_prev = _distribuir_previdencia(cliente_id, operacoes_liquidas, session)
    if entry_prev:
        resultado['previdencia'] = entry_prev

    return resultado


def _distribuir_di(
    cliente_id: int,
    valor_operacao: float,
    tipo_operacao: str,
    session: Session
) -> Dict:
    """Baixo DI: lista fundos DI do cliente, alvo proporcional ao atual de cada um."""
    posicoes = (
        session.query(PosicaoFundo)
        .join(InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id)
        .filter(
            PosicaoFundo.cliente_id == cliente_id,
            InfoFundo.risco == RiscoEnum.baixo,
            InfoFundo.subtipo_risco == SubtipoRiscoEnum.di,
        )
        .all()
    )

    fundos = []
    for p in posicoes:
        atual_R = round(float(p.cotas) * float(p.info_fundo.valor_cota), 2)
        fundos.append({
            'id': p.info_fundo.id,
            'nome': p.info_fundo.nome_fundo,
            'atual_R': atual_R,
        })

    total_atual = sum(f['atual_R'] for f in fundos)
    total_alvo = round(total_atual + (valor_operacao if tipo_operacao == 'COMPRAR' else -valor_operacao), 2)

    # Alvo por fundo proporcional ao atual; se não tem nada, divide igual
    for f in fundos:
        if total_atual > 0:
            proporcao = f['atual_R'] / total_atual
        else:
            proporcao = 1.0 / len(fundos) if fundos else 0.0
        f['alvo_R'] = round(total_alvo * proporcao, 2)
        f['delta_R'] = round(f['alvo_R'] - f['atual_R'], 2)

    return {
        'tipo_operacao': tipo_operacao,
        'valor_total': valor_operacao,
        'modo': 'di',
        'total_atual': total_atual,
        'total_alvo': total_alvo,
        'fundos_di': fundos,
        'slots': [],
    }


def _distribuir_por_slots(
    cliente_id: int,
    classe_enum: RiscoEnum,
    subtipo_risco,
    valor_operacao: float,
    tipo_operacao: str,
    session: Session
) -> Dict:
    """Slots A/B/C/D para rfx e demais classes."""
    subtipos = (
        session.query(SubtipoAtivo)
        .filter(SubtipoAtivo.classe_risco == classe_enum)
        .order_by(SubtipoAtivo.letra)
        .all()
    )

    if not subtipos:
        return None

    # Primeira passagem: coleta atual_R de cada slot
    slots_raw = []
    for subtipo in subtipos:
        fundos_do_slot = (
            session.query(InfoFundo)
            .filter(InfoFundo.subtipo_ativo_id == subtipo.id)
            .all()
        )

        if subtipo_risco is not None:
            fundos_validos = [f for f in fundos_do_slot if f.subtipo_risco == subtipo_risco]
        else:
            fundos_validos = fundos_do_slot

        fundo_ids = [f.id for f in fundos_validos]
        posicoes = (
            session.query(PosicaoFundo)
            .filter(
                PosicaoFundo.cliente_id == cliente_id,
                PosicaoFundo.fundo_id.in_(fundo_ids)
            )
            .all()
            if fundo_ids else []
        )

        atual_R = round(sum(
            float(p.cotas) * float(p.info_fundo.valor_cota)
            for p in posicoes
        ), 2)

        fundo_ids_com_posicao = {p.fundo_id for p in posicoes}
        fundos_info = [
            {'id': f.id, 'nome': f.nome_fundo, 'is_previdencia': f.is_previdencia}
            for f in fundos_validos
            if f.id in fundo_ids_com_posicao
        ]

        slots_raw.append({
            'subtipo': subtipo,
            'atual_R': atual_R,
            'fundos_info': fundos_info,
            'sem_fundo': len(fundos_do_slot) == 0,
            'sem_posicao': len(fundos_do_slot) > 0 and len(fundos_info) == 0,
        })

    # total_alvo = posição atual da classe ± operação
    total_atual_classe = sum(s['atual_R'] for s in slots_raw)
    total_alvo_classe = round(
        total_atual_classe + (valor_operacao if tipo_operacao == 'COMPRAR' else -valor_operacao),
        2
    )

    slots = []
    for s in slots_raw:
        subtipo = s['subtipo']
        alvo_R = round(total_alvo_classe * subtipo.percentual_ideal / 100, 2)
        slots.append({
            'subtipo_id': subtipo.id,
            'letra': subtipo.letra,
            'nome': subtipo.nome,
            'percentual_ideal': subtipo.percentual_ideal,
            'alvo_R': alvo_R,
            'atual_R': s['atual_R'],
            'delta_R': round(alvo_R - s['atual_R'], 2),
            'fundos': s['fundos_info'],
            'sem_fundo': s['sem_fundo'],
            'sem_posicao': s['sem_posicao'],
        })

    return {
        'tipo_operacao': tipo_operacao,
        'valor_total': valor_operacao,
        'modo': 'slots',
        'total_atual': total_atual_classe,
        'total_alvo': total_alvo_classe,
        'slots': slots,
    }


def _distribuir_previdencia(
    cliente_id: int,
    operacoes_liquidas: Dict,
    session: Session
) -> Dict:
    """Agrega ouro/dolar/cripto/internacional/fii numa tabela única de previdência/hedge."""
    linhas = []
    total_atual = 0.0
    total_delta = 0.0
    tem_operacao = False

    for classe_str in CLASSES_PREV:
        operacao = operacoes_liquidas.get(classe_str, {})
        tipo_operacao = operacao.get('tipo', 'NEUTRO')
        valor_operacao = operacao.get('valor', 0.0)

        classe_enum = _classe_str_para_enum(classe_str)
        posicoes = (
            session.query(PosicaoFundo)
            .join(InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id)
            .filter(
                PosicaoFundo.cliente_id == cliente_id,
                InfoFundo.risco == classe_enum,
            )
            .all()
        )

        atual_R = round(sum(float(p.cotas) * float(p.info_fundo.valor_cota) for p in posicoes), 2)

        if tipo_operacao == 'COMPRAR':
            delta_R = round(valor_operacao, 2)
            tem_operacao = True
        elif tipo_operacao == 'VENDER':
            delta_R = round(-valor_operacao, 2)
            tem_operacao = True
        else:
            delta_R = 0.0

        alvo_R = round(atual_R + delta_R, 2)

        fundos = [
            {'id': p.info_fundo.id, 'nome': p.info_fundo.nome_fundo}
            for p in posicoes
        ]

        linhas.append({
            'classe': classe_str,
            'label': classe_str.replace('_', ' ').title(),
            'atual_R': atual_R,
            'alvo_R': alvo_R,
            'delta_R': delta_R,
            'tipo_operacao': tipo_operacao,
            'fundos': fundos,
            'sem_posicao': len(posicoes) == 0,
        })

        total_atual += atual_R
        total_delta += delta_R

    # Só omite se não há posições nem operações em nenhuma das 5 classes
    tem_posicao = any(l['atual_R'] > 0 for l in linhas)
    if not tem_operacao and not tem_posicao:
        return None

    total_alvo = round(total_atual + total_delta, 2)
    valor_total = round(abs(total_delta), 2)
    tipo_total = 'COMPRAR' if total_delta > 0 else ('VENDER' if total_delta < 0 else 'NEUTRO')

    return {
        'tipo_operacao': tipo_total,
        'valor_total': valor_total,
        'modo': 'prev',
        'total_atual': total_atual,
        'total_alvo': total_alvo,
        'linhas': linhas,
    }


def _classe_str_para_enum(classe_str: str):
    mapa = {
        'baixo_di':      RiscoEnum.baixo,
        'baixo_rfx':     RiscoEnum.baixo,
        'moderado':      RiscoEnum.moderado,
        'alto':          RiscoEnum.alto,
        'ouro':          RiscoEnum.ouro,
        'dolar':         RiscoEnum.dolar,
        'cripto':        RiscoEnum.cripto,
        'internacional': RiscoEnum.internacional,
        'fii':           RiscoEnum.fii,
    }
    return mapa.get(classe_str)
