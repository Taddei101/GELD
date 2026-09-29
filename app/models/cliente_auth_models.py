from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, UniqueConstraint, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from app.config import CLIENTE_DATABASE_URL

ClienteBase = declarative_base()
engine_cliente = create_engine(CLIENTE_DATABASE_URL)
SessionCliente = sessionmaker(bind=engine_cliente)


class ClienteAuth(ClienteBase):
    __tablename__ = 'cliente_auth'

    id = Column(Integer, primary_key=True)
    cliente_geld_id = Column(Integer, nullable=False, unique=True)
    email = Column(String(120), nullable=False, unique=True)
    senha_hash = Column(String(256), nullable=False)
    precisa_trocar_senha = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.now)
    ultimo_login = Column(DateTime)

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def conferir_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

class SnapshotObjetivo(ClienteBase):
    __tablename__ = 'snapshot_objetivo'

    id = Column(Integer, primary_key=True)
    cliente_geld_id = Column(Integer, nullable=False, index=True)
    objetivo_id = Column(Integer, nullable=False)
    nome_objetivo = Column(String, nullable=False)
    data = Column(DateTime, nullable=False)
    valor = Column(Numeric(15, 2), nullable=False)
    valor_alvo = Column(Numeric(15, 2))
    data_alvo = Column(DateTime)

    __table_args__ = (UniqueConstraint('cliente_geld_id', 'objetivo_id', 'data', name='uq_snapshot_cliente_objetivo_data'),)

def init_cliente_db():
    ClienteBase.metadata.create_all(engine_cliente)


def create_cliente_session():
    return SessionCliente()