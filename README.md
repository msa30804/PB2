# AI-Friendly POS Software in Django

A complete Point of Sale (POS) system built with Django, featuring user management, product management, order processing, and reporting.

## Features

- **User Roles & Authentication**
  - Admin and Cashier roles
  - Secure authentication
  - User management (create, edit, delete)

- **Product Management**
  - Category management
  - Product management with pricing, barcode support
  - Inventory tracking

- **Order Management**
  - Create and process orders
  - Apply discounts
  - Multiple payment methods
  - Receipt printing

- **Reporting**
  - Sales history
  - Daily, weekly, and monthly reports
  - Product performance reports
  - Cashier performance reports

- **Settings & Customization**
  - Business information
  - Tax rates
  - Receipt formatting
  - Dark mode toggle

## Database Setup

1. Create a MySQL database using the provided SQL schema:
   ```
   mysql -u root -p < ppos_schema.sql
   ```

2. The schema includes:
   - Initial admin user (username: admin, password: admin123)
   - Sample categories and products
   - Default system settings
   - Database views for reporting

## Django Project Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install required packages:
   ```
   pip install django django-crispy-forms django-rest-framework mysqlclient pillow
   ```

3. Configure database settings in Django:
   Edit `posproject/settings.py` to configure your MySQL database:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'ppos_db',
           'USER': 'your_mysql_username',
           'PASSWORD': 'your_mysql_password',
           'HOST': 'localhost',
           'PORT': '3306',
       }
   }
   ```

4. Run migrations:
   ```
   python manage.py migrate
   ```

5. Start the development server:
   ```
   python manage.py runserver
   ```

6. Access the POS system at http://127.0.0.1:8000/

## Default Login Credentials

- **Admin User**
  - Username: admin
  - Password: admin123

## Recommended Hardware

- Receipt printer (compatible with ESCPOS)
- Barcode scanner (USB/HID compatible)
- Touch screen monitor for better UX

## License

This project is licensed under the MIT License - see the LICENSE file for details. 