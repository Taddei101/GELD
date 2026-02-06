from app.config import DATABASE_URL
from sqlalchemy import Enum, Column, Integer, Numeric, String, ForeignKey, DateTime,Float, create_engine, Index
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

class SubtipoRiscoEnum(enum.Enum):
    rfx = 'rfx'
    di = 'di'

class TipoObjetivoEnum(enum.Enum):
    geral = 'geral'
    previdencia = 'previdencia'

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
    


class Objetivo(Base):
    __tablename__ = 'objetivos'

    id = Column(Integer, primary_key = True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable = False)
    nome_objetivo = Column(String, nullable =False)
    tipo_objetivo = Column(Enum(TipoObjetivoEnum), nullable=False, default=TipoObjetivoEnum.geral)
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
    distribuicao = relationship("DistribuicaoObjetivo", back_populates="objetivo", uselist=False, cascade="all, delete-orphan")


class DistribuicaoObjetivo(Base):
    """
    Armazena a participação percentual de cada objetivo nas classes de risco
    """
    __tablename__ = 'distribuicao_objetivos'
    
    id = Column(Integer, primary_key=True)
    objetivo_id = Column(Integer, ForeignKey('objetivos.id'), nullable=False, unique=True)
    data_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)
         
    perc_baixo_di = Column(Float, default=0, nullable=False)   
    perc_baixo_rfx = Column(Float, default=0, nullable=False)  
    perc_moderado = Column(Float, default=0, nullable=False)   
    perc_alto = Column(Float, default=0, nullable=False)       
    
    # Relacionamento
    objetivo = relationship("Objetivo", back_populates="distribuicao")
    
    def __repr__(self):
        return f"<DistribuicaoObjetivo(objetivo_id={self.objetivo_id})>"



class InfoFundo(Base):
    """nome_fundo, cnpj, classe_anbima, mov_min, permanencia_min, risco,status_fundo"""

    __tablename__ = 'info_fundos'

    id = Column(Integer, primary_key = True)
    nome_fundo = Column(String, nullable = False)
    cnpj = Column(String, nullable = True)
    classe_anbima = Column(String)
    mov_min = Column(Numeric(15,2))
    permanencia_min = Column(Numeric(15,2))
    risco = Column(Enum(RiscoEnum), nullable = False)
    
    subtipo_risco = Column(Enum(SubtipoRiscoEnum),nullable=True)
    
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
    banco_custodia = Column(String(50), nullable=True)
    saldo_anterior = Column(Numeric(15,2), nullable=True)  
    saldo_bruto = Column(Numeric(15,2), nullable=True)     

    info_fundo = relationship("InfoFundo", back_populates = "posicoes_fundo")
    cliente = relationship("Cliente", back_populates="posicoes_fundo")



class MatrizRisco(Base):
    __tablename__ = 'matriz_risco'
    
    id = Column(Integer, primary_key=True)
    tipo_objetivo = Column(Enum(TipoObjetivoEnum), nullable=False)
    duracao_meses = Column(Integer, nullable=False)
        
    perc_baixo = Column(Float, nullable=False)
    perc_moderado = Column(Float, nullable=False) 
    perc_alto = Column(Float, nullable=False)
        
    perc_di_dentro_baixo = Column(Float, nullable=False)
    perc_rfx_dentro_baixo = Column(Float, nullable=False)
        
    __table_args__ = (
        Index('ix_matriz_tipo_duracao', 'tipo_objetivo', 'duracao_meses', unique=True),
    )



class IndicadoresEconomicos(Base):
    __tablename__ = 'indicadores_economicos'
    
    id = Column(Integer, primary_key=True)
    ipca = Column(Float)
    ipca_mes = Column(Float, default=0)
    data_atualizacao = Column(DateTime, default=datetime.now)


def _popular_matriz_inicial():
    """
    Popula dados iniciais da matriz de risco - chamada automaticamente pelo init_db()
    """
    from app.models.matriz_data import MATRIZ_GERAL, MATRIZ_PREVIDENCIA, validar_todas_matrizes
    
    session = create_session()
    try:
        # Verificar se já tem dados
        existe = session.query(MatrizRisco).first()
        if existe:
            print(" Matriz de risco já populada")
            return
        
        print(" Populando matriz de risco inicial...")
        
        # Validar dados antes de inserir
        if not validar_todas_matrizes():
            raise Exception("Dados da matriz inválidos - verifique app/models/matriz_data.py")
        
        # Inserir dados GERAL
        for linha in MATRIZ_GERAL:
            matriz = MatrizRisco(
                tipo_objetivo=TipoObjetivoEnum.geral,
                duracao_meses=linha['duracao_meses'],
                perc_baixo=linha['perc_baixo'],
                perc_moderado=linha['perc_moderado'],
                perc_alto=linha['perc_alto'],
                perc_di_dentro_baixo=linha['perc_di_dentro_baixo'],
                perc_rfx_dentro_baixo=linha['perc_rfx_dentro_baixo']
            )
            session.add(matriz)
        
        # Inserir dados PREVIDÊNCIA
        for linha in MATRIZ_PREVIDENCIA:
            matriz = MatrizRisco(
                tipo_objetivo=TipoObjetivoEnum.previdencia,
                duracao_meses=linha['duracao_meses'],
                perc_baixo=linha['perc_baixo'],
                perc_moderado=linha['perc_moderado'],
                perc_alto=linha['perc_alto'],
                perc_di_dentro_baixo=linha['perc_di_dentro_baixo'],
                perc_rfx_dentro_baixo=linha['perc_rfx_dentro_baixo']
            )
            session.add(matriz)
        
        session.commit()
        
        # Contar registros inseridos
        total_geral = session.query(MatrizRisco).filter(MatrizRisco.tipo_objetivo == TipoObjetivoEnum.geral).count()
        total_prev = session.query(MatrizRisco).filter(MatrizRisco.tipo_objetivo == TipoObjetivoEnum.previdencia).count()
        
        print(f"✅ Matriz populada! Geral: {total_geral}, Previdência: {total_prev}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao popular matriz: {e}")
        raise e
    finally:
        session.close()

def init_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
        
    _popular_matriz_inicial()
    
    return engine
  
def create_session():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind = engine)
    return Session()