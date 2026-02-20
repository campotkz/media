-- Полное удаление старой таблицы для обновления структуры
DROP TABLE IF EXISTS team CASCADE;

-- Создание таблицы с полем для Telegram ID
CREATE TABLE team (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE, -- Поле для связи с Telegram
    full_name TEXT NOT NULL,
    username TEXT, -- Username без собачки
    position TEXT, -- Должность
    roles TEXT[] DEFAULT '{}', -- Роли: production, post, task, actor
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Начальные данные (Исправлено: добавлено NULL в последнюю строку)
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
