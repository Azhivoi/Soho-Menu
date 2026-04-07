-- Migration: Add promo fields to orders table
-- Created: 2026-04-05

-- Add new columns to orders table
ALTER TABLE orders 
    ADD COLUMN IF NOT EXISTS delivery_fee DECIMAL(10, 2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS promo_code VARCHAR(50),
    ADD COLUMN IF NOT EXISTS promo_discount DECIMAL(10, 2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS promo_promotion_id INTEGER;
