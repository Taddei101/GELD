from app.config import DATABASE_URL
from sqlalchemy import Enum, Column, Integer, Numeric, String, ForeignKey, DateTime, Float, Boolean, create_engine, Index
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime
import enum


Base = declarative_base()

# ========== CONSTANTES CENTRAIS ==========

TODAS_CLASSES = [
    'baixo_di', 'baixo_rfx', 'moderado', 'alto',
    'ouro', 'dolar', 'cripto', 'internacional', 'fii'
]

CLASSES_DISPLAY = {
    'baixo_di':      'Baixo DI',
    'baixo_rfx':     'Baixo RFx',
    'moderado':      'Moderado',
    'alto':          'Alto',
    'ouro':          'Ouro',
    'dolar':         'Dólar',
    'cripto':        'Cripto',
    'internacional': 'Internacional',
    'fii':           'FII'
}

CLASSES_CORES = {
    'baixo_di':      '#d4edda',
    'baixo_rfx':     '#d4edda',
    'moderado':      '#fff3cd',
    'alto':          '#f8d7da',
    'ouro':          '#fff8e1',
    'dolar':         '#e3f2fd',
    'cripto':        '#f3e5f5',
    'internacional': '#e8eaf6',
    'fii':           '#fce4ec'
}

# ========== ENUMS ==========

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
    ouro = 'ouro'
    dolar = 'dolar'
    cripto = 'cripto'
    internacional = 'internacional'
    fii = 'fii'

class SubtipoRiscoEnum(enum.Enum):
    rfx = 'rfx'
    di = 'di'

class TipoObjetivoEnum(enum.Enum):
    geral = 'geral'
    previdencia = 'previdencia'

class StatusFundoEnum(enum.Enum):
    ativo = 'ativo'
    encerrado = 'encerrado'


# ========== MODELOS ==========
    
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
    ultimo_balanceamento_json = Column(String, nullable=True)
    balanceamento_pendente_json = Column(String, nullable=True)

    objetivos = relationship("Objetivo", back_populates = "cliente", cascade = "all, delete-orphan")
    posicoes_fundo = relationship("PosicaoFundo", back_populates="cliente", cascade="all, delete-orphan")
    


class Objetivo(Base):
    __tablename__ = 'objetivos'

    id = Column(Integer, primary_key = True)
    cliente_id = Column(Integer, ForeignKey('clientes.id'), nullable = False)
    nome_objetivo = Column(String, nullable =False)
    tipo_objetivo = Column(Enum(TipoObjetivoEnum), nullable=False, default=TipoObjetivoEnum.geral)
    valor_final = Column(Numeric(15,2), nullable = False)
    valor_inicial = Column(Numeric(15,2), nullable = False)
    data_inicial = Column(DateTime, nullable = False)
    data_final = Column(DateTime, nullable = False)
    prioridade = Column(Float, nullable=True)


    @property
    def duracao_meses(self):
        data_atual = datetime.now()
        return (self.data_final.year - data_atual.year) * 12 + (self.data_final.month - data_atual.month)
        

    cliente = relationship("Cliente", back_populates = "objetivos")
    distribuicao = relationship("DistribuicaoObjetivo", back_populates="objetivo", uselist=False, cascade="all, delete-orphan")


class DistribuicaoObjetivo(Base):
    """
    Armazena a participação percentual de cada objetivo nas classes de risco.
    Cada coluna perc_* representa a fatia (%) que este objetivo detém daquela classe.
    """
    __tablename__ = 'distribuicao_objetivos'
    
    id = Column(Integer, primary_key=True)
    objetivo_id = Column(Integer, ForeignKey('objetivos.id'), nullable=False, unique=True)
    data_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Classes originais
    perc_baixo_di = Column(Float, default=0, nullable=False)   
    perc_baixo_rfx = Column(Float, default=0, nullable=False)  
    perc_moderado = Column(Float, default=0, nullable=False)   
    perc_alto = Column(Float, default=0, nullable=False)
    
    # Classes de hedge (novas)
    perc_ouro = Column(Float, default=0, nullable=False)
    perc_dolar = Column(Float, default=0, nullable=False)
    perc_cripto = Column(Float, default=0, nullable=False)
    perc_internacional = Column(Float, default=0, nullable=False)
    perc_fii = Column(Float, default=0, nullable=False)
    
    # Relacionamento
    objetivo = relationship("Objetivo", back_populates="distribuicao")
    
    def __repr__(self):
        return f"<DistribuicaoObjetivo(objetivo_id={self.objetivo_id})>"



