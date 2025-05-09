# PickBug POS System

A complete Point of Sale (POS) system for retail businesses, built with Django and modern web technologies.

## Features

- **Product Management**: Add, edit, and manage products with categories and inventory tracking
- **Order Processing**: Create and manage orders with real-time receipt generation
- **Customer Management**: Track customer information and purchase history
- **Reporting**: Generate sales reports, inventory reports, and more
- **User Management**: Role-based access control with different user levels
- **Discount Management**: Apply percentage or fixed discounts to orders
- **End Day Processing**: Close out the day with detailed sales summaries
- **Order Reference System**: Unique reference numbers (PB1234) for each order

## Technical Specifications

- Built with Django 5.0+
- REST API for mobile and external integration
- Responsive design that works on all devices
- MySQL database backend

## Installation

1. Clone the repository
   ```bash
   git clone https://github.com/msa30804/PBPOS.git
   cd PBPOS
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the database in settings.py

5. Run migrations
   ```bash
   python manage.py migrate
   ```

6. Create a superuser
   ```bash
   python manage.py createsuperuser
   ```

7. Start the development server
   ```bash
   python manage.py runserver
   ```

## Usage

Access the admin interface at `/admin/` and the POS interface at the root URL (`/`).

## License

Proprietary - All rights reserved
