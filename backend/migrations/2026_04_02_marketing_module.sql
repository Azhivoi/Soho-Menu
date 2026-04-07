-- Миграция для модуля маркетинга
-- Добавляет недостающие поля в таблицу promotions

-- Проверяем и добавляем поля
DO $$
BEGIN
    -- target (all, new, loyal, vip, birthday)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='target') THEN
        ALTER TABLE promotions ADD COLUMN target VARCHAR(50) DEFAULT 'all';
    END IF;

    -- short_description (краткое описание для слайдера)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='short_description') THEN
        ALTER TABLE promotions ADD COLUMN short_description VARCHAR(200);
    END IF;

    -- start_time и end_time как строки
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='start_time') THEN
        ALTER TABLE promotions ADD COLUMN start_time VARCHAR(10);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='end_time') THEN
        ALTER TABLE promotions ADD COLUMN end_time VARCHAR(10);
    END IF;

    -- is_featured (важная акция)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='is_featured') THEN
        ALTER TABLE promotions ADD COLUMN is_featured BOOLEAN DEFAULT FALSE;
    END IF;

    -- usage_count, usage_limit, per_customer_limit
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='usage_count') THEN
        ALTER TABLE promotions ADD COLUMN usage_count INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='usage_limit') THEN
        ALTER TABLE promotions ADD COLUMN usage_limit INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='per_customer_limit') THEN
        ALTER TABLE promotions ADD COLUMN per_customer_limit INTEGER DEFAULT 0;
    END IF;

    -- first_order_only
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='first_order_only') THEN
        ALTER TABLE promotions ADD COLUMN first_order_only BOOLEAN DEFAULT FALSE;
    END IF;

    -- pickup_enabled, courier_enabled, inside_enabled
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='pickup_enabled') THEN
        ALTER TABLE promotions ADD COLUMN pickup_enabled BOOLEAN DEFAULT TRUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='courier_enabled') THEN
        ALTER TABLE promotions ADD COLUMN courier_enabled BOOLEAN DEFAULT TRUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='inside_enabled') THEN
        ALTER TABLE promotions ADD COLUMN inside_enabled BOOLEAN DEFAULT TRUE;
    END IF;

    -- delivery_zones, restaurants (JSONB)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='delivery_zones') THEN
        ALTER TABLE promotions ADD COLUMN delivery_zones JSONB DEFAULT '[]'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='restaurants') THEN
        ALTER TABLE promotions ADD COLUMN restaurants JSONB DEFAULT '[]'::jsonb;
    END IF;

    -- cross_off, discount_addition_off
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='cross_off') THEN
        ALTER TABLE promotions ADD COLUMN cross_off BOOLEAN DEFAULT TRUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='discount_addition_off') THEN
        ALTER TABLE promotions ADD COLUMN discount_addition_off BOOLEAN DEFAULT FALSE;
    END IF;

    -- auth_required
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='promotions' AND column_name='auth_required') THEN
        ALTER TABLE promotions ADD COLUMN auth_required BOOLEAN DEFAULT FALSE;
    END IF;

END $$;

-- Индексы
CREATE INDEX IF NOT EXISTS idx_promotions_code ON promotions(code);
CREATE INDEX IF NOT EXISTS idx_promotions_status ON promotions(status);
CREATE INDEX IF NOT EXISTS idx_promotions_type ON promotions(type);

-- Проверяем существование таблицы order_items и добавляем поле discount если нужно
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='order_items' AND column_name='discount') THEN
        ALTER TABLE order_items ADD COLUMN discount DECIMAL(10, 2) DEFAULT 0;
    END IF;
END $$;

-- Создаем директорию для загрузок если нужно
-- (выполняется вручную на сервере)
-- mkdir -p /opt/soho/uploads/promotions