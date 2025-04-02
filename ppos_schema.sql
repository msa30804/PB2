-- POS System Database Schema

-- Drop database if it exists
DROP DATABASE IF EXISTS ppos_db;

-- Create database
CREATE DATABASE ppos_db;
USE ppos_db;

-- User roles table
CREATE TABLE user_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert default roles
INSERT INTO user_roles (name, description) VALUES
    ('Admin', 'Full access to all features'),
    ('Cashier', 'Can only process sales');

-- Users table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20),
    role_id INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES user_roles(id)
);

-- Insert default admin user (password: 'admin123' - in production use hashed password)
INSERT INTO users (username, password, first_name, last_name, email, role_id) VALUES
    ('admin', 'pbkdf2_sha256$260000$4BtcqHoESzHQjHGxiPxVLP$TzD0hICbGKcyZgSqRVPy3J4Fm9WZ77ya3vWQgKvj2V0=', 'System', 'Admin', 'admin@ppos.com', 1);

-- Categories table
CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert sample categories
INSERT INTO categories (name, description) VALUES
    ('Drinks', 'Beverages and drinks'),
    ('Snacks', 'Quick bites and snacks'),
    ('Meals', 'Full meals and combos');

-- Products table
CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category_id INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    cost_price DECIMAL(10, 2),
    barcode VARCHAR(100),
    sku VARCHAR(50),
    stock_quantity INT DEFAULT 0,
    is_available BOOLEAN DEFAULT TRUE,
    image_url VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Insert sample products
INSERT INTO products (name, category_id, price, cost_price, barcode, stock_quantity, is_available) VALUES
    ('Coca Cola', 1, 2.50, 1.50, '8901234567890', 100, TRUE),
    ('Mineral Water', 1, 1.00, 0.50, '8901234567891', 200, TRUE),
    ('Potato Chips', 2, 1.50, 0.75, '8901234567892', 50, TRUE),
    ('Chicken Burger', 3, 5.99, 3.50, '8901234567893', 20, TRUE),
    ('Pizza Slice', 3, 3.99, 2.25, '8901234567894', 15, TRUE);

-- Orders table
CREATE TABLE orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(50) NOT NULL UNIQUE,
    user_id INT NOT NULL,
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20),
    subtotal DECIMAL(10, 2) NOT NULL,
    tax_amount DECIMAL(10, 2) NOT NULL,
    discount_amount DECIMAL(10, 2) DEFAULT 0,
    total_amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) DEFAULT 'Cash',
    payment_status ENUM('Pending', 'Paid', 'Failed') DEFAULT 'Pending',
    order_status ENUM('New', 'Processing', 'Completed', 'Cancelled') DEFAULT 'New',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Order items table
CREATE TABLE order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_price DECIMAL(10, 2) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Discounts table
CREATE TABLE discounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50),
    type ENUM('Percentage', 'Fixed') NOT NULL,
    value DECIMAL(10, 2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert sample discounts
INSERT INTO discounts (name, code, type, value, is_active) VALUES
    ('10% Off', 'DISC10', 'Percentage', 10.00, TRUE),
    ('5$ Off', 'DISC5', 'Fixed', 5.00, TRUE);

-- System settings table
CREATE TABLE settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT NOT NULL,
    setting_description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insert default settings
INSERT INTO settings (setting_key, setting_value, setting_description) VALUES
    ('business_name', 'POS System', 'Name of the business'),
    ('business_address', '123 Main Street, City', 'Address of the business'),
    ('business_phone', '+1-234-567-8900', 'Phone number of the business'),
    ('tax_rate', '7.5', 'Default tax rate percentage'),
    ('receipt_footer', 'Thank you for your business!', 'Message to display at the bottom of receipts'),
    ('currency_symbol', '$', 'Currency symbol to use'),
    ('dark_mode', 'false', 'Enable/disable dark mode'),
    ('receipt_printer', 'Default Printer', 'Default printer for receipts');

-- Payment transactions table
CREATE TABLE payment_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    transaction_number VARCHAR(100) NOT NULL UNIQUE,
    amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    transaction_status ENUM('Pending', 'Completed', 'Failed') DEFAULT 'Pending',
    transaction_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

-- Audit logs table
CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(255) NOT NULL,
    entity VARCHAR(50) NOT NULL,
    entity_id INT,
    details TEXT,
    ip_address VARCHAR(50),
    user_agent VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes for better performance
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);
CREATE INDEX idx_payment_transactions_order ON payment_transactions(order_id);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);

-- Create views for reporting
-- Daily sales view
CREATE VIEW daily_sales_view AS
SELECT 
    DATE(created_at) AS sale_date,
    COUNT(id) AS number_of_orders,
    SUM(subtotal) AS total_subtotal,
    SUM(tax_amount) AS total_tax,
    SUM(discount_amount) AS total_discount,
    SUM(total_amount) AS total_sales
FROM orders
WHERE payment_status = 'Paid'
GROUP BY DATE(created_at);

-- Product sales view
CREATE VIEW product_sales_view AS
SELECT 
    p.id AS product_id,
    p.name AS product_name,
    c.name AS category_name,
    SUM(oi.quantity) AS total_quantity_sold,
    SUM(oi.total_price) AS total_sales_amount
FROM order_items oi
JOIN products p ON oi.product_id = p.id
JOIN categories c ON p.category_id = c.id
JOIN orders o ON oi.order_id = o.id
WHERE o.payment_status = 'Paid'
GROUP BY p.id, p.name, c.name;

-- User sales performance view
CREATE VIEW user_sales_view AS
SELECT 
    u.id AS user_id,
    CONCAT(u.first_name, ' ', u.last_name) AS cashier_name,
    COUNT(o.id) AS number_of_orders,
    SUM(o.total_amount) AS total_sales_amount
FROM orders o
JOIN users u ON o.user_id = u.id
WHERE o.payment_status = 'Paid'
GROUP BY u.id, cashier_name; 