"""
Serviço de posições - cálculos sobre PosicaoFundo

Responsabilidade única: responder "quanto o cliente tem investido, e em quê?"

Usado por:
- posicao.py (rota) - exibição na tela
- balance_service.py - cálculos de balanceamento
- distribuicao_capital_service.py - simulação de alocação
"""

from app.models.geld_models import (
    PosicaoFundo, InfoFundo, RiscoEnum, SubtipoRiscoEnum, TODAS_CLASSES
)
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict


class PosicaoService:

    @staticmethod
    def calcular_totais_por_classe(
        cliente_id: int, session: Session, excluir_previdencia: bool = False
    ) -> Dict[str, float]:
        """
        Calcula total investido por subclasse de risco usando SQL agregado.

        excluir_previdencia=True → exclui fundos com is_previdencia=True (pool de fundos regulares).
        excluir_previdencia=False → todos os fundos (padrão).

        Retorna dict com todas as 9 classes:
            {
                'baixo_di':      float,  # Risco baixo, subtipo DI
                'baixo_rfx':     float,  # Risco baixo, subtipo RFx ou sem subtipo
                'moderado':      float,
                'alto':          float,
                'ouro':          float,
                'dolar':         float,
                'cripto':        float,
                'internacional': float,
                'fii':           float,
            }
        """

        def _soma(*filtros):
            filtros_base = [
                PosicaoFundo.cliente_id == cliente_id,
            ]
            if excluir_previdencia:
                filtros_base.append(InfoFundo.is_previdencia == False)
            return float(
                session.query(
                    func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
                ).join(
                    InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
                ).filter(
                    *filtros_base,
                    *filtros
                ).scalar() or 0.0
            )

        return {
            'baixo_di': _soma(
                InfoFundo.risco == RiscoEnum.baixo,
                InfoFundo.subtipo_risco == SubtipoRiscoEnum.di
            ),
            'baixo_rfx': _soma(
                InfoFundo.risco == RiscoEnum.baixo,
                (InfoFundo.subtipo_risco == SubtipoRiscoEnum.rfx) | (InfoFundo.subtipo_risco.is_(None))
            ),
            'moderado':      _soma(InfoFundo.risco == RiscoEnum.moderado),
            'alto':          _soma(InfoFundo.risco == RiscoEnum.alto),
            'ouro':          _soma(InfoFundo.risco == RiscoEnum.ouro),
            'dolar':         _soma(InfoFundo.risco == RiscoEnum.dolar),
            'cripto':        _soma(InfoFundo.risco == RiscoEnum.cripto),
            'internacional': _soma(InfoFundo.risco == RiscoEnum.internacional),
            'fii':           _soma(InfoFundo.risco == RiscoEnum.fii),
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
        Versão simplificada sem separação de subtipo — agrupa por risco principal.
        Usado por distribuicao_capital_service que não precisa da separação DI/RFx.

        Retorna todas as classes no nível de risco (baixo sem subdivisão):
            {
                'baixo':         float,
                'moderado':      float,
                'alto':          float,
                'ouro':          float,
                'dolar':         float,
                'cripto':        float,
                'internacional': float,
                'fii':           float,
            }
        """
        def _soma(risco_enum):
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
            'baixo':         _soma(RiscoEnum.baixo),
            'moderado':      _soma(RiscoEnum.moderado),
            'alto':          _soma(RiscoEnum.alto),
            'ouro':          _soma(RiscoEnum.ouro),
            'dolar':         _soma(RiscoEnum.dolar),
            'cripto':        _soma(RiscoEnum.cripto),
            'internacional': _soma(RiscoEnum.internacional),
            'fii':           _soma(RiscoEnum.fii),
        }