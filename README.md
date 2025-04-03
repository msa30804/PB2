# Point of Sale (POS) System

A comprehensive Point of Sale (POS) System built with Django, designed for retail and restaurant businesses.

## Features

- Product Management
- Category Management
- Discount Management with Unique Discount Codes
- Order Processing
- Receipt Generation
- Inventory Tracking
- User Authentication with Unique Email Validation
- Dashboard with Sales Analytics
- Responsive Design
- Dark Mode Support

## Technology Stack

- Backend: Django 5.0.2
- Frontend: Bootstrap 5, JavaScript
- Database: SQLite (default), easily configurable to PostgreSQL or MySQL
- JavaScript Libraries: jQuery, Chart.js

## Installation

1. Clone the repository:

   ```
   git clone https://github.com/msa30804/ppos.git
   cd ppos
   ```

2. Create and activate a virtual environment:

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

4. Run migrations:

   ```
   python manage.py migrate
   ```

5. Create a superuser:

   ```
   python manage.py createsuperuser
   ```

6. Run the development server:

   ```
   python manage.py runserver
   ```

7. Access the POS system at http://127.0.0.1:8000/

## Recent Updates

- **Dark Mode**: Added complete dark mode support across all interfaces including the payment modal
- **Unique Discount Codes**: Implemented validation to ensure discount codes are unique
- **User Management**: Enhanced user profile management with settings functionalities
- **Email Validation**: Added unique email validation for user registration

## Screenshots

- Dashboard
- POS Interface
- Products Management
- Orders List

## License

This project is licensed under the MIT License - see the LICENSE file for details.
