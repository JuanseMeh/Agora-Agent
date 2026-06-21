from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '5c8d43e9f1a2'
down_revision: Union[str, Sequence[str], None] = '4b7a32c46bb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE class_plans (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL,
            title       VARCHAR(255) NOT NULL,
            prompt      TEXT NOT NULL,
            plan_data   JSONB NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text("CREATE INDEX idx_class_plans_user_id ON class_plans(user_id)"))
    op.execute(sa.text("CREATE INDEX idx_class_plans_created_at ON class_plans(created_at DESC)"))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS class_plans"))
