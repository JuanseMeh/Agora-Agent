CREATE TABLE class_plans (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    title       VARCHAR(255) NOT NULL,
    prompt      TEXT NOT NULL,
    plan_data   JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_class_plans_user_id ON class_plans(user_id);
CREATE INDEX idx_class_plans_created_at ON class_plans(created_at DESC);
