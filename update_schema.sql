-- Field: "Оценка работы вашего отдела продаж" (Process Step)
alter table public.client_feedback 
add column if not exists sales_process_rating text;

-- Field: "Качество рекламы/таргета" (Content Step)
alter table public.client_feedback 
add column if not exists ad_quality_score int;

-- Field: "Качество контента/визуала" (Content Step)
alter table public.client_feedback 
add column if not exists content_quality_score int;

-- Field: "Работа менеджера Campot" (Service Step)
alter table public.client_feedback 
add column if not exists manager_quality_score int;

-- Field: "Общее впечатление" (Service Step)
alter table public.client_feedback 
add column if not exists agency_impression_score int;

-- Note: We will reuse 'response_speed' for "Как быстро ВЫ отвечаете clients?", 
-- but just change the label in the frontend. No DB change needed for that one 
-- if the data type (string/text) is compatible.
