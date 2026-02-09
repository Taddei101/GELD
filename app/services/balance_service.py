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
        
        # Buscar todas posições do cliente
        posicoes = session.query(PosicaoFundo).filter_by(cliente_id=cliente_id).all()
        
        for pos in posicoes:
            fundo = pos.info_fundo
            valor = float(pos.cotas) * float(fundo.valor_cota)
            
            # Classificar por risco
            if fundo.risco == RiscoEnum.baixo:
                if fundo.subtipo_risco == SubtipoRiscoEnum.di:
                    totais['baixo_di'] += valor
                elif fundo.subtipo_risco == SubtipoRiscoEnum.rfx:
                    totais['baixo_rfx'] += valor
                else:
                    # Se não tem subtipo, assumir RFx
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
            # Buscar distribuição (percentuais)
            dist = session.query(DistribuicaoObjetivo).filter_by(objetivo_id=obj.id).first()
            
            if not dist:
                # Objetivo sem distribuição ainda
                valores_por_objetivo[obj.id] = {
                    'baixo_di': 0.0,
                    'baixo_rfx': 0.0,
                    'moderado': 0.0,
                    'alto': 0.0,
                    'total': 0.0
                }
            else:
                # Aplicar percentuais
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
        
        # Prazos disponíveis
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
        # Calcular percentuais absolutos
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
        
        # Valor futuro corrigido pela inflação
        valor_futuro = float(objetivo.valor_final) * ((1 + ipca_mensal) ** duracao)
        
        # Trazer a VP com taxa real
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
        Processa balanceamento completo
        Args:
            aportes_por_objetivo: Obj1,X reais, Obj2, Y reais
        Returns:
            Resultado do balanceamento
        """
        # 1. Buscar IPCA
        indicadores = session.query(IndicadoresEconomicos).first()
        if not indicadores:
            raise ValueError("IPCA não encontrado")
        
        ipca_anual = indicadores.ipca
        
        # 2. Calcular totais ATUAIS por classe (de PosicaoFundo)
        totais_atuais = BalanceamentoService.calcular_totais_por_classe(cliente_id, session)
        
        # 3. Calcular valores atuais por objetivo (aplicando % atuais)
        valores_atuais_obj = BalanceamentoService.calcular_valores_atuais_objetivos(
            cliente_id, totais_atuais, session
        )
        
        # 4. Processar TODOS os objetivos (com e sem aporte)
        todos_objetivos = session.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        resultados_objetivos = []
        novos_valores_por_classe = {k: 0.0 for k in totais_atuais.keys()}
        
        # Criar dict de aportes para lookup rápido
        aportes_dict = {a['objetivo_id']: a['valor_aporte'] for a in aportes_por_objetivo}
        
        for objetivo in todos_objetivos:
            valor_aporte = aportes_dict.get(objetivo.id, 0.0)
            
            # Buscar matriz e distribuir aporte (se houver)
            matriz = BalanceamentoService.buscar_matriz_alvo(objetivo, session)
            
            if valor_aporte > 0:
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
            
            # Valores atuais deste objetivo
            valores_atuais = valores_atuais_obj.get(objetivo.id, {
                'baixo_di': 0, 'baixo_rfx': 0, 'moderado': 0, 'alto': 0, 'total': 0
            })
            
            # Novos valores = atuais + aporte
            novos_valores = {
                'baixo_di': valores_atuais['baixo_di'] + distribuicao_aporte['baixo_di'],
                'baixo_rfx': valores_atuais['baixo_rfx'] + distribuicao_aporte['baixo_rfx'],
                'moderado': valores_atuais['moderado'] + distribuicao_aporte['moderado'],
                'alto': valores_atuais['alto'] + distribuicao_aporte['alto']
            }
            novos_valores['total'] = sum([v for k, v in novos_valores.items() if k != 'total'])
            
            # Acumular para calcular totais depois
            for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
                novos_valores_por_classe[classe] += novos_valores[classe]
            
            # Calcular VP Ideal e Gap
            vp_ideal = BalanceamentoService.calcular_vp_ideal(objetivo, ipca_anual)
            gap = vp_ideal - valores_atuais['total']
            
            # Percentuais da matriz
            perc_alvo = {
                'baixo_di': (matriz.perc_baixo * matriz.perc_di_dentro_baixo) / 100,
                'baixo_rfx': (matriz.perc_baixo * matriz.perc_rfx_dentro_baixo) / 100,
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
                'percentuais_alvo': perc_alvo,
                'matriz_prazo': matriz.duracao_meses
            })
        
        # 5. Calcular novos PERCENTUAIS de cada objetivo
        # Total geral por classe = soma dos novos valores de todos objetivos
        totais_novos = novos_valores_por_classe
        
        # Calcular percentual de cada objetivo
        for resultado in resultados_objetivos:
            novos_percentuais = {}
            for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
                total_classe = totais_novos[classe]
                valor_obj = resultado['novos_valores'][classe]
                
                if total_classe > 0:
                    novos_percentuais[classe] = (valor_obj / total_classe) * 100
                else:
                    novos_percentuais[classe] = 0.0
            
            resultado['novos_percentuais'] = novos_percentuais
        
        # 6. Resultado agregado
        total_aporte = sum(r['valor_aporte'] for r in resultados_objetivos)
        
        aportes_agregados = {
            'baixo_di': sum(r['distribuicao_aporte']['baixo_di'] for r in resultados_objetivos),
            'baixo_rfx': sum(r['distribuicao_aporte']['baixo_rfx'] for r in resultados_objetivos),
            'moderado': sum(r['distribuicao_aporte']['moderado'] for r in resultados_objetivos),
            'alto': sum(r['distribuicao_aporte']['alto'] for r in resultados_objetivos)
        }
        
        # ✅ CALCULAR GAPS AGREGADOS (diferença entre novo e atual)
        gaps_agregados = {
            'baixo_di': totais_novos['baixo_di'] - totais_atuais['baixo_di'],
            'baixo_rfx': totais_novos['baixo_rfx'] - totais_atuais['baixo_rfx'],
            'moderado': totais_novos['moderado'] - totais_atuais['moderado'],
            'alto': totais_novos['alto'] - totais_atuais['alto']
        }
        
        return {
            'cliente_id': cliente_id,
            'data_calculo': datetime.now().isoformat(),
            'ipca_usado': ipca_anual,
            'total_aporte': total_aporte,
            'totais_atuais': totais_atuais,
            'totais_novos': totais_novos,
            'aportes_agregados': aportes_agregados,
            'gaps_agregados': gaps_agregados,  # ✅ NOVO CAMPO
            'resultados_por_objetivo': resultados_objetivos
        }
    
    @staticmethod
    def aplicar_balanceamento(resultado: Dict, session: Session):
        """
        Aplica balanceamento, salvando novos percentuais em DistribuicaoObjetivo
        ✅ REMOVIDO: atualização de valor_real (campo não existe mais)
        """
        for obj_resultado in resultado['resultados_por_objetivo']:
            objetivo_id = obj_resultado['objetivo_id']
            novos_percentuais = obj_resultado['novos_percentuais']
            
            # Buscar ou criar distribuição
            dist = session.query(DistribuicaoObjetivo).filter_by(
                objetivo_id=objetivo_id
            ).first()
            
            if not dist:
                dist = DistribuicaoObjetivo(objetivo_id=objetivo_id)
                session.add(dist)
            
            # Atualizar percentuais
            dist.perc_baixo_di = novos_percentuais['baixo_di']
            dist.perc_baixo_rfx = novos_percentuais['baixo_rfx']
            dist.perc_moderado = novos_percentuais['moderado']
            dist.perc_alto = novos_percentuais['alto']
            dist.data_atualizacao = datetime.now()
            
            # ✅ REMOVIDO: objetivo.valor_real (campo não existe mais no modelo)
        
        session.commit()