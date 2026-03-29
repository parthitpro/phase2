# Order Management System (OMS)

A complete, production-ready Order Management System for wholesale/retail Khakhra business.

## Technology Stack

- **Backend**: Python 3.9+, Flask, Flask-Login, Flask-WTF, SQLAlchemy
- **Database**: MySQL 8.0+ (UTF-8 encoding)
- **Frontend**: HTML5, CSS3 (Bootstrap 5), JavaScript, Chart.js
- **Data Processing**: Pandas, OpenPyXL
- **Security**: Password hashing (Werkzeug), Role-based Access Control (RBAC)

## Project Structure

```
oms/
├── app.py                 # Main Flask application
├── models.py              # Database models (SQLAlchemy)
├── utils.py               # Contact cleaning utility
├── backup_db.py           # Database backup script
├── static/
│   ├── css/
│   │   └── style.css      # Custom styles
│   └── js/
│       └── main.js        # JavaScript utilities
├── templates/
│   ├── base.html          # Base template
│   ├── login.html         # Login page
│   ├── dashboard.html     # Dashboard with KPIs
│   ├── order_form.html    # Dynamic order entry
│   ├── order_view.html    # Order details view
│   ├── print_order.html   # Delivery slip print view
│   ├── products.html      # Product management
│   ├── product_form.html  # Add/Edit product
│   ├── upload_contacts.html # Contact import
│   ├── review_contacts.html # Contact review
│   ├── reports.html       # Reports & export
│   ├── 404.html           # Error page
│   └── 500.html           # Error page
├── tests/
│   └── test_oms.py        # Unit tests
└── backups/               # Backup storage directory
```

## Installation

### Prerequisites

- Python 3.9+
- MySQL 8.0+
- pip

### Setup Steps

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install flask flask-sqlalchemy flask-login flask-wtf pymysql pandas openpyxl werkzeug
   ```

3. **Set environment variables** (optional - defaults provided):
   ```bash
   export DATABASE_URL="mysql+pymysql://root:password@localhost/oms_db"
   export SECRET_KEY="your-secret-key-change-in-production"
   ```
   
   > **Note**: If you don't set DATABASE_URL, the app will use `mysql+pymysql://root:password@localhost/oms_db` by default. Make sure your MySQL root password matches, or update the URL accordingly.

4. **Run the application**:
   ```bash
   python app.py
   ```
   
   > The app will automatically:
   > - Create the database if it doesn't exist
   > - Create all tables
   > - Seed the admin user and initial products
   
5. **Access the application**:
   - URL: http://localhost:5000
   - Default admin: `admin@oms.com` / `admin123`

## Features

### Authentication & Authorization
- Secure login with password hashing
- Role-based access control (Admin, Order Taker)
- Admin-only features: Product management, Contact review, Reports

### Customer Management
- Google Contacts CSV import with robust cleaning
- Phone number standardization (+91XXXXXXXXXX)
- Duplicate detection and merge
- Name conflict review system
- Wholesale/Retail customer types with automatic discount

### Order Management
- Dynamic order entry with AJAX customer search
- Pack-size based pricing (250g, 500g, 1kg)
- Automatic wholesale discount (15% default)
- Live total calculation
- Unique order number generation (ORD-YYYYMMDD-001)

### Product Management
- Add/Edit products with multiple pack sizes
- Price per kg configuration
- Active/Inactive status

### Reports & Export
- Date range filtering
- Excel export with Pandas/OpenPyXL
- Detailed order breakdown

### Printing
- Professional delivery slip format
- Print-optimized CSS
- Mark as printed functionality

### Data Backup
- Automated daily backups via mysqldump
- Compressed backup files
- Cleanup of old backups

## Contact Cleaning Logic

The system handles messy Google Contacts data by:

1. **Filtering out**:
   - Entries with only phone numbers (no names)
   - Address entries (Road, Street, Lane, etc.)
   - Service numbers (Bank, Hospital, Emergency)
   - Import notes and labels

2. **Standardizing**:
   - All phones to +91XXXXXXXXXX format
   - Merging duplicate contacts
   - Flagging name conflicts for review

## API Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/login` | GET, POST | User login | No |
| `/logout` | GET | User logout | Yes |
| `/dashboard` | GET | Dashboard with KPIs | Yes |
| `/search_customer/<fragment>` | GET | AJAX customer search | Yes |
| `/get_products` | GET | Get all products | Yes |
| `/order` | GET, POST | Create new order | Yes |
| `/order/<id>` | GET | View order details | Yes |
| `/print_order/<id>` | GET | Print delivery slip | Yes |
| `/upload_contacts` | GET, POST | Import contacts | Admin |
| `/review_contacts` | GET | Review pending contacts | Admin |
| `/products` | GET | Manage products | Admin |
| `/reports` | GET | Reports page | Yes |
| `/reports/export` | POST | Export to Excel | Yes |

## Running Tests

```bash
python tests/test_oms.py
```

## Deployment (Production)

### Using Gunicorn + Nginx

1. **Install Gunicorn**:
   ```bash
   pip install gunicorn
   ```

2. **Create systemd service** (`/etc/systemd/system/oms.service`):
   ```ini
   [Unit]
   Description=OMS Gunicorn instance
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/path/to/oms
   Environment="PATH=/path/to/venv/bin"
   ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app

   [Install]
   WantedBy=multi-user.target
   ```

3. **Setup Cron job for daily backups**:
   ```bash
   crontab -e
   # Add: 0 2 * * * cd /path/to/oms && /path/to/venv/bin/python backup_db.py
   ```

4. **Configure Nginx** as reverse proxy to port 8000

## Security Considerations

- Change default admin password immediately
- Use strong SECRET_KEY in production
- Enable HTTPS in production
- Regular database backups
- Keep dependencies updated

## License

Proprietary - For internal business use only.
