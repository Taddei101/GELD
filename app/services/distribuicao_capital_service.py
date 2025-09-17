from app.models.geld_models import InfoFundo, PosicaoFundo, Objetivo, RiscoEnum
from sqlalchemy import func
import logging
from decimal import Decimal

class DistribuicaoCapitalService:
        
    def __init__(self, db=None):
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    def distribuir_capital(self, cliente_id):
        """
        Distribui o capital existente nos fundos para objetivos do cliente
        Args:
            cliente_id: ID do cliente            
        Returns:
            Dict com o resultado da alocação
        """
        try:
            # 1. Obter posições do cliente
            posicoes = self.db.query(PosicaoFundo).filter(PosicaoFundo.cliente_id == cliente_id).all()
            if not posicoes:
                return {"error": f"Cliente com ID {cliente_id} não possui posições em fundos"}
            
            # 2. Obter objetivos do cliente ordenados por prazo (crescente)
            objetivos = self.db.query(Objetivo).filter(Objetivo.cliente_id == cliente_id).all()
            if not objetivos:
                return {"error": f"Cliente com ID {cliente_id} não possui objetivos cadastrados"}
            
            # Ordenar objetivos por prazo
            objetivos_ordenados = sorted(objetivos, key=lambda obj: obj.duracao_meses)
            
            # 3. Calcular valor total disponível
            total_disponivel = self.db.query(
                func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
            ).join(
                InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
            ).filter(
                PosicaoFundo.cliente_id == cliente_id
            ).scalar() or Decimal('0')
            
            # Converter para float 
            total_disponivel_float = float(total_disponivel)
            
            # 4. Agrupar investimentos por nível de risco
            investimentos_por_risco = {
                RiscoEnum.baixo: [],
                RiscoEnum.moderado: [],
                RiscoEnum.alto: [],
                RiscoEnum.fundo_DI: []

            }
            
            # Processar cada posição
            for posicao in posicoes:
                valor_posicao = float(posicao.cotas * posicao.info_fundo.valor_cota)
                
                investimentos_por_risco[posicao.info_fundo.risco].append({
                    "id": posicao.id,
                    "fundo_id": posicao.fundo_id,
                    "nome_fundo": posicao.info_fundo.nome_fundo,
                    "risco": posicao.info_fundo.risco,
                    "valor": valor_posicao,
                    "valor_cota": float(posicao.info_fundo.valor_cota),
                    "cotas": float(posicao.cotas)
                })
            
            # 5. Calcular total por tipo de risco
            total_por_risco = {
                RiscoEnum.baixo: sum(inv["valor"] for inv in investimentos_por_risco[RiscoEnum.baixo]),
                RiscoEnum.moderado: sum(inv["valor"] for inv in investimentos_por_risco[RiscoEnum.moderado]),
                RiscoEnum.alto: sum(inv["valor"] for inv in investimentos_por_risco[RiscoEnum.alto]),
                RiscoEnum.fundo_DI: sum(inv["valor"] for inv in investimentos_por_risco[RiscoEnum.fundo_DI])

            }
            
            # 6. Preparar resultado
            resultado = {
                "alocacao_por_objetivo": {},
                "objetivos_nao_atendidos": [],
                "capital_nao_alocado": 0.0,
                "sumario": {
                    "total_disponivel": total_disponivel_float,
                    "total_alocado": 0.0,
                    "percentual_alocado": 0.0
                },
                "total_por_risco": {
                    RiscoEnum.baixo.value: total_por_risco[RiscoEnum.baixo],
                    RiscoEnum.moderado.value: total_por_risco[RiscoEnum.moderado], 
                    RiscoEnum.alto.value: total_por_risco[RiscoEnum.alto],
                    RiscoEnum.fundo_DI.value: total_por_risco[RiscoEnum.fundo_DI]
                }
            }
            
            # 7. Cópias de trabalho
            saldo_por_risco = total_por_risco.copy()
            investimentos_restantes = {k: list(v) for k, v in investimentos_por_risco.items()}
            
            # 8. Distribuir para cada objetivo por ordem de prazo
            for objetivo in objetivos_ordenados:
                objetivo_id = objetivo.id
                
                # Valor alvo para este objetivo - todo valor alvo, não considerando valor_real
                valor_alvo = float(objetivo.valor_final)
                
                # Determinar o perfil de risco baseado no prazo
                perfil_risco = self._determinar_perfil_risco(objetivo.duracao_meses)
                
                # Inicializar alocação para este objetivo
                resultado["alocacao_por_objetivo"][objetivo_id] = {
                    "nome": objetivo.nome_objetivo,
                    "valor_alvo": valor_alvo,
                    "prazo_meses": objetivo.duracao_meses,
                    "alocacao_total": 0.0,
                    "percentual_atingido": 0.0,
                    "alocacao_por_investimento": [],
                    "alocacao_por_risco": {
                        RiscoEnum.baixo.value: 0.0,
                        RiscoEnum.moderado.value: 0.0, 
                        RiscoEnum.alto.value: 0.0,
                        RiscoEnum.fundo_DI.value: 0.0
                    }
                }
                
                # Calcular alocação ideal por tipo de risco
                alocacao_ideal = self._calcular_alocacao_ideal(valor_alvo, perfil_risco)
                
                # Alocar fundos para cada tipo de risco
                for risco, valor_ideal in alocacao_ideal.items():
                    valor_alocado = self._alocar_por_risco(
                        risco,
                        valor_ideal,
                        saldo_por_risco,
                        investimentos_restantes,
                        resultado["alocacao_por_objetivo"][objetivo_id]
                    )
                    
                    # Atualizar totais
                    resultado["alocacao_por_objetivo"][objetivo_id]["alocacao_total"] += valor_alocado
                    resultado["alocacao_por_objetivo"][objetivo_id]["alocacao_por_risco"][risco.value] += valor_alocado
                
                # Calcular percentual atingido
                valor_alocado = resultado["alocacao_por_objetivo"][objetivo_id]["alocacao_total"]
                
                percentual = (valor_alocado / valor_alvo * 100) if valor_alvo > 0 else 0
                resultado["alocacao_por_objetivo"][objetivo_id]["percentual_atingido"] = round(min(percentual, 100), 2)
                
                # Se não atingiu 100%, adicionar à lista de não totalmente atendidos
                if percentual < 100:
                    resultado["objetivos_nao_atendidos"].append({
                        "id": objetivo_id,
                        "nome": objetivo.nome_objetivo,
                        "valor_alvo": valor_alvo,
                        "valor_alocado": valor_alocado,
                        "percentual_atingido": round(percentual, 2),
                        "valor_faltante": valor_alvo - valor_alocado
                    })
            
            # 9. Calcular capital não alocado
            capital_nao_alocado = sum(saldo_por_risco.values())
            resultado["capital_nao_alocado"] = capital_nao_alocado
            
            # 10. Atualizar sumário
            resultado["sumario"]["total_alocado"] = total_disponivel_float - capital_nao_alocado
            resultado["sumario"]["percentual_alocado"] = round(
                (resultado["sumario"]["total_alocado"] / total_disponivel_float * 100) 
                if total_disponivel_float > 0 else 0.0, 2
            )
            
            return resultado
        
        except Exception as e:
            self.logger.error(f"Erro na distribuição de capital: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": f"Erro na distribuição de capital: {str(e)}"}
    
    def _determinar_perfil_risco(self, prazo_meses):
        """
        Determina o perfil de risco ideal baseado no prazo 
        Args:
            prazo_meses
        Returns:
            Dict com a distribuição percentual por tipo de risco
        """
        if prazo_meses <= 12:
            # Curto prazo
            return {RiscoEnum.baixo: 0.80, RiscoEnum.moderado: 0.15, RiscoEnum.alto: 0.05,RiscoEnum.fundo_DI: 0.0}
        elif prazo_meses <= 36:
            # Médio prazo
            return {RiscoEnum.baixo: 0.50, RiscoEnum.moderado: 0.35, RiscoEnum.alto: 0.15,RiscoEnum.fundo_DI: 0.0}
        elif prazo_meses <= 60:
            # Médio-longo prazo  
            return {RiscoEnum.baixo: 0.30, RiscoEnum.moderado: 0.40, RiscoEnum.alto: 0.30,RiscoEnum.fundo_DI: 0.0}
        else:
            # Longo prazo
            return {RiscoEnum.baixo: 0.15, RiscoEnum.moderado: 0.35, RiscoEnum.alto: 0.50,RiscoEnum.fundo_DI: 0.0}
    
    def _calcular_alocacao_ideal(self, valor_alvo, perfil_risco):
        """
        Calcula quanto deve ser alocado em cada tipo de risco para o objetivo
        Args:
            valor_alvo
            perfil_risco: Distribuição percentual por tipo de risco
        Returns:
            Dict com valores absolutos por tipo de risco
        """
        return {risco: valor_alvo * percentual for risco, percentual in perfil_risco.items()}
    
    def _alocar_por_risco(self, risco, valor_ideal, saldo_por_risco, investimentos_restantes, resultado_objetivo):
        """
        Aloca fundos de um tipo de risco específico para um objetivo
        Args:
            risco, valor_ideal, saldo_por_risco,investimentos_restantes
            resultado_objetivo.
        Returns:
            Valor total alocado deste tipo de risco
        """
        # Verificar quanto pode ser alocado deste risco
        valor_disponivel = min(valor_ideal, saldo_por_risco[risco])
        
        if valor_disponivel <= 0:
            return 0.0
        
        valor_alocado_total = 0.0
        
        # Ordenar investimentos por valor (do maior para o menor)
        investimentos = sorted(investimentos_restantes[risco], key=lambda x: x["valor"], reverse=True)
        
        for inv in investimentos:
            inv_id = inv["id"]
            inv_valor = inv["valor"]
            
            # Quanto alocar deste investimento
            valor_a_alocar = min(valor_disponivel - valor_alocado_total, inv_valor)
            
            if valor_a_alocar <= 0:
                continue
            
            # Percentual de cotas a alocar do total
            percentual_cotas = valor_a_alocar / inv_valor
            cotas_alocadas = percentual_cotas * inv["cotas"]
            
            # Atualizar o valor do investimento
            inv_index = next(i for i, x in enumerate(investimentos_restantes[risco]) if x["id"] == inv_id)
            investimentos_restantes[risco][inv_index]["valor"] -= valor_a_alocar
            investimentos_restantes[risco][inv_index]["cotas"] -= cotas_alocadas
            
            # Se o investimento foi totalmente usado, remove-o
            if investimentos_restantes[risco][inv_index]["valor"] <= 0.01:  # Margem de erro
                investimentos_restantes[risco].pop(inv_index)
            
            # Atualizar saldo disponível
            saldo_por_risco[risco] -= valor_a_alocar
            
            # Adicionar ao resultado do objetivo
            resultado_objetivo["alocacao_por_investimento"].append({
                "posicao_id": inv_id,
                "fundo_id": inv["fundo_id"],
                "nome_fundo": inv["nome_fundo"],
                "risco": risco.value,
                "valor_alocado": valor_a_alocar,
                "cotas_alocadas": cotas_alocadas
            })
            
            valor_alocado_total += valor_a_alocar
            
            # Se já alocou tudo o que precisava, para
            if valor_alocado_total >= valor_disponivel - 0.01:  # Margem de erro
                break
        
        return valor_alocado_total