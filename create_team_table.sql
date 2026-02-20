-- Drop table if exists to ensure clean schema update
DROP TABLE IF EXISTS team CASCADE;

-- Create team table with telegram_id
CREATE TABLE team (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE, -- Bigint for Telegram IDs
    full_name TEXT NOT NULL,
    username TEXT, -- Telegram username
    position TEXT, -- e.g., "Motion Designer", "Operator"
    roles TEXT[] DEFAULT '{}', -- array of roles: 'production', 'post', 'task', 'actor'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed initial data (IDs are placeholders if unknown, but username/name will match)
INSERT INTO team (full_name, username, position, roles, telegram_id) VALUES
('MIRA', 'MiraWWLL', 'Монтаж', '{post}', NULL),
('Yuume', 'younjopa', 'Монтаж', '{post}', NULL),
('Iliyas', 'ilirender', 'Motion Designer', '{post}', NULL),
('Кирилл', 'Fufec', 'Оператор', '{production, post}', NULL),
('Alish', '5843540271', 'Бас оператор', '{production, post}', 5843540271),
('Дарья', '887184918', 'Фотограф', '{production, post}', 887184918),
('Roman', 'magnate71k', 'Администратор', '{production}', NULL),
('LENA TANGO', 'lenn_nnia', 'Сценарист', '{task}', NULL),
('Юлия', 'Bird_of_nord', 'Сценарист', '{task}', NULL),
('Кириллович', 'P4rkir', 'Smm менеджер', '{task}', NULL),
('Aru', 'Arumeyyy', 'Дизайнер', '{task}', NULL),
('Yuriu', 'fumchik', 'Дизайнер', '{task}', NULL),
('Evgeniy', 'evoron', 'Руководитель', '{task}', NULL),
('Иван', 'tango_thecreator', 'Директор', '{production, actor}', NULL),
('Sergey', 'sijicbond', 'Продюсер', '{production}', NULL);
