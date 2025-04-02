# POS System Database Structure

## Entity Relationship Diagram (ERD) Description

### Core Entities

1. **users**
   - Primary entity for user authentication and management
   - Related to `user_roles` (Many-to-One): Each user has one role
   - Related to `orders` (One-to-Many): One user can create many orders
   - Related to `audit_logs` (One-to-Many): User actions are tracked in audit logs

2. **user_roles**
   - Stores role definitions (Admin, Cashier)
   - Related to `users` (One-to-Many): One role can be assigned to many users

3. **categories**
   - Stores product categories
   - Related to `products` (One-to-Many): One category can have many products

4. **products**
   - Stores product information
   - Related to `categories` (Many-to-One): Each product belongs to one category
   - Related to `order_items` (One-to-Many): One product can appear in many order items

5. **orders**
   - Stores order header information
   - Related to `users` (Many-to-One): Each order is created by one user
   - Related to `order_items` (One-to-Many): One order can have many items
   - Related to `payment_transactions` (One-to-Many): One order can have multiple payment transactions

6. **order_items**
   - Stores line items for each order
   - Related to `orders` (Many-to-One): Each order item belongs to one order
   - Related to `products` (Many-to-One): Each order item refers to one product

7. **discounts**
   - Stores discount definitions
   - Applied to orders during checkout

8. **settings**
   - Stores system configuration
   - No direct relationships with other entities

9. **payment_transactions**
   - Stores payment information
   - Related to `orders` (Many-to-One): Each payment transaction is for one order

10. **audit_logs**
    - Stores system audit information
    - Related to `users` (Many-to-One): Each log entry may be associated with a user

### Key Relationships

- Users create Orders
- Products belong to Categories
- Orders contain Order Items
- Order Items reference Products
- Orders have Payment Transactions
- Users have Roles

### Database Views

1. **daily_sales_view**
   - Aggregates order data by date

2. **product_sales_view**
   - Aggregates order item data by product

3. **user_sales_view**
   - Aggregates order data by user (cashier)

## Schema Design Features

- **Soft Deletion Pattern**: Using `is_active` flags instead of physical deletion
- **Audit Timestamps**: Using `created_at` and `updated_at` timestamps on all tables
- **Data Integrity**: Foreign key constraints for referential integrity
- **Indexing**: Strategic indexes for optimal query performance
- **Enumerations**: Using ENUM types for status fields
- **Detailed Tracking**: Comprehensive audit logging system 