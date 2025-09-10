from app.config import DATABASE_URL
from sqlalchemy import Enum, Column, Integer, Numeric, String, ForeignKey, DateTime,Float, create_engine
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime
import enum


Base = declarative_base()

class PerfilEnum(enum.Enum):
    arrojado = 'arrojado'
    moderado = 'moderado'
    conservador = 'conservador'

class BancoEnum(enum.Enum):
    BTG = 'BTG'
    XP = 'XP'
    NU = 'NU'

class StatusEnum(enum.Enum):
    ativo = 'ativo'
    inativo = 'inativo'

class RiscoEnum(enum.Enum):
    alto = 'alto'
    moderado = 'moderado'
    baixo = 'baixo'
    fundo_DI='fundo DI'

class StatusFundoEnum(enum.Enum):
    ativo = 'ativo'
    encerrado = 'encerrado'

class TipoOperacaoEnum(enum.Enum):
    resgate = 'resgate'
    aporte = 'aporte'
    
class Cliente(Base):
    __tablename__ = 'clientes'

    id = Column(Integer, primary_key = True)
    nome = Column(String, nullable = False)
    nascimento = Column(DateTime, nullable = False)
    cep = Column(Integer)
    endereco = Column(String)
    escolaridade = Column(String)
    cpf = Column(String(11), nullable = False, unique = True)
    email = Column(String, nullable = False, unique = True)
    telefone = Column(String, nullable = False)
    banco = Column(Enum(BancoEnum), nullable = False)
    status = Column(Enum(StatusEnum), nullable = False)

    objetivos = relationship("Objetivo", back_populates = "cliente", cascade = "all, delete-orphan")
    posicoes_fundo = relationship("PosicaoFundo", back_populates="cliente", cascade="all, delete-orphan")
    transacoes = relationship("Transacao", back_populates="cliente", cascade="all, delete-orphan")


class Objetivo(Base):
    __tablename__ = 'objetivos'

    id = Column(Integer, primary_key = True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable = False)
    nome_objetivo = Column(String, nullable =False)
    valor_final = Column(Numeric(15,2), nullable = False)
    valor_real = Column(Numeric(15,2), nullable = False)
    valor_inicial = Column(Numeric(15,2), nullable = False)
    data_inicial = Column(DateTime, nullable = False)
    data_final = Column(DateTime, nullable = False)
    @property
    def duracao_meses(self):
        data_atual = datetime.now()
        return (self.data_final.year - data_atual.year) * 12 + (self.data_final.month - data_atual.month)
        

    cliente = relationship("Cliente", back_populates = "objetivos")
    


class InfoFundo(Base):
    """nome_fundo, cnpj, classe_anbima, mov_min, permanencia_min, risco,status_fundo"""

    __tablename__ = 'info_fundos'

    id = Column(Integer, primary_key = True)
    nome_fundo = Column(String, nullable = False)
    cnpj = Column(String, nullable = False)
    classe_anbima = Column(String)
    mov_min = Column(Numeric(15,2))
    permanencia_min = Column(Numeric(15,2))
    risco = Column(Enum(RiscoEnum), nullable = False)
    status_fundo = Column(Enum(StatusFundoEnum), nullable = False)
    valor_cota = Column(Numeric(15,6), nullable=False)
    data_atualizacao = Column(DateTime, nullable=True)

    posicoes_fundo = relationship("PosicaoFundo", back_populates="info_fundo")


class PosicaoFundo(Base):
    __tablename__ = 'posicao_fundos'
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer,ForeignKey('clientes.id'),nullable=False)
    fundo_id = Column(Integer,ForeignKey('info_fundos.id'),nullable=False)
    cotas = Column(Numeric(15,6), nullable = False)
    data_atualizacao = Column(DateTime, nullable=False)

    info_fundo = relationship("InfoFundo", back_populates = "posicoes_fundo")
    cliente = relationship("Cliente", back_populates="posicoes_fundo")

class Transacao(Base):
    """num_operacao, data_mov, data_cotizacao,data_liquidacao,tipo_operacao,quantidade_cotas"""
    __tablename__ = 'transacoes'

    #identificacao
    id = Column(Integer, primary_key = True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable = False)
    fundo_id = Column(Integer, ForeignKey('info_fundos.id'), nullable=False)
    num_operacao = Column(String, nullable=True)

    #datas
    data_mov = Column(DateTime, nullable=False)
    data_cotizacao = Column(DateTime, nullable=False)
    data_liquidacao = Column(DateTime, nullable=False)

    #dados financeiros
    tipo_operacao = Column(Enum(TipoOperacaoEnum), nullable=False)
    quantidade_cotas = Column(Numeric(15,6), nullable=False)
    
    cliente = relationship("Cliente", back_populates="transacoes")
    info_fundo = relationship("InfoFundo")

class IndicadoresEconomicos(Base):
    __tablename__ = 'indicadores_economicos'
    
    id = Column(Integer, primary_key=True)
    ipca = Column(Float)
    ipca_mes = Column(Float, default=0)
    data_atualizacao = Column(DateTime, default=datetime.now)

def init_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine
  
def create_session():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind = engine)
    return Session()

