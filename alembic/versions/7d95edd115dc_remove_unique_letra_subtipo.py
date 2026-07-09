"""remove_unique_letra_subtipo

Revision ID: 7d95edd115dc
Revises: 67c40962d927
Create Date: 2026-06-27 15:28:35.203196

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d95edd115dc'
down_revision: Union[str, Sequence[str], None] = '67c40962d927'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('subtipos_ativo', recreate='always') as batch_op:
        pass


def downgrade() -> None:
    pass
