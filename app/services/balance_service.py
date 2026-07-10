"""
Serviço de balanceamento de carteiras por percentuais de participação.
"""

from app.models.geld_models import (
    Objetivo, MatrizRisco, DistribuicaoObjetivo,
    IndicadoresEconomicos, TipoObjetivoEnum,
    PosicaoFundo, InfoFundo, RiscoEnum, SubtipoRiscoEnum,
    TODAS_CLASSES
)
from app.services.posicao_service import PosicaoService
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session


# ========== HELPERS INTERNOS ==========

def _distribuicao_por_matriz(valor: float, matriz: MatrizRisco) -> Dict[str, float]:
    perc_baixo_di  = (matriz.perc_baixo * matriz.perc_di_dentro_baixo)  / 100
    perc_baixo_rfx = (matriz.perc_baixo * matriz.perc_rfx_dentro_baixo) / 100
    return {
        'baixo_di':      valor * perc_baixo_di            / 100,
        'baixo_rfx':     valor * perc_baixo_rfx           / 100,
        'moderado':      valor * matriz.perc_moderado      / 100,
        'alto':          valor * matriz.perc_alto          / 100,
        'ouro':          valor * matriz.perc_ouro          / 100,
        'dolar':         valor * matriz.perc_dolar         / 100,
        'cripto':        valor * matriz.perc_cripto        / 100,
        'internacional': valor * matriz.perc_internacional / 100,
        'fii':           valor * matriz.perc_fii           / 100,
    }


def _percentuais_alvo_da_matriz(matriz: MatrizRisco) -> Dict[str, float]:
    perc_baixo_di  = (matriz.perc_baixo * matriz.perc_di_dentro_baixo)  / 100
    perc_baixo_rfx = (matriz.perc_baixo * matriz.perc_rfx_dentro_baixo) / 100
    return {
        'baixo_di':      perc_baixo_di,
        'baixo_rfx':     perc_baixo_rfx,
        'moderado':      matriz.perc_moderado,
        'alto':          matriz.perc_alto,
        'ouro':          matriz.perc_ouro,
        'dolar':         matriz.perc_dolar,
        'cripto':        matriz.perc_cripto,
        'internacional': matriz.perc_internacional,
        'fii':           matriz.perc_fii,
    }


def _zeros() -> Dict[str, float]:
    return {c: 0.0 for c in TODAS_CLASSES}


# ========== SERVICE ==========

