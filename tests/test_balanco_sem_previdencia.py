"""
Regressão: tabela "Sem Previdência" para um cliente sem nenhum ativo/objetivo
alocado em previdência deve ser idêntica à tabela "Operações a Executar no
Advisor" — a previdência não deveria mudar nada no resultado.

Bug original: "Sem Previdência" somava só gap_individual bruto de cada
objetivo não-previdência, ignorando distribuicao_aporte (o que a cascata de
rebalanceamento já move entre objetivos). Com 2+ objetivos não-previdência
e cascata ativa entre eles, a tabela mostrava o gap bruto de rebalanceamento
interno em vez do valor líquido real — dezenas de milhares de reais de
diferença para o mesmo cliente, no mesmo cálculo.

Reproduz o cenário relatado: cliente com 3 objetivos (2 gerais + 1
previdência), fatias no estado pós "Pipeline Rápida" (100% no objetivo
prioritário, demais em zero), sem nenhuma posição em fundo is_previdencia,
sem aporte novo.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.geld_models import (
    Base, Cliente, Objetivo, DistribuicaoObjetivo, InfoFundo, PosicaoFundo,
    MatrizRisco, IndicadoresEconomicos,
    BancoEnum, StatusEnum, RiscoEnum, SubtipoRiscoEnum, TipoObjetivoEnum,
    StatusFundoEnum, TODAS_CLASSES,
)
from app.services.balance_service import BalanceamentoService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _add_matriz(db, tipo, duracao_meses, perc_baixo, perc_moderado, perc_alto,
                 perc_di_dentro_baixo=100.0, perc_rfx_dentro_baixo=0.0,
                 perc_ouro=0.0, perc_dolar=0.0, perc_cripto=0.0,
                 perc_internacional=0.0, perc_fii=0.0):
    db.add(MatrizRisco(
        tipo_objetivo=tipo, duracao_meses=duracao_meses,
        perc_baixo=perc_baixo, perc_moderado=perc_moderado, perc_alto=perc_alto,
        perc_di_dentro_baixo=perc_di_dentro_baixo, perc_rfx_dentro_baixo=perc_rfx_dentro_baixo,
        perc_ouro=perc_ouro, perc_dolar=perc_dolar, perc_cripto=perc_cripto,
        perc_internacional=perc_internacional, perc_fii=perc_fii,
    ))


def _add_fundo(db, nome, risco, valor_cota, subtipo_risco=None, is_previdencia=False):
    fundo = InfoFundo(
        nome_fundo=nome, risco=risco, subtipo_risco=subtipo_risco,
        is_previdencia=is_previdencia, status_fundo=StatusFundoEnum.ativo,
        valor_cota=valor_cota,
    )
    db.add(fundo)
    db.flush()
    return fundo


def _add_posicao(db, cliente, fundo, cotas):
    db.add(PosicaoFundo(
        cliente_id=cliente.id, fundo_id=fundo.id, cotas=cotas,
        data_atualizacao=datetime.now(),
    ))


def _cliente_sem_previdencia(db):
    """Cliente com 3 objetivos (2 gerais, 1 previdência), fatias no estado
    pós Pipeline Rápida, e nenhum fundo classificado como previdência."""
    cliente = Cliente(
        nome="Cliente Teste", nascimento=datetime(1990, 1, 1), cpf="00000000000",
        email="teste@teste.com", telefone="0000000000",
        banco=BancoEnum.BTG, status=StatusEnum.ativo,
    )
    db.add(cliente)
    db.flush()

    hoje = datetime.now()
    obj_a = Objetivo(
        cliente_id=cliente.id, nome_objetivo="Viagem", tipo_objetivo=TipoObjetivoEnum.geral,
        valor_final=20000, valor_inicial=0,
        data_inicial=hoje - timedelta(days=365), data_final=hoje + timedelta(days=150),
        prioridade=None,
    )
    obj_b = Objetivo(
        cliente_id=cliente.id, nome_objetivo="Estúdio", tipo_objetivo=TipoObjetivoEnum.geral,
        valor_final=200000, valor_inicial=0,
        data_inicial=hoje - timedelta(days=365), data_final=hoje + timedelta(days=30 * 59),
        prioridade=None,
    )
    obj_prev = Objetivo(
        cliente_id=cliente.id, nome_objetivo="Previdência", tipo_objetivo=TipoObjetivoEnum.previdencia,
        valor_final=3500000, valor_inicial=0,
        data_inicial=hoje - timedelta(days=365), data_final=hoje + timedelta(days=30 * 131),
        prioridade=None,
    )
    db.add_all([obj_a, obj_b, obj_prev])
    db.flush()

    # Pipeline Rápida: 100% no objetivo prioritário (Viagem, primeiro por
    # data_final), demais objetivos sem DistribuicaoObjetivo (tratados como
    # zero por calcular_valores_atuais_objetivos).
    dist_a = DistribuicaoObjetivo(objetivo_id=obj_a.id)
    for c in TODAS_CLASSES:
        setattr(dist_a, f'perc_{c}', 100.0)
    db.add(dist_a)

    # Fundos regulares (nenhum is_previdencia=True) cobrindo baixo/moderado/alto
    f_di = _add_fundo(db, "Fundo DI", RiscoEnum.baixo, 1.5, subtipo_risco=SubtipoRiscoEnum.di)
    f_rfx = _add_fundo(db, "Fundo RFx", RiscoEnum.baixo, 1.7, subtipo_risco=SubtipoRiscoEnum.rfx)
    f_mod = _add_fundo(db, "Fundo Moderado", RiscoEnum.moderado, 2.0)
    f_alto = _add_fundo(db, "Fundo Alto", RiscoEnum.alto, 2.5)
    db.flush()

    _add_posicao(db, cliente, f_di, cotas=6000)
    _add_posicao(db, cliente, f_rfx, cotas=10000)
    _add_posicao(db, cliente, f_mod, cotas=4000)
    _add_posicao(db, cliente, f_alto, cotas=1500)

    db.add(IndicadoresEconomicos(ipca=4.5, ipca_mes=0.3, data_atualizacao=hoje))

    # Matrizes: geral (12 e 60 meses) e previdência (132 meses), cobrindo os
    # prazos arredondados dos 3 objetivos.
    _add_matriz(db, TipoObjetivoEnum.geral, 12, perc_baixo=85.0, perc_moderado=13.5, perc_alto=1.5)
    _add_matriz(db, TipoObjetivoEnum.geral, 60, perc_baixo=59.0, perc_moderado=25.42, perc_alto=15.58,
                perc_di_dentro_baixo=5.0, perc_rfx_dentro_baixo=95.0)
    _add_matriz(db, TipoObjetivoEnum.previdencia, 132, perc_baixo=25.6, perc_moderado=15.36, perc_alto=23.04,
                perc_di_dentro_baixo=10.0, perc_rfx_dentro_baixo=90.0,
                perc_ouro=4.5, perc_dolar=4.5, perc_cripto=2.0, perc_internacional=10.0, perc_fii=15.0)

    db.commit()
    return cliente


def _operacoes_sem_prev(resultado, todas_classes):
    """Fórmula corrigida usada em balanco.py / resultado.html."""
    operacoes = {}
    for classe in todas_classes:
        valor = sum(
            obj['distribuicao_aporte'].get(classe, 0.0) + obj['gap_individual'].get(classe, 0.0)
            for obj in resultado.get('resultados_por_objetivo', [])
            if obj.get('tipo_objetivo') != 'previdencia'
        )
        if valor > 100:
            operacoes[classe] = {'tipo': 'COMPRAR', 'valor': round(valor, 2)}
        elif valor < -100:
            operacoes[classe] = {'tipo': 'VENDER', 'valor': round(abs(valor), 2)}
    return operacoes


def _operacoes_sem_prev_bug_original(resultado, todas_classes):
    """Fórmula com o bug (só gap_individual, sem distribuicao_aporte) —
    mantida aqui só para provar que o teste pega a regressão."""
    operacoes = {}
    for classe in todas_classes:
        valor = sum(
            obj['gap_individual'].get(classe, 0.0)
            for obj in resultado.get('resultados_por_objetivo', [])
            if obj.get('tipo_objetivo') != 'previdencia'
        )
        if valor > 100:
            operacoes[classe] = {'tipo': 'COMPRAR', 'valor': round(valor, 2)}
        elif valor < -100:
            operacoes[classe] = {'tipo': 'VENDER', 'valor': round(abs(valor), 2)}
    return operacoes


def test_sem_previdencia_igual_advisor_quando_cliente_nao_tem_previdencia(db):
    cliente = _cliente_sem_previdencia(db)
    todas_classes = TODAS_CLASSES

    objetivos = db.query(Objetivo).filter_by(cliente_id=cliente.id).all()
    aportes = [{'objetivo_id': o.id, 'valor_aporte': 0.0} for o in objetivos]

    resultado = BalanceamentoService.executar_cascata_e_rebalancear(cliente.id, aportes, db)

    # Pré-condição do cenário: previdência não recebe nada da cascata.
    obj_prev = next(o for o in resultado['resultados_por_objetivo'] if o['tipo_objetivo'] == 'previdencia')
    assert obj_prev['novos_valores']['total'] == pytest.approx(0.0, abs=0.01)
    assert all(abs(v) < 0.01 for v in obj_prev['gap_individual'].values())

    advisor = {c: v for c, v in resultado['operacoes_liquidas'].items() if v['tipo'] != 'NEUTRO'}
    sem_prev = _operacoes_sem_prev(resultado, todas_classes)

    assert sem_prev.keys() == advisor.keys()
    for classe in advisor:
        assert sem_prev[classe]['tipo'] == advisor[classe]['tipo']
        assert sem_prev[classe]['valor'] == pytest.approx(advisor[classe]['valor'], abs=0.01)


def test_formula_com_bug_diverge_do_advisor_no_mesmo_cenario(db):
    """Prova que o teste acima realmente cobre a regressão: a fórmula antiga
    (sem distribuicao_aporte) produz um valor muito diferente do Advisor
    quando há cascata entre objetivos não-previdência."""
    cliente = _cliente_sem_previdencia(db)
    todas_classes = TODAS_CLASSES

    objetivos = db.query(Objetivo).filter_by(cliente_id=cliente.id).all()
    aportes = [{'objetivo_id': o.id, 'valor_aporte': 0.0} for o in objetivos]

    resultado = BalanceamentoService.executar_cascata_e_rebalancear(cliente.id, aportes, db)
    assert resultado['tem_cascata'], "cenário precisa ter cascata ativa para expor o bug"

    advisor = resultado['operacoes_liquidas']
    sem_prev_bug = _operacoes_sem_prev_bug_original(resultado, todas_classes)

    diverge = any(
        classe not in sem_prev_bug
        or abs(sem_prev_bug[classe]['valor'] - advisor[classe]['valor']) > 100
        for classe in advisor if advisor[classe]['tipo'] != 'NEUTRO'
    )
    assert diverge, "fórmula com bug deveria divergir do Advisor neste cenário"


def test_sem_previdencia_diverge_quando_cliente_tem_previdencia(db):
    """Contraprova: quando a previdência de fato recebe capital (via fatia
    manual), Sem Previdência DEVE divergir do Advisor — não pode virar
    sempre-igual por acidente da correção."""
    cliente = _cliente_sem_previdencia(db)
    todas_classes = TODAS_CLASSES

    objetivos = db.query(Objetivo).filter_by(cliente_id=cliente.id).all()
    obj_a = next(o for o in objetivos if o.nome_objetivo == "Viagem")
    obj_prev = next(o for o in objetivos if o.tipo_objetivo == TipoObjetivoEnum.previdencia)

    db.query(DistribuicaoObjetivo).filter(
        DistribuicaoObjetivo.objetivo_id.in_([o.id for o in objetivos])
    ).delete(synchronize_session=False)
    db.flush()

    dist_a = DistribuicaoObjetivo(objetivo_id=obj_a.id)
    dist_prev = DistribuicaoObjetivo(objetivo_id=obj_prev.id)
    for c in TODAS_CLASSES:
        setattr(dist_a, f'perc_{c}', 70.0)
        setattr(dist_prev, f'perc_{c}', 30.0)
    db.add_all([dist_a, dist_prev])
    db.commit()

    aportes = [{'objetivo_id': o.id, 'valor_aporte': 0.0} for o in objetivos]
    resultado = BalanceamentoService.executar_cascata_e_rebalancear(cliente.id, aportes, db)

    advisor = {c: v for c, v in resultado['operacoes_liquidas'].items() if v['tipo'] != 'NEUTRO'}
    sem_prev = _operacoes_sem_prev(resultado, todas_classes)

    assert sem_prev != advisor
