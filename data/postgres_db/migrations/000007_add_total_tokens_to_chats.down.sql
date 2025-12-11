-- Remove total_tokens field from chats table
ALTER TABLE chats DROP COLUMN IF EXISTS total_tokens;
