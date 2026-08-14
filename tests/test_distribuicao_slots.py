"""
Regressão: divisão do alvo de compra/venda entre slots (A/B/C/D) dentro de
uma classe de risco.

Regra nova: o alvo final da classe (posição atual + delta do balanceamento)
é dividido em PARTES IGUAIS entre os slots que têm algum fundo cadastrado —
o objetivo é priorizar comprar nos slots zerados/defasados até nivelá-los
com os demais, em vez de manter a proporção fixa de percentual_ideal
(default 25% cada, que ignorava o saldo atual de cada slot).

Slots sem nenhum fundo cadastrado no sistema ficam fora da divisão — não
faz sentido instruir o gestor a comprar num slot onde não existe fundo
disponível para executar a operação.

Cobre os dois pontos que fazem esse cálculo: slot_service.py (usado pela
tela "Ver por Slots" em resultado.html / area_cliente.html) e
asset_distribution_service.py (distribuir_por_ativo).
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.geld_models import (
    Base, Cliente, InfoFundo, PosicaoFundo, SubtipoAtivo,
    BancoEnum, StatusEnum, RiscoEnum, StatusFundoEnum,
)
from app.services.slot_service import _linhas_com_slot
from app.services.asset_distribution_service import _distribuir_por_slots


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _add_cliente(db, cpf="00000000000", email="teste@teste.com"):
    cliente = Cliente(
        nome="Cliente Teste", nascimento=datetime(1990, 1, 1), cpf=cpf,
        email=email, telefone="0000000000",
        banco=BancoEnum.BTG, status=StatusEnum.ativo,
    )
    db.add(cliente)
    db.flush()
    return cliente


def _add_slots(db, letras, classe_risco=RiscoEnum.moderado, percentual_ideal=25.0):
    slots = []
    for letra in letras:
        slot = SubtipoAtivo(letra=letra, nome=f"Slot {letra}", percentual_ideal=percentual_ideal, classe_risco=classe_risco)
        db.add(slot)
        db.flush()
        slots.append(slot)
    return slots


def _add_fundo(db, nome, slot, risco=RiscoEnum.moderado, valor_cota=1.0):
    fundo = InfoFundo(
        nome_fundo=nome, risco=risco, is_previdencia=False,
        status_fundo=StatusFundoEnum.ativo, valor_cota=valor_cota,
        subtipo_ativo_id=slot.id,
    )
    db.add(fundo)
    db.flush()
    return fundo


def _add_posicao(db, cliente, fundo, cotas):
    db.add(PosicaoFundo(
        cliente_id=cliente.id, fundo_id=fundo.id, cotas=cotas,
        data_atualizacao=datetime.now(),
    ))
    db.flush()


# ---------- slot_service._linhas_com_slot ----------

def test_slot_zerado_recebe_prioridade_ate_nivelar(db):
    """A=1000, B=C=D=0, delta_classe=3000 (alvo total=4000) -> A não compra
    nada (já está no alvo de 1000), B/C/D compram 1000 cada."""
    cliente = _add_cliente(db)
    slots = _add_slots(db, ["A", "B", "C", "D"])
    fundos = [_add_fundo(db, f"Fundo {s.letra}", s) for s in slots]
    _add_posicao(db, cliente, fundos[0], cotas=1000)  # slot A: R$1000
    db.commit()

    linhas = _linhas_com_slot(cliente.id, "moderado", 3000.0, db)

    assert [l["delta"] for l in linhas] == [0.0, 1000.0, 1000.0, 1000.0]
    assert [l["alvo"] for l in linhas] == [1000.0, 1000.0, 1000.0, 1000.0]
    assert sum(l["delta"] for l in linhas) == pytest.approx(3000.0)


def test_slot_com_saldo_alto_pode_vender_mesmo_com_classe_comprando(db):
    """A=3000, B=C=D=0, delta_classe=1000 (alvo total=4000) -> alvo por slot
    é 1000; A precisa vender 2000 para nivelar, mesmo a classe estando líquida
    em compra no total."""
    cliente = _add_cliente(db)
    slots = _add_slots(db, ["A", "B", "C", "D"])
    fundos = [_add_fundo(db, f"Fundo {s.letra}", s) for s in slots]
    _add_posicao(db, cliente, fundos[0], cotas=3000)
    db.commit()

    linhas = _linhas_com_slot(cliente.id, "moderado", 1000.0, db)

    assert linhas[0]["delta"] == pytest.approx(-2000.0)
    assert linhas[1]["delta"] == pytest.approx(1000.0)
    assert linhas[2]["delta"] == pytest.approx(1000.0)
    assert linhas[3]["delta"] == pytest.approx(1000.0)


def test_slot_sem_fundo_cadastrado_fica_fora_da_divisao(db):
    """A, B, C têm fundo; D não tem nenhum fundo cadastrado no sistema.
    O alvo total deve ser dividido só entre A, B, C — D fica com delta 0."""
    cliente = _add_cliente(db)
    slots = _add_slots(db, ["A", "B", "C", "D"])
    fundos = [_add_fundo(db, f"Fundo {s.letra}", s) for s in slots[:3]]  # D sem fundo
    _add_posicao(db, cliente, fundos[0], cotas=1000)
    db.commit()

    linhas = _linhas_com_slot(cliente.id, "moderado", 3000.0, db)

    letra_d = linhas[3]
    assert letra_d["alvo"] == 0.0
    assert letra_d["delta"] == 0.0
    assert letra_d["fundo_nomes"] == []

    # total_alvo (4000) dividido só entre A, B, C = 1333.33 cada
    assert linhas[0]["alvo"] == pytest.approx(1333.33, abs=0.01)
    assert linhas[1]["alvo"] == pytest.approx(1333.33, abs=0.01)
    assert linhas[2]["alvo"] == pytest.approx(1333.33, abs=0.01)
    # soma dos deltas dos slots com fundo bate com o delta_classe pedido
    # (tolerância maior aqui: soma de 3 arredondamentos de 2 casas decimais)
    assert sum(l["delta"] for l in linhas) == pytest.approx(3000.0, abs=0.02)


def test_todos_slots_zerados_dividem_igualmente(db):
    """Nenhuma posição em nenhum slot: delta_classe=4000 deve dividir 1000
    igual para cada um dos 4 slots com fundo."""
    cliente = _add_cliente(db)
    slots = _add_slots(db, ["A", "B", "C", "D"])
    for s in slots:
        _add_fundo(db, f"Fundo {s.letra}", s)
    db.commit()

    linhas = _linhas_com_slot(cliente.id, "moderado", 4000.0, db)

    assert [l["delta"] for l in linhas] == [1000.0, 1000.0, 1000.0, 1000.0]


# ---------- asset_distribution_service._distribuir_por_slots ----------

def test_distribuir_por_slots_iguala_alvo_final(db):
    cliente = _add_cliente(db)
    slots = _add_slots(db, ["A", "B", "C", "D"])
    fundos = [_add_fundo(db, f"Fundo {s.letra}", s) for s in slots]
    _add_posicao(db, cliente, fundos[0], cotas=1000)
    db.commit()

    entry = _distribuir_por_slots(cliente.id, RiscoEnum.moderado, None, 3000.0, "COMPRAR", db)

    assert entry["total_alvo"] == pytest.approx(4000.0)
    alvo_por_letra = {s["letra"]: s["alvo_R"] for s in entry["slots"]}
    delta_por_letra = {s["letra"]: s["delta_R"] for s in entry["slots"]}
    assert alvo_por_letra == {"A": 1000.0, "B": 1000.0, "C": 1000.0, "D": 1000.0}
    assert delta_por_letra == {"A": 0.0, "B": 1000.0, "C": 1000.0, "D": 1000.0}


def test_distribuir_por_slots_slot_sem_fundo_recebe_alvo_zero(db):
    cliente = _add_cliente(db)
    slots = _add_slots(db, ["A", "B", "C", "D"])
    fundos = [_add_fundo(db, f"Fundo {s.letra}", s) for s in slots[:3]]
    _add_posicao(db, cliente, fundos[0], cotas=1000)
    db.commit()

    entry = _distribuir_por_slots(cliente.id, RiscoEnum.moderado, None, 3000.0, "COMPRAR", db)

    slot_d = next(s for s in entry["slots"] if s["letra"] == "D")
    assert slot_d["alvo_R"] == 0.0
    assert slot_d["delta_R"] == 0.0
    assert slot_d["sem_fundo"] is True