class SubtipoAtivo(Base):
    __tablename__ = 'subtipos_ativo'

    id = Column(Integer, primary_key=True)
    letra = Column(String(1), nullable=False)
    nome = Column(String, nullable=False)
    percentual_ideal = Column(Float, nullable=False, default=25.0)
    classe_risco = Column(Enum(RiscoEnum), nullable=False)

    fundos = relationship("InfoFundo", back_populates="subtipo_ativo")


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
    subtipo_risco = Column(Enum(SubtipoRiscoEnum), nullable=True)
    is_previdencia = Column(Boolean, default=False, nullable=False)
    status_fundo = Column(Enum(StatusFundoEnum), nullable = False)
    valor_cota = Column(Numeric(15,6), nullable=False)
    data_atualizacao = Column(DateTime, nullable=True)
    subtipo_ativo_id = Column(Integer, ForeignKey('subtipos_ativo.id'), nullable=True)

    posicoes_fundo = relationship("PosicaoFundo", back_populates="info_fundo")
    subtipo_ativo = relationship("SubtipoAtivo", back_populates="fundos")


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
    
    # Classes principais (existentes)
    perc_baixo = Column(Float, nullable=False)
    perc_moderado = Column(Float, nullable=False) 
    perc_alto = Column(Float, nullable=False)
    
    # Subdivisão dentro de baixo (existentes)
    perc_di_dentro_baixo = Column(Float, nullable=False)
    perc_rfx_dentro_baixo = Column(Float, nullable=False)
    
    # Classes de hedge (novas)
    perc_ouro = Column(Float, nullable=False, default=0)
    perc_dolar = Column(Float, nullable=False, default=0)
    perc_cripto = Column(Float, nullable=False, default=0)
    perc_internacional = Column(Float, nullable=False, default=0)
    perc_fii = Column(Float, nullable=False, default=0)
        
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
            print("✓ Matriz de risco já populada")
            return
        
        print("→ Populando matriz de risco inicial...")
        
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
                perc_rfx_dentro_baixo=linha['perc_rfx_dentro_baixo'],
                perc_ouro=linha['perc_ouro'],
                perc_dolar=linha['perc_dolar'],
                perc_cripto=linha['perc_cripto'],
                perc_internacional=linha['perc_internacional'],
                perc_fii=linha['perc_fii']
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
                perc_rfx_dentro_baixo=linha['perc_rfx_dentro_baixo'],
                perc_ouro=linha['perc_ouro'],
                perc_dolar=linha['perc_dolar'],
                perc_cripto=linha['perc_cripto'],
                perc_internacional=linha['perc_internacional'],
                perc_fii=linha['perc_fii']
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

def sincronizar_matriz():
    """
    Sincroniza a tabela matriz_risco com os dados atuais de matriz_data.py.
    Faz UPDATE em todas as linhas existentes — ao contrário de _popular_matriz_inicial(),
    esta função sempre roda e sempre atualiza, mesmo que os dados já existam.
    Chame-a sempre que alterar matriz_data.py para refletir as mudanças no banco.
    """
    from app.models.matriz_data import MATRIZ_GERAL, MATRIZ_PREVIDENCIA, validar_todas_matrizes

    session = create_session()
    try:
        if not validar_todas_matrizes():
            raise Exception("Dados da matriz inválidos — verifique app/models/matriz_data.py")

        mapa = {
            TipoObjetivoEnum.geral:        MATRIZ_GERAL,
            TipoObjetivoEnum.previdencia:  MATRIZ_PREVIDENCIA,
        }

        atualizados = 0
        inseridos   = 0

        for tipo_enum, linhas in mapa.items():
            for linha in linhas:
                registro = session.query(MatrizRisco).filter_by(
                    tipo_objetivo=tipo_enum,
                    duracao_meses=linha['duracao_meses']
                ).first()

                campos = dict(
                    perc_baixo            = linha['perc_baixo'],
                    perc_moderado         = linha['perc_moderado'],
                    perc_alto             = linha['perc_alto'],
                    perc_di_dentro_baixo  = linha['perc_di_dentro_baixo'],
                    perc_rfx_dentro_baixo = linha['perc_rfx_dentro_baixo'],
                    perc_ouro             = linha['perc_ouro'],
                    perc_dolar            = linha['perc_dolar'],
                    perc_cripto           = linha['perc_cripto'],
                    perc_internacional    = linha['perc_internacional'],
                    perc_fii              = linha['perc_fii'],
                )

                if registro:
                    for campo, valor in campos.items():
                        setattr(registro, campo, valor)
                    atualizados += 1
                else:
                    session.add(MatrizRisco(
                        tipo_objetivo=tipo_enum,
                        duracao_meses=linha['duracao_meses'],
                        **campos
                    ))
                    inseridos += 1

        session.commit()
        print(f"✅ Matriz sincronizada! Atualizados: {atualizados}, Inseridos: {inseridos}")

    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao sincronizar matriz: {e}")
        raise e
    finally:
        session.close()


def _popular_subtipos_iniciais():
    session = create_session()
    try:
        if session.query(SubtipoAtivo).first():
            print("✓ Subtipos já populados")
            return
        print("→ Populando subtipos de ativo iniciais...")
        for classe in RiscoEnum:
            for letra, nome in [('A', 'Slot A'), ('B', 'Slot B'), ('C', 'Slot C'), ('D', 'Slot D')]:
                session.add(SubtipoAtivo(letra=letra, nome=nome, percentual_ideal=25.0, classe_risco=classe))
        session.commit()
        print("✅ Subtipos populados!")
    except Exception as e:
        session.rollback()
        print(f"❌ Erro ao popular subtipos: {e}")
        raise e
    finally:
        session.close()


def init_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)

    sincronizar_matriz()       # sempre atualiza a partir de matriz_data.py
    _popular_subtipos_iniciais()
    
    return engine
  
def create_session():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind = engine)
    return Session()