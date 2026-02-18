"""
Serviço de posições - cálculos sobre PosicaoFundo

Responsabilidade única: responder "quanto o cliente tem investido, e em quê?"

Usado por:
- posicao.py (rota) - exibição na tela
- balance_service.py - cálculos de balanceamento
- distribuicao_capital_service.py - simulação de alocação
"""

from app.models.geld_models import PosicaoFundo, InfoFundo, RiscoEnum, SubtipoRiscoEnum
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict


class PosicaoService:

    @staticmethod
    def calcular_totais_por_classe(cliente_id: int, session: Session) -> Dict[str, float]:
        """
        Calcula total investido por subclasse de risco usando SQL agregado.

        Retorna:
            {
                'baixo_di':  float,  # Risco baixo, subtipo DI
                'baixo_rfx': float,  # Risco baixo, subtipo RFx ou sem subtipo
                'moderado':  float,
                'alto':      float
            }
        
        """

        def _query_soma(filtros):
            return float(
                session.query(
                    func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
                ).join(
                    InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
                ).filter(
                    PosicaoFundo.cliente_id == cliente_id,
                    *filtros
                ).scalar() or 0.0
            )

        return {
            'baixo_di': _query_soma([
                InfoFundo.risco == RiscoEnum.baixo,
                InfoFundo.subtipo_risco == SubtipoRiscoEnum.di
            ]),
            'baixo_rfx': _query_soma([
                InfoFundo.risco == RiscoEnum.baixo,
                (InfoFundo.subtipo_risco == SubtipoRiscoEnum.rfx) | (InfoFundo.subtipo_risco == None)
            ]),
            'moderado': _query_soma([
                InfoFundo.risco == RiscoEnum.moderado
            ]),
            'alto': _query_soma([
                InfoFundo.risco == RiscoEnum.alto
            ]),
        }

    @staticmethod
    def calcular_montante_total(cliente_id: int, session: Session) -> float:
        """
        Calcula o valor total de todas as posições do cliente.

        Retorna:
            float - soma de (cotas * valor_cota) para todas as posições
        """
        return float(
            session.query(
                func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
            ).join(
                InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
            ).filter(
                PosicaoFundo.cliente_id == cliente_id
            ).scalar() or 0.0
        )

    @staticmethod
    def calcular_totais_por_risco_simples(cliente_id: int, session: Session) -> Dict[str, float]:
        """
        Versão simplificada sem separação de subtipo — agrupa apenas por risco principal.
        Usado por distribuicao_capital_service que não precisa da separação DI/RFx.

        Retorna:
            {
                'baixo':    float,
                'moderado': float,
                'alto':     float
            }
        """
        def _query_soma(risco_enum):
            return float(
                session.query(
                    func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
                ).join(
                    InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
                ).filter(
                    PosicaoFundo.cliente_id == cliente_id,
                    InfoFundo.risco == risco_enum
                ).scalar() or 0.0
            )

        return {
            'baixo':    _query_soma(RiscoEnum.baixo),
            'moderado': _query_soma(RiscoEnum.moderado),
            'alto':     _query_soma(RiscoEnum.alto),
        }