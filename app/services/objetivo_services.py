from sqlalchemy.orm import Session
from app.models.geld_models import Objetivo, IndicadoresEconomicos

class ObjetivoServices:
    def __init__(self, db: Session = None):
        self.db = db

    def calc_aporte_mensal(self, objetivo_id, taxa_anual_adicional=3.5):
        
        try:
            # Buscar o objetivo
            objetivo = self.db.query(Objetivo).filter(Objetivo.id == objetivo_id).first()
            if not objetivo:
                return {"error": f"Objetivo com ID {objetivo_id} não encontrado"}
            
            # Buscar o IPCA mensal
            indicadores = self.db.query(IndicadoresEconomicos).first()
            if not indicadores or not indicadores.ipca_mes:
                return {"error": "IPCA mensal não encontrado"}
            
            ipca_mensal = indicadores.ipca_mes / 100  # Converter de percentual para decimal
            
            # Converter taxa anual adicional para mensal
            i = ipca_mensal + ((1 + taxa_anual_adicional/100) ** (1/12)) - 1
            
            # Período restante em meses
            n = objetivo.duracao_meses
            
            # Valor presente (capital atual)
            PV = float(objetivo.valor_real)
            
            # Valor futuro (valor objetivo corrigido pela inflação)
            valor_corrigido = float(objetivo.valor_final) * ((1 + ipca_mensal) ** n)
            FV = valor_corrigido
                        
            if i == 0:  # Caso especial para taxa zero
                PMT = (FV - PV) / n
            else:
                fator_futuro = (1 + i) ** n
                PMT = (FV - PV * fator_futuro) * i / (fator_futuro - 1)
            
            # Se PMT for negativo, significa que o valor atual já atinge ou supera o objetivo
            if PMT < 0:
                PMT = 0
                
            return {
                "objetivo_id": objetivo_id,
                "nome_objetivo": objetivo.nome_objetivo,
                "valor_atual": PV,
                "valor_final_original": float(objetivo.valor_final),
                "valor_final_corrigido": valor_corrigido,
                "periodo_meses": n,
                "taxa_mensal": i * 100,  # Convertendo de volta para percentual
                "aporte_mensal": PMT
            }
            
        except Exception as e:
            return {"error": f"Erro ao calcular aporte: {str(e)}"}
    
    def calc_aportes_cliente(self, cliente_id, taxa_anual_adicional=3.5):
       
        try:
            # Buscar todos os objetivos do cliente
            objetivos = self.db.query(Objetivo).filter(Objetivo.cliente_id == cliente_id).all()
            
            if not objetivos:
                return {"error": f"Cliente com ID {cliente_id} não possui objetivos cadastrados"}
            
            resultados = []
            aporte_total = 0
            
            for objetivo in objetivos:
                resultado = self.calc_aporte_mensal(objetivo.id, taxa_anual_adicional)
                
                if "error" in resultado:
                    print(f"Erro no objetivo {objetivo.id}: {resultado['error']}")
                    continue
                    
                resultados.append(resultado)
                aporte_total += resultado["aporte_mensal"]
            
            return {
                "cliente_id": cliente_id,
                "aportes_por_objetivo": resultados,
                "aporte_total_mensal": aporte_total,
                "taxa_anual_adicional": taxa_anual_adicional
            }
            
        except Exception as e:
            return {"error": f"Erro ao calcular aportes do cliente: {str(e)}"}