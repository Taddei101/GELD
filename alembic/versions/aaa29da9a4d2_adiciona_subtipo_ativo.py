"""adiciona_subtipo_ativo

Revision ID: aaa29da9a4d2
Revises: 76a0276a26d2
Create Date: 2026-06-27 14:46:51.698375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aaa29da9a4d2'
down_revision: Union[str, Sequence[str], None] = '76a0276a26d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('subtipos_ativo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('letra', sa.String(length=1), nullable=False),
    sa.Column('nome', sa.String(), nullable=False),
    sa.Column('descricao', sa.String(), nullable=True),
    sa.Column('percentual_ideal', sa.Float(), nullable=False),
    sa.Column('classe_risco', sa.Enum('alto', 'moderado', 'baixo', 'ouro', 'dolar', 'cripto', 'internacional', 'fii', name='riscoenum'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('letra')
    )
    with op.batch_alter_table('info_fundos') as batch_op:
        batch_op.add_column(sa.Column('subtipo_ativo_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_info_fundos_subtipo', 'subtipos_ativo', ['subtipo_ativo_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('info_fundos') as batch_op:
        batch_op.drop_constraint('fk_info_fundos_subtipo', type_='foreignkey')
        batch_op.drop_column('subtipo_ativo_id')
    op.drop_table('subtipos_ativo')
