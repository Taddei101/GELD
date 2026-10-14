from datetime import datetime
from app.services.extract_services import ExtractServices
from app.models.cliente_auth_models import create_cliente_session, SnapshotObjetivo, Movimentacao


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

def valores_em_reais(pontos, movimentacoes, cdi):
    investido = [round(sum(v for d, v in movimentacoes if d <= pontos[0][0]), 2)]
    cdi_reais = [pontos[0][1]]
    for i in range(1, len(pontos)):
        d0, d1 = pontos[i - 1][0], pontos[i][0]
        fluxo = sum(v for d, v in movimentacoes if d0 < d <= d1)
        investido.append(round(investido[-1] + fluxo, 2))
        if cdi:
            fator = (1 + cdi[i] / 100) / (1 + cdi[i - 1] / 100)
            cdi_reais.append(round(cdi_reais[-1] * fator + fluxo, 2))
    return investido, (cdi_reais if cdi else None)

def xirr(fluxos):
    """fluxos: lista de (data, valor). Aporte negativo, saque/valor final positivo."""
    d0 = fluxos[0][0]

    def vpl(taxa):
        return sum(v / (1 + taxa) ** ((d - d0).days / 365) for d, v in fluxos)

    baixo, alto = -0.99, 10.0
    if vpl(baixo) * vpl(alto) > 0:
        return None
    for _ in range(200):
        meio = (baixo + alto) / 2
        if vpl(baixo) * vpl(meio) <= 0:
            alto = meio
        else:
            baixo = meio
    return meio

def fluxos_xirr(pontos, movimentacoes):
    inicio, fim = pontos[0][0], pontos[-1][0]
    fluxos = [(inicio, -pontos[0][1])]
    fluxos += [(d, -v) for d, v in movimentacoes if inicio < d <= fim]
    fluxos.append((fim, pontos[-1][1]))
    return sorted(fluxos)

def serie_mensal(cliente_id):
    db = create_cliente_session()
    try:
        linhas = db.query(SnapshotObjetivo).filter_by(cliente_geld_id=cliente_id).order_by(SnapshotObjetivo.data).all()
        movs = db.query(Movimentacao).filter_by(cliente_geld_id=cliente_id).order_by(Movimentacao.data).all()

        totais = {}
        for s in linhas:
            dia = datetime(s.data.year, s.data.month, s.data.day)
            totais[dia] = totais.get(dia, 0.0) + float(s.valor)
        mensal = {}
        for dia, valor in totais.items():
            mensal[datetime(dia.year, dia.month, 1)] = valor

        pontos = [(d, round(v, 2)) for d, v in mensal.items()]
        fluxos = [(m.data, float(m.valor)) for m in movs]
        return pontos, fluxos
    finally:
        db.close()