# Getting Started with PPOS Desktop

This guide will help you set up and package the PPOS desktop application.

## Prerequisites

Before starting, ensure you have the following installed:

1. **Node.js and npm** - Download and install from [nodejs.org](https://nodejs.org/)
2. **Python 3.8+** - Download and install from [python.org](https://www.python.org/downloads/)
3. **MySQL** - Download and install from [mysql.com](https://www.mysql.com/downloads/)

## Setup Steps

### 1. Clone the Repository

If you haven't already, clone the repository and navigate to the project directory:

```bash
git clone https://github.com/msa30804/ppos.git
cd ppos
```

### 2. Set Up the Python Environment

Create and activate a virtual environment:

**Windows:**
```bat
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Install Python dependencies:
```bash
pip install -r requirements.txt
```

### 3. Set Up the Database

Create a MySQL database named `ppos_db`:

```sql
CREATE DATABASE ppos_db;
```

Then import the database schema:

```bash
mysql -u root -p ppos_db < simple_ppos_db.sql
```

### 4. Configure the Application

Update the database credentials in `posproject/settings.py` if necessary:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'ppos_db',
        'USER': 'root',  # Update with your MySQL username
        'PASSWORD': 'msa123',  # Update with your MySQL password
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### 5. Set Up the Electron Application

Navigate to the electron app directory and install dependencies:

```bash
cd electron_app
npm install
```

## Running the Application in Development Mode

To run the application in development mode:

```bash
npm run dev
```

This will:
1. Start the Django development server
2. Launch the Electron application that loads the Django interface

## Packaging the Application

### For Windows:

```bash
npm run package-win
```

The packaged application will be available in the `dist` folder.

### For macOS:

```bash
npm run package-mac
```

### For Linux:

```bash
npm run package-linux
```

## Customization

### Application Icon

Replace the placeholder icon in the `electron_app/assets` directory:
- `icon.png` - For Linux (512x512 pixels recommended)
- `icon.ico` - For Windows
- `icon.icns` - For macOS

### Application Name

To change the application name, edit the `productName` field in `electron_app/package.json`.

## Troubleshooting

### Database Connection Issues

If you encounter database connection issues:
1. Verify MySQL is running and accessible
2. Check the database credentials in `posproject/settings.py`
3. The application will fall back to SQLite if MySQL is unavailable

### Packaging Errors

If you encounter packaging errors:
1. Ensure all dependencies are installed: `npm install`
2. Check for any errors in the console output
3. Make sure you have sufficient disk space

## Next Steps

- Add custom receipt printing capabilities
- Integrate with hardware like barcode scanners or cash drawers
- Add offline mode enhancements

For more detailed information, refer to the project documentation. 