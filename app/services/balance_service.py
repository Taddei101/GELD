"""
Serviço de balanceamento de carteiras por percentuais de participação.

Responsabilidade: algoritmos de balanceamento, matriz de risco, VP ideal,
distribuição de aportes e gestão de fatias entre objetivos.

Depende de PosicaoService para cálculos de saldo por classe de risco.
"""

from app.models.geld_models import (
    Objetivo, MatrizRisco, DistribuicaoObjetivo,
    IndicadoresEconomicos, TipoObjetivoEnum,
    PosicaoFundo, InfoFundo, RiscoEnum, SubtipoRiscoEnum
)
from app.services.posicao_service import PosicaoService
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session


class BalanceamentoService:
    """Serviço para balanceamento de carteiras com percentuais"""

    TAXA_REAL_ANUAL = 3.5  # IPCA + 3.5% ao ano

    # ========== MÉTODOS DE CÁLCULO DE POSIÇÕES ==========

    @staticmethod
    def calcular_totais_por_classe(cliente_id: int, session: Session) -> Dict[str, float]:
        """
        DELEGADO para PosicaoService — mantido aqui por compatibilidade.
        Prefira chamar PosicaoService.calcular_totais_por_classe() diretamente.
        """
        return PosicaoService.calcular_totais_por_classe(cliente_id, session)

    @staticmethod
    def calcular_valores_atuais_objetivos(
        cliente_id: int,
        totais_classe: Dict[str, float],
        session: Session
    ) -> Dict[int, Dict[str, float]]:
        """
        Aplica percentuais de cada objetivo aos totais para calcular valores atuais.
        Returns: {objetivo_id: {'baixo_di': valor, 'baixo_rfx': valor, 'moderado': valor, 'alto': valor, 'total': valor}}
        """
        objetivos = session.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        valores_por_objetivo = {}

        for obj in objetivos:
            dist = session.query(DistribuicaoObjetivo).filter_by(objetivo_id=obj.id).first()

            if not dist:
                valores_por_objetivo[obj.id] = {
                    'baixo_di': 0.0, 'baixo_rfx': 0.0, 'moderado': 0.0, 'alto': 0.0, 'total': 0.0
                }
            else:
                valores = {
                    'baixo_di': totais_classe['baixo_di'] * (dist.perc_baixo_di / 100),
                    'baixo_rfx': totais_classe['baixo_rfx'] * (dist.perc_baixo_rfx / 100),
                    'moderado':  totais_classe['moderado']  * (dist.perc_moderado  / 100),
                    'alto':      totais_classe['alto']      * (dist.perc_alto      / 100)
                }
                valores['total'] = sum(valores.values())
                valores_por_objetivo[obj.id] = valores

        return valores_por_objetivo

    # ========== MÉTODOS DE MATRIZ DE RISCO ==========

    @staticmethod
    def buscar_matriz_alvo(objetivo: Objetivo, session: Session) -> MatrizRisco:
        """Busca matriz de risco baseada no prazo do objetivo."""
        duracao = objetivo.duracao_meses
        tipo = objetivo.tipo_objetivo

        prazos = [12, 24, 36, 48, 60, 72, 84, 96, 108, 120, 132]
        prazo_arredondado = min(prazos, key=lambda x: abs(x - duracao))

        matriz = session.query(MatrizRisco).filter(
            MatrizRisco.tipo_objetivo == tipo,
            MatrizRisco.duracao_meses == prazo_arredondado
        ).first()

        if not matriz:
            raise ValueError(f"Matriz não encontrada para tipo={tipo}, prazo={prazo_arredondado}")

        return matriz

    @staticmethod
    def distribuir_aporte_por_matriz(valor_aporte: float, matriz: MatrizRisco) -> Dict[str, float]:
        """Distribui aporte em R$ conforme percentuais da matriz."""
        perc_baixo_di  = (matriz.perc_baixo * matriz.perc_di_dentro_baixo)  / 100
        perc_baixo_rfx = (matriz.perc_baixo * matriz.perc_rfx_dentro_baixo) / 100

        return {
            'baixo_di':  valor_aporte * perc_baixo_di  / 100,
            'baixo_rfx': valor_aporte * perc_baixo_rfx / 100,
            'moderado':  valor_aporte * matriz.perc_moderado / 100,
            'alto':      valor_aporte * matriz.perc_alto     / 100
        }

    # ========== VALOR PRESENTE IDEAL ==========

    @staticmethod
    def calcular_vp_ideal(objetivo: Objetivo, ipca_anual: float) -> float:
        """
        Calcula Valor Presente Ideal.
        VP Ideal = valor necessário hoje para atingir objetivo sem aportes adicionais.
        """
        ipca_mensal      = ((1 + ipca_anual / 100) ** (1/12)) - 1
        taxa_real_mensal = ((1 + (ipca_anual + BalanceamentoService.TAXA_REAL_ANUAL) / 100) ** (1/12)) - 1
        duracao          = objetivo.duracao_meses
        valor_futuro     = float(objetivo.valor_final) * ((1 + ipca_mensal) ** duracao)

        return valor_futuro / ((1 + taxa_real_mensal) ** duracao)

    # ========== GESTÃO DE FATIAS ==========

    @staticmethod
    def redistribuir_fatias_apos_delecao(objetivo_id: int, cliente_id: int, session: Session):
        """
        Redistribui as fatias do objetivo deletado proporcionalmente entre os sobreviventes.
        DEVE ser chamado ANTES de deletar o objetivo.

        Exemplo para baixo_di:
            Obj1: 60%, Obj2: 30%, Obj3 (deletado): 10%
            Sobreviventes somam 90%
            Obj1 recebe (60/90) * 10% = 6.67% → fica com 66.67%
            Obj2 recebe (30/90) * 10% = 3.33% → fica com 33.33%
        """
        dist_deletado = session.query(DistribuicaoObjetivo).filter_by(
            objetivo_id=objetivo_id
        ).first()

        if not dist_deletado:
            return

        fatias_deletado = {
            'baixo_di':  dist_deletado.perc_baixo_di,
            'baixo_rfx': dist_deletado.perc_baixo_rfx,
            'moderado':  dist_deletado.perc_moderado,
            'alto':      dist_deletado.perc_alto
        }

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

        for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
            fatia_a_redistribuir = fatias_deletado[classe]

            if fatia_a_redistribuir <= 0:
                continue

            campo = f'perc_{classe}'
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

    # ========== BALANCEAMENTO PRINCIPAL ==========

    @staticmethod
    def processar_balanceamento(
        cliente_id: int,
        aportes_por_objetivo: List[Dict],
        session: Session
    ) -> Dict:
        """
        Processa balanceamento completo da carteira.

        Args:
            cliente_id: ID do cliente
            aportes_por_objetivo: [{'objetivo_id': int, 'valor_aporte': float}]
            session: SQLAlchemy session

        Quando há APORTE:     novos_percentuais = novos_valores  / totais_pos_aporte
        Quando NÃO há aporte: novos_percentuais = estado_alvo    / totais_pos_redistribuicao
        Isso garante que após executar as operações recomendadas o gap zera.
        """
        # 1. Buscar IPCA
        ipca = session.query(IndicadoresEconomicos).order_by(
            IndicadoresEconomicos.data_atualizacao.desc()
        ).first()
        ipca_anual = float(ipca.ipca) if ipca else 4.5

        # 2. Totais atuais por classe
        totais_atuais = PosicaoService.calcular_totais_por_classe(cliente_id, session)

        # 3. Valores atuais por objetivo (usando fatias salvas)
        valores_por_objetivo = BalanceamentoService.calcular_valores_atuais_objetivos(
            cliente_id, totais_atuais, session
        )

        # 4. Processar cada objetivo
        resultados_objetivos = []
        aportes_dict    = {a['objetivo_id']: a['valor_aporte'] for a in aportes_por_objetivo}
        todos_objetivos = session.query(Objetivo).filter_by(cliente_id=cliente_id).all()

        for objetivo in todos_objetivos:
            valor_aporte = aportes_dict.get(objetivo.id, 0.0)
            matriz       = BalanceamentoService.buscar_matriz_alvo(objetivo, session)

            if valor_aporte > 0:
                distribuicao_aporte = BalanceamentoService.distribuir_aporte_por_matriz(valor_aporte, matriz)
            else:
                distribuicao_aporte = {'baixo_di': 0.0, 'baixo_rfx': 0.0, 'moderado': 0.0, 'alto': 0.0}

            valores_atuais = valores_por_objetivo.get(objetivo.id, {
                'baixo_di': 0.0, 'baixo_rfx': 0.0, 'moderado': 0.0, 'alto': 0.0, 'total': 0.0
            })

            novos_valores = {
                'baixo_di':  valores_atuais['baixo_di']  + distribuicao_aporte['baixo_di'],
                'baixo_rfx': valores_atuais['baixo_rfx'] + distribuicao_aporte['baixo_rfx'],
                'moderado':  valores_atuais['moderado']  + distribuicao_aporte['moderado'],
                'alto':      valores_atuais['alto']      + distribuicao_aporte['alto']
            }
            novos_valores['total'] = sum(v for k, v in novos_valores.items() if k != 'total')

            perc_baixo_di  = (matriz.perc_baixo * matriz.perc_di_dentro_baixo)  / 100
            perc_baixo_rfx = (matriz.perc_baixo * matriz.perc_rfx_dentro_baixo) / 100

            estado_alvo = {
                'baixo_di':  novos_valores['total'] * perc_baixo_di  / 100,
                'baixo_rfx': novos_valores['total'] * perc_baixo_rfx / 100,
                'moderado':  novos_valores['total'] * matriz.perc_moderado / 100,
                'alto':      novos_valores['total'] * matriz.perc_alto     / 100
            }

            gap_individual = {
                'baixo_di':  estado_alvo['baixo_di']  - novos_valores['baixo_di'],
                'baixo_rfx': estado_alvo['baixo_rfx'] - novos_valores['baixo_rfx'],
                'moderado':  estado_alvo['moderado']  - novos_valores['moderado'],
                'alto':      estado_alvo['alto']      - novos_valores['alto']
            }

            vp_ideal = BalanceamentoService.calcular_vp_ideal(objetivo, ipca_anual)

            resultados_objetivos.append({
                'objetivo_id':     objetivo.id,
                'objetivo_nome':   objetivo.nome_objetivo,
                'prazo_meses':     objetivo.duracao_meses,
                'valor_desejado':  float(objetivo.valor_final),
                'vp_ideal':        vp_ideal,
                'gap':             vp_ideal - valores_atuais['total'],
                'valor_aporte':    valor_aporte,
                'valores_atuais':  valores_atuais,
                'distribuicao_aporte': distribuicao_aporte,
                'novos_valores':   novos_valores,
                'estado_alvo':     estado_alvo,
                'gap_individual':  gap_individual,
                'percentuais_alvo': {
                    'baixo_di': perc_baixo_di, 'baixo_rfx': perc_baixo_rfx,
                    'moderado': matriz.perc_moderado, 'alto': matriz.perc_alto
                },
                'matriz_prazo': matriz.duracao_meses
            })

        # 5. Agregados
        total_aporte = sum(r['valor_aporte'] for r in resultados_objetivos)

        aportes_agregados = {
            c: sum(r['distribuicao_aporte'][c] for r in resultados_objetivos)
            for c in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']
        }
        acoes_necessarias = {
            c: sum(r['gap_individual'][c] for r in resultados_objetivos)
            for c in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']
        }
        totais_pos_aporte = {
            c: totais_atuais[c] + aportes_agregados[c]
            for c in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']
        }
        totais_pos_redistribuicao = {
            c: totais_pos_aporte[c] + acoes_necessarias[c]
            for c in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']
        }

        # 6. Recalcular percentuais (fatias)
        # Todos os objetivos usam estado_alvo / totais_pos_redistribuicao
        # porque esse é o estado real após executar as operações líquidas
        for resultado in resultados_objetivos:
            resultado['novos_percentuais'] = {
                c: (resultado['estado_alvo'][c] / totais_pos_redistribuicao[c] * 100)
                   if totais_pos_redistribuicao[c] > 0 else 0.0
                for c in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']
            }

        # 7. Consolidar ações
        TOLERANCIA_GAP = 100.0
        acoes_consolidadas = {}

        for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
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

        # 8. Operações líquidas = aporte + rebalanceamento
        # É o que o usuário executa no Advisor — uma única instrução por classe
        TOLERANCIA_OPERACAO = 100.0
        operacoes_liquidas = {}
        for c in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
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
            'totais_atuais':           totais_atuais,
            'totais_novos':            totais_pos_aporte,
            'aportes_agregados':       aportes_agregados,
            'acoes_necessarias':       acoes_necessarias,
            'acoes_consolidadas':      acoes_consolidadas,
            'operacoes_liquidas':      operacoes_liquidas,
            'resultados_por_objetivo': resultados_objetivos
        }

    @staticmethod
    def aplicar_balanceamento(resultado: Dict, session: Session):
        """Aplica balanceamento salvando novos percentuais em DistribuicaoObjetivo."""
        for obj_resultado in resultado['resultados_por_objetivo']:
            objetivo_id       = obj_resultado['objetivo_id']
            novos_percentuais = obj_resultado['novos_percentuais']

            dist = session.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo_id).first()
            if not dist:
                dist = DistribuicaoObjetivo(objetivo_id=objetivo_id)
                session.add(dist)

            dist.perc_baixo_di  = novos_percentuais['baixo_di']
            dist.perc_baixo_rfx = novos_percentuais['baixo_rfx']
            dist.perc_moderado  = novos_percentuais['moderado']
            dist.perc_alto      = novos_percentuais['alto']
            dist.data_atualizacao = datetime.now()

        session.commit()