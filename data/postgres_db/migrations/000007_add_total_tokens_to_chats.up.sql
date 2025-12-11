-- Add total_tokens field to chats table
ALTER TABLE chats ADD COLUMN total_tokens INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN chats.total_tokens IS 'Суммарное количество токенов в чате';
