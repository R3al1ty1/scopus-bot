CREATE TABLE IF NOT EXISTS user_requests (
    chat_id BIGINT PRIMARY KEY NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    username TEXT,
    trial_start TEXT
);
