# POS System

A comprehensive Point of Sale (POS) system built with Django, designed for restaurants and retail businesses.

## Features

- User-friendly interface with responsive design
- Product management with categories and inventory tracking
- Order processing with various payment methods
- Customer management
- Receipt printing optimized for thermal printers
- Sales reporting and analytics
- Discount management
- Multiple order types (Dine In, Delivery, etc.)
- Table management for restaurants

## Technical Stack

- **Backend**: Django
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Database**: SQLite (can be configured for PostgreSQL, MySQL)
- **Additional Libraries**: jQuery, FontAwesome

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/msa30804/PB2.git
   cd PB2
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```
   python manage.py migrate
   ```

4. Create a superuser:
   ```
   python manage.py createsuperuser
   ```

5. Run the development server:
   ```
   python manage.py runserver
   ```

## Usage

Access the admin interface at `/admin/` and the POS interface at `/pos/`.

## License

This project is proprietary and confidential. 