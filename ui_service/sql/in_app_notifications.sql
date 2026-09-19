-- in_app_notifications table for stock_tracker.
-- Owner: ui_service (read/write) as ui_db_user.
-- Lives in ui_schema alongside user_auth_data.
--
-- user_id is UUID FK to user_auth_data (same schema, no cross-schema issue).
-- ON DELETE CASCADE ensures notifications are removed with the user account.

SET search_path TO ui_schema;

CREATE TABLE IF NOT EXISTS in_app_notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES user_auth_data (id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Primary access pattern: list unread notifications for a user
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON in_app_notifications (user_id, is_read);
