-- Миграция для добавления parent_id в product_categories
-- Поддержка иерархических категорий (материнские/дочерние)

DO $$
BEGIN
    -- Добавляем parent_id если его нет
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='product_categories' AND column_name='parent_id') THEN
        ALTER TABLE product_categories ADD COLUMN parent_id INTEGER REFERENCES product_categories(id);
    END IF;
END $$;

-- Индекс для быстрого поиска дочерних категорий
CREATE INDEX IF NOT EXISTS idx_product_categories_parent ON product_categories(parent_id);
