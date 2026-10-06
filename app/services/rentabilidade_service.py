from app.services.extract_services import ExtractServices


def cdi_acumulado(datas):
    df = ExtractServices().extracao_bcb(12, datas[0].strftime('%d/%m/%Y'), datas[-1].strftime('%d/%m/%Y'))
    if df.empty:
        return None
    acumulado = []
    for d in datas:
        taxas = df.loc[(df.index >= datas[0]) & (df.index < d), 'valor']
        acumulado.append(round(float((1 + taxas / 100).prod() - 1) * 100, 4))
    return acumulado

def retorno_acumulado(pontos, movimentacoes):
    acumulado = [0.0]
    fator = 1.0
    for (d0, v0), (d1, v1) in zip(pontos, pontos[1:]):
        fluxo = sum(v for d, v in movimentacoes if d0 < d <= d1)
        fator *= (v1 - fluxo) / v0
        acumulado.append(round((fator - 1) * 100, 4))
    return acumulado