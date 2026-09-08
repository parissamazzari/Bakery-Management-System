-- Bakery Management System - Database Schema
-- Executed automatically by the official postgres image on first container startup
-- (files in /docker-entrypoint-initdb.d/ run once, only against an empty data directory)

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    category VARCHAR(50) NOT NULL,
    in_stock BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending -> processing -> completed / failed
    total_amount NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL
);

-- Seed data so the product listing endpoint has something to show out of the box
INSERT INTO products (name, description, price, category, in_stock) VALUES
    ('Sourdough Loaf', 'Classic slow-fermented sourdough bread', 6.50, 'bread', TRUE),
    ('Croissant', 'Buttery, flaky French pastry', 3.25, 'pastry', TRUE),
    ('Chocolate Chip Cookie', 'Soft-baked cookie with dark chocolate chips', 2.00, 'cookies', TRUE),
    ('Blueberry Muffin', 'Moist muffin loaded with blueberries', 3.00, 'pastry', TRUE),
    ('Baguette', 'Traditional French baguette', 4.00, 'bread', TRUE),
    ('Cinnamon Roll', 'Iced cinnamon roll with cream cheese frosting', 3.75, 'pastry', TRUE),
    ('Red Velvet Cupcake', 'Cupcake with cream cheese frosting', 3.50, 'cake', TRUE),
    ('Whole Wheat Bread', 'Healthy whole wheat sandwich loaf', 5.50, 'bread', FALSE)
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
