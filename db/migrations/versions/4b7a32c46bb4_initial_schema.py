from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '4b7a32c46bb4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system', 'tool', 'error')"))
    op.execute(sa.text("CREATE TYPE grading_status AS ENUM ('suggested', 'graded')"))
    op.execute(sa.text("""
        CREATE TABLE conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL,
            user_id UUID NOT NULL,
            workspace_id UUID,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text("""
        CREATE TABLE messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role message_role NOT NULL,
            content TEXT NOT NULL,
            blocks JSONB,
            tokens_used INT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(sa.text("""
        CREATE TABLE grading_summaries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
            workspace_id UUID NOT NULL,
            assignment_id UUID NOT NULL,
            suggestion_id TEXT NOT NULL,
            status grading_status NOT NULL,
            summary_blocks JSONB NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            invalidated_at TIMESTAMPTZ
        )
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS grading_summaries"))
    op.execute(sa.text("DROP TABLE IF EXISTS messages"))
    op.execute(sa.text("DROP TABLE IF EXISTS conversations"))
    op.execute(sa.text("DROP TYPE IF EXISTS grading_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS message_role"))