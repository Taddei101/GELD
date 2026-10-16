from app.services.balance_service import BalanceamentoService


def taxa_mensal(ipca_anual):
    taxa_anual = (1 + ipca_anual / 100) * (1 + BalanceamentoService.TAXA_REAL_ANUAL / 100) - 1
    return (1 + taxa_anual) ** (1/12) - 1


def valor_estimado(valor_atual, ipca_anual, meses):
    if meses <= 0:
        return valor_atual
    return valor_atual * (1 + taxa_mensal(ipca_anual)) ** meses


def aporte_mensal(vp_ideal, valor_atual, ipca_anual, meses):
    if meses <= 0:
        return None
    falta = vp_ideal - valor_atual
    if falta <= 0:
        return 0
    i = taxa_mensal(ipca_anual)
    return falta * i / (1 - (1 + i) ** -meses)