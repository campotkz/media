-- Drop table if exists to ensure clean schema update
DROP TABLE IF EXISTS team CASCADE;

-- Create team table
CREATE TABLE team (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name TEXT NOT NULL,
    username TEXT, -- Telegram username or ID
    position TEXT, -- e.g., "Motion Designer", "Operator"
    roles TEXT[] DEFAULT '{}', -- array of roles: 'production', 'post', 'task', 'actor'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed initial data
INSERT INTO team (full_name, username, position, roles) VALUES
('MIRA', 'MiraWWLL', 'Монтаж', '{post}'),
('Yuume', 'younjopa', 'Монтаж', '{post}'),
('Iliyas', 'ilirender', 'Motion Designer', '{post}'),
('Кирилл', 'Fufec', 'Оператор', '{production, post}'),
('Alish', '5843540271', 'Бас оператор', '{production, post}'),
('Дарья', '887184918', 'Фотограф', '{production, post}'),
('Roman', 'magnate71k', 'Администратор', '{production}'),
('LENA TANGO', 'lenn_nnia', 'Сценарист', '{task}'),
('Юлия', 'Bird_of_nord', 'Сценарист', '{task}'),
('Кириллович', 'P4rkir', 'Smm менеджер', '{task}'),
('Aru', 'Arumeyyy', 'Дизайнер', '{task}'),
('Yuriu', 'fumchik', 'Дизайнер', '{task}'),
('Evgeniy', 'evoron', 'Руководитель', '{task}'),
('Иван', 'tango_thecreator', 'Директор', '{production, actor}'),
('Sergey', 'sijicbond', 'Продюсер', '{production}');
