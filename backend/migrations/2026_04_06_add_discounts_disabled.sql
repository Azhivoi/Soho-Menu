-- Add discounts_disabled column to menu_products table
ALTER TABLE menu_products ADD COLUMN IF NOT EXISTS discounts_disabled BOOLEAN DEFAULT FALSE;