class BalanceamentoService:

    TAXA_REAL_ANUAL = 3.5

    @staticmethod
    def calcular_totais_por_classe(
        cliente_id: int, session: Session, excluir_previdencia: bool = False
    ) -> Dict[str, float]:
        return PosicaoService.calcular_totais_por_classe(cliente_id, session, excluir_previdencia)

    @staticmethod
    def calcular_valores_atuais_objetivos(
        cliente_id: int,
        totais_regular: Dict[str, float],
        session: Session,
        totais_todos: Dict[str, float] = None,
    ) -> Dict[int, Dict[str, float]]:
        if totais_todos is None:
            totais_todos = totais_regular

        prev_only = {c: totais_todos.get(c, 0.0) - totais_regular.get(c, 0.0) for c in TODAS_CLASSES}

        objetivos = session.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        valores_por_objetivo = {}
        for obj in objetivos:
            dist = session.query(DistribuicaoObjetivo).filter_by(objetivo_id=obj.id).first()
            if not dist:
                valores = _zeros()
                if obj.tipo_objetivo == TipoObjetivoEnum.previdencia:
                    for c in TODAS_CLASSES:
                        valores[c] = prev_only[c]
                valores['total'] = sum(valores[c] for c in TODAS_CLASSES)
                valores_por_objetivo[obj.id] = valores
            else:
                valores = {
                    c: totais_regular.get(c, 0.0) * (getattr(dist, f'perc_{c}') / 100)
                    for c in TODAS_CLASSES
                }
                if obj.tipo_objetivo == TipoObjetivoEnum.previdencia:
                    for c in TODAS_CLASSES:
                        valores[c] += prev_only[c]
                valores['total'] = sum(valores.values())
                valores_por_objetivo[obj.id] = valores
        return valores_por_objetivo

    @staticmethod
    def buscar_matriz_alvo(objetivo: Objetivo, session: Session) -> MatrizRisco:
        duracao = objetivo.duracao_meses
        tipo    = objetivo.tipo_objetivo
        prazos  = [12, 24, 36, 48, 60, 72, 84, 96, 108, 120, 132]
        prazo_arredondado = next((p for p in prazos if p >= duracao), prazos[-1])
        matriz = session.query(MatrizRisco).filter(
            MatrizRisco.tipo_objetivo == tipo,
            MatrizRisco.duracao_meses == prazo_arredondado
        ).first()
        if not matriz:
            raise ValueError(f"Matriz não encontrada para tipo={tipo}, prazo={prazo_arredondado}")
        return matriz

    @staticmethod
    def distribuir_aporte_por_matriz(valor_aporte: float, matriz: MatrizRisco) -> Dict[str, float]:
        return _distribuicao_por_matriz(valor_aporte, matriz)

    @staticmethod
    def _percentuais_da_matriz(matriz: MatrizRisco) -> Dict[str, float]:
        return _percentuais_alvo_da_matriz(matriz)

    @staticmethod
    def calcular_vp_ideal(objetivo: Objetivo, ipca_anual: float = None) -> float:
        ipca_anual        = ipca_anual if ipca_anual is not None else 0
        ipca_mensal       = (1 + ipca_anual / 100) ** (1/12) - 1
        taxa_real_mensal  = (1 + BalanceamentoService.TAXA_REAL_ANUAL / 100) ** (1/12) - 1
        duracao           = objetivo.duracao_meses

        valor_futuro = float(objetivo.valor_final) * ((1 + ipca_mensal) ** duracao)
        return valor_futuro / ((1 + taxa_real_mensal) ** duracao)

    @staticmethod
    def redistribuir_fatias_apos_delecao(objetivo_id: int, cliente_id: int, session: Session):
        dist_deletado = session.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo_id).first()
        if not dist_deletado:
            return
        fatias_deletado = {c: getattr(dist_deletado, f'perc_{c}') for c in TODAS_CLASSES}
        outros_objetivos = session.query(Objetivo).filter(
            Objetivo.cliente_id == cliente_id,
            Objetivo.id != objetivo_id
        ).all()
        if not outros_objetivos:
            session.delete(dist_deletado)
            session.commit()
            return
        dists_sobreviventes = []
        for obj in outros_objetivos:
            dist = session.query(DistribuicaoObjetivo).filter_by(objetivo_id=obj.id).first()
            if dist:
                dists_sobreviventes.append(dist)
        if not dists_sobreviventes:
            session.delete(dist_deletado)
            session.commit()
            return
        for classe in TODAS_CLASSES:
            fatia_a_redistribuir = fatias_deletado[classe]
            if fatia_a_redistribuir <= 0:
                continue
            campo              = f'perc_{classe}'
            soma_sobreviventes = sum(getattr(d, campo) for d in dists_sobreviventes)
            for dist in dists_sobreviventes:
                fatia_atual = getattr(dist, campo)
                if soma_sobreviventes > 0:
                    proporcao = fatia_atual / soma_sobreviventes
                    adicional = proporcao * fatia_a_redistribuir
                else:
                    adicional = fatia_a_redistribuir / len(dists_sobreviventes)
                setattr(dist, campo, fatia_atual + adicional)
                dist.data_atualizacao = datetime.now()
        session.delete(dist_deletado)
        session.commit()

    @staticmethod
    def processar_balanceamento(
        cliente_id: int,
        aportes_por_objetivo: List[Dict],
        session: Session
    ) -> Dict:
        # 1. IPCA
        ipca = session.query(IndicadoresEconomicos).order_by(
            IndicadoresEconomicos.data_atualizacao.desc()
        ).first()
        ipca_anual = float(ipca.ipca) if ipca else 4.5

        # 2. Totais
        totais_regular = PosicaoService.calcular_totais_por_classe(cliente_id, session, excluir_previdencia=True)
        totais_todos   = PosicaoService.calcular_totais_por_classe(cliente_id, session)
        prev_only      = {c: totais_todos[c] - totais_regular[c] for c in TODAS_CLASSES}

        # 3. Valores atuais por objetivo
        valores_por_objetivo = BalanceamentoService.calcular_valores_atuais_objetivos(
            cliente_id, totais_regular, session, totais_todos
        )

        # 4. Processar cada objetivo
        resultados_objetivos = []
        aportes_dict         = {a['objetivo_id']: a['valor_aporte'] for a in aportes_por_objetivo}
        todos_objetivos      = session.query(Objetivo).filter_by(cliente_id=cliente_id).order_by(
            Objetivo.prioridade.asc().nulls_last(), Objetivo.data_final.asc()
        ).all()

        for objetivo in todos_objetivos:
            valor_aporte    = aportes_dict.get(objetivo.id, 0.0)
            valor_atual_obj = valores_por_objetivo.get(objetivo.id, {}).get('total', 0.0)

            if valor_aporte < 0 and abs(valor_aporte) > valor_atual_obj:
                raise ValueError(
                    f"Saque de R$ {abs(valor_aporte):,.0f} excede o saldo do objetivo "
                    f"'{objetivo.nome_objetivo}' (R$ {valor_atual_obj:,.0f})"
                )

            matriz              = BalanceamentoService.buscar_matriz_alvo(objetivo, session)
            distribuicao_aporte = _distribuicao_por_matriz(valor_aporte, matriz) if valor_aporte != 0 else _zeros()
            valores_atuais      = valores_por_objetivo.get(objetivo.id, {**_zeros(), 'total': 0.0})

            novos_valores = {c: valores_atuais[c] + distribuicao_aporte[c] for c in TODAS_CLASSES}
            novos_valores['total'] = sum(novos_valores.values())

            percentuais_alvo = _percentuais_alvo_da_matriz(matriz)
            estado_alvo      = {c: novos_valores['total'] * percentuais_alvo[c] / 100 for c in TODAS_CLASSES}
            gap_individual   = {c: estado_alvo[c] - novos_valores[c] for c in TODAS_CLASSES}
            vp_ideal         = BalanceamentoService.calcular_vp_ideal(objetivo, ipca_anual)

            resultados_objetivos.append({
                'objetivo_id':         objetivo.id,
                'objetivo_nome':       objetivo.nome_objetivo,
                'tipo_objetivo':       objetivo.tipo_objetivo.value,
                'prazo_meses':         objetivo.duracao_meses,
                'prioridade':          objetivo.prioridade,
                'valor_desejado':      float(objetivo.valor_final),
                'vp_ideal':            vp_ideal,
                'gap_vp':              vp_ideal - novos_valores['total'],
                'valor_aporte':        valor_aporte,
                'valores_atuais':      valores_atuais,
                'distribuicao_aporte': distribuicao_aporte,
                'novos_valores':       novos_valores,
                'estado_alvo':         estado_alvo,
                'gap_individual':      gap_individual,
                'percentuais_alvo':    percentuais_alvo,
                'matriz_prazo':        matriz.duracao_meses,
            })

        # 5. Agregados
        total_aporte      = sum(r['valor_aporte'] for r in resultados_objetivos)
        aportes_agregados = {c: sum(r['distribuicao_aporte'][c] for r in resultados_objetivos) for c in TODAS_CLASSES}
        acoes_necessarias = {c: sum(r['gap_individual'][c] for r in resultados_objetivos) for c in TODAS_CLASSES}
        totais_pos_aporte = {c: totais_todos[c] + aportes_agregados[c] for c in TODAS_CLASSES}

        # 6. Recalcular percentuais (fatias) respeitando prioridade e mix de risco
        # Para cada objetivo em ordem de prioridade:
        #   1. Tenta alocar pelo mix ideal da matriz (maior % primeiro)
        #   2. Se faltar pool numa classe, completa com outras classes disponíveis
        # Resultado: fatias somam 100% por classe, respeitando prioridade

        # Ordenar por prioridade (mesma ordem da cascata)
        resultados_ordenados = sorted(
            resultados_objetivos,
            key=lambda r: (r['prioridade'] is None, r['prioridade'] if r['prioridade'] is not None else 999, r['prazo_meses'])
        )

        # Pool disponível por classe (apenas regular — prev-only é exclusivo da previdência)
        pool_disponivel = {c: totais_regular.get(c, 0.0) for c in TODAS_CLASSES}

        # Alocado por objetivo por classe (em R$)
        alocado_por_obj = {r['objetivo_id']: {c: 0.0 for c in TODAS_CLASSES} for r in resultados_objetivos}

        for resultado in resultados_ordenados:
            obj_id = resultado['objetivo_id']
            eh_prev = resultado['tipo_objetivo'] == 'previdencia'

            # Valor que esse objetivo deve receber (calculado pela cascata)
            valor_necessario = resultado['novos_valores']['total']

            if eh_prev:
                
                # (o calcular_valores_atuais_objetivos já soma prev_only automaticamente)
                prev_total = sum(prev_only.get(c, 0.0) for c in TODAS_CLASSES)
                valor_necessario = max(0.0, valor_necessario - prev_total)

            # Ordenar classes por preferência da matriz (maior % primeiro)
            classes_por_preferencia = sorted(
                TODAS_CLASSES,
                key=lambda c: resultado['percentuais_alvo'].get(c, 0.0),
                reverse=True
            )

            restante = valor_necessario

            # Primeira passagem: aloca pelo mix ideal
            for classe in classes_por_preferencia:
                if restante <= 0:
                    break
                quero = valor_necessario * resultado['percentuais_alvo'].get(classe, 0.0) / 100
                aloco = min(quero, pool_disponivel[classe], restante)
                alocado_por_obj[obj_id][classe] += aloco
                pool_disponivel[classe] -= aloco
                restante -= aloco

            # Segunda passagem: se ainda falta, completa com qualquer classe disponível
            if restante > 0.01:
                for classe in classes_por_preferencia:
                    if restante <= 0:
                        break
                    aloco = min(pool_disponivel[classe], restante)
                    alocado_por_obj[obj_id][classe] += aloco
                    pool_disponivel[classe] -= aloco
                    restante -= aloco

        # Converter R$ alocado em % do pool total por classe
        for resultado in resultados_objetivos:
            obj_id = resultado['objetivo_id']
            resultado['novos_percentuais'] = {}
            for classe in TODAS_CLASSES:
                pool_total_classe = totais_regular.get(classe, 0.0)
                if pool_total_classe > 0:
                    resultado['novos_percentuais'][classe] = (
                        alocado_por_obj[obj_id][classe] / pool_total_classe * 100
                    )
                else:
                    resultado['novos_percentuais'][classe] = 0.0

        

        # 7. Consolidar ações por classe
        TOLERANCIA_GAP     = 100.0
        acoes_consolidadas = {}
        for classe in TODAS_CLASSES:
            gap_total = acoes_necessarias[classe]
            if abs(gap_total) < TOLERANCIA_GAP:
                acoes_consolidadas[classe] = {
                    'tipo': 'REDISTRIBUIR', 'gap_total': gap_total,
                    'descricao': 'Ajustar percentuais entre objetivos (sem aportes/resgates)'
                }
            elif gap_total > 0:
                acoes_consolidadas[classe] = {
                    'tipo': 'COMPRAR', 'gap_total': gap_total, 'valor': gap_total,
                    'descricao': f'Aportar R$ {gap_total:,.0f} nesta classe'
                }
            else:
                acoes_consolidadas[classe] = {
                    'tipo': 'VENDER', 'gap_total': gap_total, 'valor': abs(gap_total),
                    'descricao': f'Resgatar R$ {abs(gap_total):,.0f} desta classe'
                }

        # 8. Operações líquidas
        TOLERANCIA_OPERACAO = 100.0
        operacoes_liquidas  = {}
        for c in TODAS_CLASSES:
            valor_liquido = aportes_agregados[c] + acoes_necessarias[c]
            if abs(valor_liquido) < TOLERANCIA_OPERACAO:
                operacoes_liquidas[c] = {'tipo': 'NEUTRO',  'valor': valor_liquido}
            elif valor_liquido > 0:
                operacoes_liquidas[c] = {'tipo': 'COMPRAR', 'valor': valor_liquido}
            else:
                operacoes_liquidas[c] = {'tipo': 'VENDER',  'valor': abs(valor_liquido)}

        return {
            'cliente_id':              cliente_id,
            'data_calculo':            datetime.now().isoformat(),
            'ipca_usado':              ipca_anual,
            'total_aporte':            total_aporte,
            'totais_atuais':           totais_todos,
            'totais_regular':          totais_regular,
            'totais_novos':            totais_pos_aporte,
            'aportes_agregados':       aportes_agregados,
            'acoes_necessarias':       acoes_necessarias,
            'acoes_consolidadas':      acoes_consolidadas,
            'operacoes_liquidas':      operacoes_liquidas,
            'resultados_por_objetivo': resultados_objetivos,
        }

    @staticmethod
    def executar_cascata_e_rebalancear(
        cliente_id: int,
        aportes_por_objetivo: List[Dict],
        session: Session
    ) -> Dict:
        TOLERANCIA_VP   = 100.0
        todos_objetivos = session.query(Objetivo).filter_by(cliente_id=cliente_id).order_by(
            Objetivo.prioridade.asc().nulls_last(), Objetivo.data_final.asc()
        ).all()
        max_iter = max(len(todos_objetivos) - 1, 1)

        aportes_dict = {a['objetivo_id']: a['valor_aporte'] for a in aportes_por_objetivo}
        for obj in todos_objetivos:
            if obj.id not in aportes_dict:
                aportes_dict[obj.id] = 0.0

        historico_cascata = []

        

        for i in range(max_iter):
            aportes_lista = [{'objetivo_id': oid, 'valor_aporte': v} for oid, v in aportes_dict.items()]
            resultado     = BalanceamentoService.processar_balanceamento(cliente_id, aportes_lista, session)

            doadores = [
                r for r in resultado['resultados_por_objetivo']
                if r['novos_valores']['total'] > r['vp_ideal'] + TOLERANCIA_VP
            ]
            

            receptores = sorted(
                [r for r in resultado['resultados_por_objetivo']
                 if r['vp_ideal'] - r['novos_valores']['total'] > TOLERANCIA_VP],
                key=lambda x: (x['prioridade'] is None, x['prioridade'] if x['prioridade'] is not None else x['prazo_meses'])
            )
            

            movimentacoes_iter = []
            for doador in doadores:
                excedente = doador['novos_valores']['total'] - doador['vp_ideal']
                for receptor in receptores:
                    if excedente <= TOLERANCIA_VP:
                        break
                    deficit = receptor['vp_ideal'] - receptor['novos_valores']['total']
                    if deficit <= TOLERANCIA_VP:
                        continue
                    valor_transferir = min(excedente, deficit)
                    aportes_dict[doador['objetivo_id']]   -= valor_transferir
                    aportes_dict[receptor['objetivo_id']] += valor_transferir
                    movimentacoes_iter.append({
                        'origem_nome':  doador['objetivo_nome'],
                        'destino_nome': receptor['objetivo_nome'],
                        'valor':        valor_transferir,
                    })
                    excedente                          -= valor_transferir
                    receptor['novos_valores']['total'] += valor_transferir
                    doador['novos_valores']['total']   -= valor_transferir

            if not movimentacoes_iter:
                break

            historico_cascata.append({'iteracao': i + 1, 'movimentacoes': movimentacoes_iter})

        aportes_finais = [{'objetivo_id': oid, 'valor_aporte': v} for oid, v in aportes_dict.items()]
        resultado      = BalanceamentoService.processar_balanceamento(cliente_id, aportes_finais, session)
        resultado['historico_cascata'] = historico_cascata
        resultado['tem_cascata']       = len(historico_cascata) > 0
        return resultado

    @staticmethod
    def aplicar_balanceamento(resultado: Dict, session: Session):
        for obj_resultado in resultado['resultados_por_objetivo']:
            objetivo_id       = obj_resultado['objetivo_id']
            novos_percentuais = obj_resultado['novos_percentuais']

            dist = session.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo_id).first()
            if not dist:
                dist = DistribuicaoObjetivo(objetivo_id=objetivo_id)
                session.add(dist)

            for classe in TODAS_CLASSES:
                setattr(dist, f'perc_{classe}', novos_percentuais[classe])

            dist.data_atualizacao = datetime.now()

        session.commit()