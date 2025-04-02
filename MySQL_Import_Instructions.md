# MySQL Database Import Instructions

This document provides instructions on how to import the PPOS (Point of Sale System) database into MySQL Workbench.

## SQL Files Provided

We provide a simplified SQL file for database import:

- **simple_ppos_db.sql** - A clean schema with basic tables and minimal sample data

## Prerequisites

- MySQL Server 5.7 or higher installed
- MySQL Workbench installed
- The SQL file downloaded to your computer

## Import Steps

1. **Open MySQL Workbench**

2. **Connect to your MySQL Server**
   - Launch MySQL Workbench and connect to your MySQL server instance
   - Use your existing connection or create a new one with your credentials

3. **Import the Database File**
   - From the top menu, select **Server > Data Import**
   - Choose the **Import from Self-Contained File** option
   - Browse and select the `simple_ppos_db.sql` file
   - In the **Default Schema to be Imported To** field, leave it blank as the script will create the database
   - Click the **Start Import** button

4. **Verify the Import**
   - After the import completes, click on the refresh icon in the Navigator panel
   - You should see a new database named `ppos_db`
   - Expand the database to view tables, views, and other database objects

## Alternative Import Method

If you encounter issues with the MySQL Workbench import functionality, you can try importing via the command line:

```bash
mysql -u root -p < simple_ppos_db.sql
```

Replace `root` with your MySQL username. You will be prompted for your password.

## Troubleshooting Import Issues

If you continue to have issues with the import:

1. Use the command line method instead of MySQL Workbench
2. Check if your MySQL version is compatible (5.7 or higher)
3. Ensure you have proper permissions to create databases
4. Try manually creating the database first:
   ```sql
   CREATE DATABASE ppos_db;
   USE ppos_db;
   ```
   Then import the SQL file with the tables only

## Database Credentials for Django

The Django application is configured to use the following database settings:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'ppos_db',
        'USER': 'root',  # Update with your MySQL username
        'PASSWORD': 'msa123',  # Update with your MySQL password
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
```

You may need to update the `USER` and `PASSWORD` values in the Django settings file (`posproject/settings.py`) to match your MySQL credentials.

## Default Admin User

After importing the database and running migrations, you can log into the POS system with the superuser credentials you created.

## Database Schema

The database includes the following main tables:

- `user_roles` - User role definitions
- `users` - User account information
- `categories` - Product categories
- `products` - Product information
- `orders` - Order header information
- `order_items` - Order line items
- `discounts` - Discount definitions
- `settings` - System settings
- `payment_transactions` - Payment records

For a more detailed understanding of the database structure, refer to the `database_structure.md` file in the project repository.