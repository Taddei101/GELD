"""subtipo_ativo_ajustes

Revision ID: 67c40962d927
Revises: aaa29da9a4d2
Create Date: 2026-06-27 15:11:25.965246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67c40962d927'
down_revision: Union[str, Sequence[str], None] = 'aaa29da9a4d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('subtipos_ativo') as batch_op:
        batch_op.alter_column('classe_risco', existing_type=sa.VARCHAR(length=13), nullable=False)
        batch_op.drop_column('descricao')

    with op.batch_alter_table('info_fundos') as batch_op:
        batch_op.create_foreign_key('fk_info_fundos_subtipo', 'subtipos_ativo', ['subtipo_ativo_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('info_fundos') as batch_op:
        batch_op.drop_constraint('fk_info_fundos_subtipo', type_='foreignkey')

    with op.batch_alter_table('subtipos_ativo') as batch_op:
        batch_op.add_column(sa.Column('descricao', sa.VARCHAR(), nullable=True))
        batch_op.alter_column('classe_risco', existing_type=sa.VARCHAR(length=13), nullable=True)
