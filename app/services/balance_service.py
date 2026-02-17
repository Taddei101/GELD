"""
Serviço de balanceamento baseado em percentuais de participação
"""

from app.models.geld_models import (
    Objetivo, MatrizRisco, DistribuicaoObjetivo, 
    IndicadoresEconomicos, TipoObjetivoEnum,
    PosicaoFundo, InfoFundo, RiscoEnum, SubtipoRiscoEnum
)
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from sqlalchemy.orm import Session


class BalanceamentoService:
    """Serviço para balanceamento de carteiras com percentuais"""
    
    TAXA_REAL_ANUAL = 3.5  # IPCA + 3.5% ao ano
    
    # ========== MÉTODOS DE CÁLCULO DE POSIÇÕES ==========
    
    @staticmethod
    def calcular_totais_por_classe(cliente_id: int, session: Session) -> Dict[str, float]:
        """
        Calcula total investido por classe de risco a partir de PosicaoFundo
        Returns:
            {'baixo_di': X, 'baixo_rfx': Y, 'moderado': Z, 'alto': W}
        """
        totais = {
            'baixo_di': 0.0,
            'baixo_rfx': 0.0,
            'moderado': 0.0,
            'alto': 0.0
        }
        
        posicoes = session.query(PosicaoFundo).filter_by(cliente_id=cliente_id).all()
        
        for pos in posicoes:
            fundo = pos.info_fundo
            valor = float(pos.cotas) * float(fundo.valor_cota)
            
            if fundo.risco == RiscoEnum.baixo:
                if fundo.subtipo_risco == SubtipoRiscoEnum.di:
                    totais['baixo_di'] += valor
                elif fundo.subtipo_risco == SubtipoRiscoEnum.rfx:
                    totais['baixo_rfx'] += valor
                else:
                    totais['baixo_rfx'] += valor
            elif fundo.risco == RiscoEnum.moderado:
                totais['moderado'] += valor
            elif fundo.risco == RiscoEnum.alto:
                totais['alto'] += valor
        
        return totais
    
    @staticmethod
    def calcular_valores_atuais_objetivos(
        cliente_id: int, 
        totais_classe: Dict[str, float],
        session: Session
    ) -> Dict[int, Dict[str, float]]:
        """
        Aplica percentuais de cada objetivo aos totais para calcular valores atuais
        Returns:{objetivo_id: {'baixo_di': valor,'baixo_rfx': valor,'moderado': valor,'alto': valor,'total': valor}}
        """
        objetivos = session.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        
        valores_por_objetivo = {}
        
        for obj in objetivos:
            dist = session.query(DistribuicaoObjetivo).filter_by(objetivo_id=obj.id).first()
            
            if not dist:
                valores_por_objetivo[obj.id] = {
                    'baixo_di': 0.0,
                    'baixo_rfx': 0.0,
                    'moderado': 0.0,
                    'alto': 0.0,
                    'total': 0.0
                }
            else:
                valores = {
                    'baixo_di': totais_classe['baixo_di'] * (dist.perc_baixo_di / 100),
                    'baixo_rfx': totais_classe['baixo_rfx'] * (dist.perc_baixo_rfx / 100),
                    'moderado': totais_classe['moderado'] * (dist.perc_moderado / 100),
                    'alto': totais_classe['alto'] * (dist.perc_alto / 100)
                }
                valores['total'] = sum(valores.values())
                valores_por_objetivo[obj.id] = valores
        
        return valores_por_objetivo
    
    # ========== MÉTODOS DE MATRIZ DE RISCO ==========
    
    @staticmethod
    def buscar_matriz_alvo(objetivo: Objetivo, session: Session) -> MatrizRisco:
        """Busca matriz de risco baseada no prazo do objetivo"""
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
        """
        Distribui aporte em R$ conforme percentuais da matriz
        """
        perc_baixo_di = (matriz.perc_baixo * matriz.perc_di_dentro_baixo) / 100
        perc_baixo_rfx = (matriz.perc_baixo * matriz.perc_rfx_dentro_baixo) / 100
        
        return {
            'baixo_di': valor_aporte * perc_baixo_di / 100,
            'baixo_rfx': valor_aporte * perc_baixo_rfx / 100,
            'moderado': valor_aporte * matriz.perc_moderado / 100,
            'alto': valor_aporte * matriz.perc_alto / 100
        }
    
    # ========== MÉTODOS DE Valor Presente (VP) IDEAL ==========
    
    @staticmethod
    def calcular_vp_ideal(objetivo: Objetivo, ipca_anual: float) -> float:
        """
        Calcula Valor Presente Ideal
        
        VP Ideal = valor necessário hoje para atingir objetivo sem aportes adicionais
        """
        ipca_mensal = ((1 + ipca_anual / 100) ** (1/12)) - 1
        taxa_real_mensal = ((1 + (ipca_anual + BalanceamentoService.TAXA_REAL_ANUAL) / 100) ** (1/12)) - 1
        
        duracao = objetivo.duracao_meses
        
        valor_futuro = float(objetivo.valor_final) * ((1 + ipca_mensal) ** duracao)
        vp_ideal = valor_futuro / ((1 + taxa_real_mensal) ** duracao)
        
        return vp_ideal
    
    # ========== MÉTODO PRINCIPAL DE BALANCEAMENTO ==========
    
    @staticmethod
    def processar_balanceamento(
        cliente_id: int,
        aportes_por_objetivo: List[Dict],
        session: Session
    ) -> Dict:
        """
        Processa balanceamento completo.

        Lógica de estabilização:
        - Cada aporte é distribuído pela MATRIZ do objetivo que recebeu o dinheiro.
        - Os novos percentuais (fatias) são recalculados simplesmente dividindo o
          valor absoluto de cada objetivo pelo novo pool total da classe.
        - Objetivos sem aporte preservam seus valores absolutos em R$ — apenas sua
          fatia percentual diminui proporcionalmente porque o pool cresceu.
        - Isso garante convergência: nenhum objetivo é perturbado sem ter recebido capital.
        """
        # 1. Buscar IPCA
        indicadores = session.query(IndicadoresEconomicos).first()
        if not indicadores:
            raise ValueError("IPCA não encontrado")
        
        ipca_anual = indicadores.ipca
        
        # 2. Calcular totais ATUAIS por classe (de PosicaoFundo)
        totais_atuais = BalanceamentoService.calcular_totais_por_classe(cliente_id, session)
        
        # 3. Calcular valores atuais por objetivo (aplicando % salvos)
        valores_atuais_obj = BalanceamentoService.calcular_valores_atuais_objetivos(
            cliente_id, totais_atuais, session
        )
        
        # 4. Processar TODOS os objetivos (com e sem aporte)
        todos_objetivos = session.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        resultados_objetivos = []
        
        aportes_dict = {a['objetivo_id']: a['valor_aporte'] for a in aportes_por_objetivo}
        
        for objetivo in todos_objetivos:
            valor_aporte = aportes_dict.get(objetivo.id, 0.0)
            
            matriz = BalanceamentoService.buscar_matriz_alvo(objetivo, session)
            
            if valor_aporte > 0:
                # Distribui o aporte pela matriz DESTE objetivo
                distribuicao_aporte = BalanceamentoService.distribuir_aporte_por_matriz(
                    valor_aporte, matriz
                )
            else:
                distribuicao_aporte = {
                    'baixo_di': 0.0,
                    'baixo_rfx': 0.0,
                    'moderado': 0.0,
                    'alto': 0.0
                }
            
            valores_atuais = valores_atuais_obj.get(objetivo.id, {
                'baixo_di': 0, 'baixo_rfx': 0, 'moderado': 0, 'alto': 0, 'total': 0
            })
            
            # Novos valores absolutos = atuais + aporte distribuído
            novos_valores = {
                'baixo_di': valores_atuais['baixo_di'] + distribuicao_aporte['baixo_di'],
                'baixo_rfx': valores_atuais['baixo_rfx'] + distribuicao_aporte['baixo_rfx'],
                'moderado': valores_atuais['moderado'] + distribuicao_aporte['moderado'],
                'alto': valores_atuais['alto'] + distribuicao_aporte['alto']
            }
            novos_valores['total'] = sum(v for k, v in novos_valores.items() if k != 'total')
            
            # Estado alvo DESTE objetivo segundo sua matriz (para exibição de gap)
            perc_baixo_di = (matriz.perc_baixo * matriz.perc_di_dentro_baixo) / 100
            perc_baixo_rfx = (matriz.perc_baixo * matriz.perc_rfx_dentro_baixo) / 100
            
            estado_alvo = {
                'baixo_di': novos_valores['total'] * perc_baixo_di / 100,
                'baixo_rfx': novos_valores['total'] * perc_baixo_rfx / 100,
                'moderado': novos_valores['total'] * matriz.perc_moderado / 100,
                'alto': novos_valores['total'] * matriz.perc_alto / 100
            }
            
            gap_individual = {
                'baixo_di': estado_alvo['baixo_di'] - novos_valores['baixo_di'],
                'baixo_rfx': estado_alvo['baixo_rfx'] - novos_valores['baixo_rfx'],
                'moderado': estado_alvo['moderado'] - novos_valores['moderado'],
                'alto': estado_alvo['alto'] - novos_valores['alto']
            }
            
            vp_ideal = BalanceamentoService.calcular_vp_ideal(objetivo, ipca_anual)
            gap = vp_ideal - valores_atuais['total']
            
            perc_alvo = {
                'baixo_di': perc_baixo_di,
                'baixo_rfx': perc_baixo_rfx,
                'moderado': matriz.perc_moderado,
                'alto': matriz.perc_alto
            }
            
            resultados_objetivos.append({
                'objetivo_id': objetivo.id,
                'objetivo_nome': objetivo.nome_objetivo,
                'prazo_meses': objetivo.duracao_meses,
                'valor_desejado': float(objetivo.valor_final),
                'vp_ideal': vp_ideal,
                'gap': gap,
                'valor_aporte': valor_aporte,
                'valores_atuais': valores_atuais,
                'distribuicao_aporte': distribuicao_aporte,
                'novos_valores': novos_valores,
                'gap_individual': gap_individual,
                'percentuais_alvo': perc_alvo,
                'matriz_prazo': matriz.duracao_meses
            })
        
        # 5. Calcular agregados
        total_aporte = sum(r['valor_aporte'] for r in resultados_objetivos)
        
        aportes_agregados = {
            'baixo_di': sum(r['distribuicao_aporte']['baixo_di'] for r in resultados_objetivos),
            'baixo_rfx': sum(r['distribuicao_aporte']['baixo_rfx'] for r in resultados_objetivos),
            'moderado': sum(r['distribuicao_aporte']['moderado'] for r in resultados_objetivos),
            'alto': sum(r['distribuicao_aporte']['alto'] for r in resultados_objetivos)
        }
        
        acoes_necessarias = {
            'baixo_di': sum(r['gap_individual']['baixo_di'] for r in resultados_objetivos),
            'baixo_rfx': sum(r['gap_individual']['baixo_rfx'] for r in resultados_objetivos),
            'moderado': sum(r['gap_individual']['moderado'] for r in resultados_objetivos),
            'alto': sum(r['gap_individual']['alto'] for r in resultados_objetivos)
        }
        
        totais_pos_aporte = {
            'baixo_di': totais_atuais['baixo_di'] + aportes_agregados['baixo_di'],
            'baixo_rfx': totais_atuais['baixo_rfx'] + aportes_agregados['baixo_rfx'],
            'moderado': totais_atuais['moderado'] + aportes_agregados['moderado'],
            'alto': totais_atuais['alto'] + aportes_agregados['alto']
        }
        
        # 6. Recalcular percentuais (fatias) por divisão direta dos valores absolutos.
        #
        #    REGRA: fatia(obj, classe) = novos_valores(obj, classe) / pool_total(classe)
        #
        #    Isso garante estabilidade porque:
        #    - Objetivos sem aporte preservam seu valor absoluto → sua fatia só diminui
        #      proporcionalmente se o pool cresceu, sem perturbação na composição.
        #    - Objetivos com aporte crescem exatamente pela matriz → convergem gradualmente.
        #    - A soma das fatias por classe é sempre 100% por definição matemática.
        
        for resultado in resultados_objetivos:
            novos_percentuais = {}
            for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
                pool = totais_pos_aporte[classe]
                if pool > 0:
                    novos_percentuais[classe] = (resultado['novos_valores'][classe] / pool) * 100
                else:
                    novos_percentuais[classe] = 0.0
            resultado['novos_percentuais'] = novos_percentuais
        
        # 7. Consolidar ações por classe de risco
        acoes_consolidadas = {}
        TOLERANCIA_GAP = 100.0  # R$ 100 de tolerância
        
        for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
            gap_total = acoes_necessarias[classe]
            
            if abs(gap_total) < TOLERANCIA_GAP:
                acoes_consolidadas[classe] = {
                    'tipo': 'REDISTRIBUIR',
                    'gap_total': gap_total,
                    'descricao': 'Ajustar percentuais entre objetivos (sem aportes/resgates)'
                }
            elif gap_total > 0:
                acoes_consolidadas[classe] = {
                    'tipo': 'COMPRAR',
                    'gap_total': gap_total,
                    'valor': gap_total,
                    'descricao': f'Aportar R$ {gap_total:,.0f} nesta classe'
                }
            else:
                acoes_consolidadas[classe] = {
                    'tipo': 'VENDER',
                    'gap_total': gap_total,
                    'valor': abs(gap_total),
                    'descricao': f'Resgatar R$ {abs(gap_total):,.0f} desta classe'
                }
        
        # 8. Retornar resultado completo
        return {
            'cliente_id': cliente_id,
            'data_calculo': datetime.now().isoformat(),
            'ipca_usado': ipca_anual,
            'total_aporte': total_aporte,
            'totais_atuais': totais_atuais,
            'totais_novos': totais_pos_aporte,
            'aportes_agregados': aportes_agregados,
            'acoes_necessarias': acoes_necessarias,
            'acoes_consolidadas': acoes_consolidadas,
            'resultados_por_objetivo': resultados_objetivos
        }
    
    @staticmethod
    def aplicar_balanceamento(resultado: Dict, session: Session):
        """
        Aplica balanceamento, salvando novos percentuais em DistribuicaoObjetivo
        """
        for obj_resultado in resultado['resultados_por_objetivo']:
            objetivo_id = obj_resultado['objetivo_id']
            novos_percentuais = obj_resultado['novos_percentuais']
            
            dist = session.query(DistribuicaoObjetivo).filter_by(
                objetivo_id=objetivo_id
            ).first()
            
            if not dist:
                dist = DistribuicaoObjetivo(objetivo_id=objetivo_id)
                session.add(dist)
            
            dist.perc_baixo_di = novos_percentuais['baixo_di']
            dist.perc_baixo_rfx = novos_percentuais['baixo_rfx']
            dist.perc_moderado = novos_percentuais['moderado']
            dist.perc_alto = novos_percentuais['alto']
            dist.data_atualizacao = datetime.now()
        
        session.commit()