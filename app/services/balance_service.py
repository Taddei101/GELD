from sqlalchemy.orm import Session
from typing import List, Dict

# Balanceamento do aporte entre os objetivos
class Balance:
    def __init__(self, db: Session = None):
        self.db = db

    def balancear_aporte(self, aporte: float, objetivos: List) -> Dict:
        """REGRA DE BALANCEAMENTO DE DO APORTE ENTRE OS OBJETIVOS. ATUALMENTE DIVIDE IGUALMENTE"""
        try:
            num_objetivos = len(objetivos)
            if num_objetivos == 0:
                return {"error": "Não há objetivos cadastrados"}
            
            aporte = float(aporte)
            valor_por_objetivo = aporte / num_objetivos
        
            # Dicionario das quotas linkadas ao objetivo_id
            quotas = {objetivo.id: valor_por_objetivo for objetivo in objetivos}
           
            return quotas
        
        except Exception as e:
            return {"error": f"Erro ao balancear aporte: {str(e)}"}

    def balancear_quota(self, quota: float, objetivo) -> Dict:
        """
        Balanceia a quota de um objetivo entre diferentes níveis de risco
        TEMPORÁRIO: Tabela hardcoded até implementar nova matriz
        """
        try:
            if not objetivo:
                return {"error": "Objetivo não encontrado"}
            
            # Obter a duração em meses do objetivo
            duracao_meses = objetivo.duracao_meses
            
            # TABELA TEMPORÁRIA - substituir pela nova matriz no futuro
            tabela_riscos = [
                {"prazo": 12, "risco_baixo": 0.0, "risco_moderado": 0.135, "risco_alto": 0.015, "risco_di": 1},
                {"prazo": 24, "risco_baixo": 0.635, "risco_moderado": 0.178, "risco_alto": 0.037, "risco_di": 0.15},
                {"prazo": 36, "risco_baixo": 0.670, "risco_moderado": 0.213, "risco_alto": 0.067, "risco_di": 0.05},
                {"prazo": 48, "risco_baixo": 0.605, "risco_moderado": 0.238, "risco_alto": 0.107, "risco_di": 0.05},
                {"prazo": 60, "risco_baixo": 0.540, "risco_moderado": 0.254, "risco_alto": 0.156, "risco_di": 0.05},
                {"prazo": 72, "risco_baixo": 0.475, "risco_moderado": 0.261, "risco_alto": 0.214, "risco_di": 0.05},
                {"prazo": 84, "risco_baixo": 0.410, "risco_moderado": 0.259, "risco_alto": 0.281, "risco_di": 0.05},
                {"prazo": 96, "risco_baixo": 0.345, "risco_moderado": 0.248, "risco_alto": 0.357, "risco_di": 0.05},
                {"prazo": 108, "risco_baixo": 0.280, "risco_moderado": 0.228, "risco_alto": 0.442, "risco_di": 0.05},
                {"prazo": 120, "risco_baixo": 0.215, "risco_moderado": 0.198, "risco_alto": 0.537, "risco_di": 0.05},
                {"prazo": 132, "risco_baixo": 0.150, "risco_moderado": 0.160, "risco_alto": 0.640, "risco_di": 0.05}
            ]
            
            # Encontrar a regra correspondente ao prazo do objetivo
            regra_aplicavel = None
            
            # Se for menor ou igual ao menor prazo na tabela
            if duracao_meses <= tabela_riscos[0]["prazo"]:
                regra_aplicavel = tabela_riscos[0]
            # Se for maior ou igual ao maior prazo na tabela
            elif duracao_meses >= tabela_riscos[-1]["prazo"]:
                regra_aplicavel = tabela_riscos[-1]
            else:
                # Percorrer a tabela para encontrar o prazo mais próximo
                for i in range(len(tabela_riscos)-1):
                    prazo_atual = tabela_riscos[i]["prazo"]
                    proximo_prazo = tabela_riscos[i+1]["prazo"]
                    
                    # Se o prazo estiver exatamente em uma das entradas da tabela
                    if duracao_meses == prazo_atual:
                        regra_aplicavel = tabela_riscos[i]
                        break
                    
                    # Se o prazo estiver entre duas entradas da tabela, pega a maior
                    if prazo_atual < duracao_meses < proximo_prazo:
                        regra_aplicavel = tabela_riscos[i+1]
                        break
            
            # Aplicar a regra encontrada
            percentagens = {
                "risco_baixo": regra_aplicavel["risco_baixo"],
                "risco_moderado": regra_aplicavel["risco_moderado"],
                "risco_alto": regra_aplicavel["risco_alto"],
                "risco_di": regra_aplicavel["risco_di"]
            }
            
            # Adicionar informação da regra aplicada ao resultado
            prazo_aplicado = regra_aplicavel["prazo"]
            
            # Calcular a quota para cada tipo de risco
            balanceamento = {
                "objetivo_id": objetivo.id,
                "nome_objetivo": objetivo.nome_objetivo,
                "quota_total": quota,
                "duracao_meses": duracao_meses,
                "prazo_referencia": prazo_aplicado,
                "distribuicao": {
                    "risco_baixo": {
                        "percentagem": percentagens["risco_baixo"] * 100,
                        "valor": quota * percentagens["risco_baixo"]
                    },
                    "risco_moderado": {
                        "percentagem": percentagens["risco_moderado"] * 100,
                        "valor": quota * percentagens["risco_moderado"]
                    },
                    "risco_alto": {
                        "percentagem": percentagens["risco_alto"] * 100,
                        "valor": quota * percentagens["risco_alto"]
                    },
                    "risco_di":{
                        "percentagem": percentagens["risco_di"] * 100,
                        "valor": quota * percentagens["risco_di"]
                    }
                }
            }
            
            # Log opcional
            print(f"Objetivo: {balanceamento['nome_objetivo']} (ID: {balanceamento['objetivo_id']})")
            print(f"Quota Total: {balanceamento['quota_total']}")
            print(f"Duração: {balanceamento['duracao_meses']} meses (Prazo ref.: {balanceamento['prazo_referencia']} meses)")
            print(f"Distribuição:")
            print(f"  Risco Baixo: {balanceamento['distribuicao']['risco_baixo']['percentagem']}% = {balanceamento['distribuicao']['risco_baixo']['valor']}")
            print(f"  Risco Moderado: {balanceamento['distribuicao']['risco_moderado']['percentagem']}% = {balanceamento['distribuicao']['risco_moderado']['valor']}")
            print(f"  Risco Alto: {balanceamento['distribuicao']['risco_alto']['percentagem']}% = {balanceamento['distribuicao']['risco_alto']['valor']}")
            print(f"  Risco DI: {balanceamento['distribuicao']['risco_di']['percentagem']}% = {balanceamento['distribuicao']['risco_di']['valor']}")
            
            return balanceamento
            
        except Exception as e:
            return {"error": f"Erro ao balancear quota para objetivo {objetivo.id if objetivo else 'desconhecido'}: {str(e)}"}