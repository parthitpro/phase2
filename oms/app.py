"""
Order Management System - Main Application
"""
import os
import re
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import CSRFProtect
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import pandas as pd
import json
from functools import wraps
from sqlalchemy import create_engine, text

from models import db, User, Customer, Product, Order, OrderItem
from utils import process_contact_upload


def ensure_database_exists(db_uri):
    """
    Extract database name from URI and create it if it doesn't exist.
    This allows running 'python app.py' without manual DB setup.
    """
    # Parse the database URI
    # Format: mysql+pymysql://user:pass@host/dbname
    pattern = r'^mysql\+pymysql://([^:]+):([^@]+)@([^/]+)/(.+)$'
    match = re.match(pattern, db_uri)
    
    if not match:
        # If no match, assume DB already exists or using SQLite
        return db_uri
    
    user, password, host, dbname = match.groups()
    
    # Create engine without database to create the database
    base_uri = f'mysql+pymysql://{user}:{password}@{host}'
    engine = create_engine(base_uri)
    
    try:
        with engine.connect() as conn:
            # Check if database exists
            result = conn.execute(text(f"SHOW DATABASES LIKE '{dbname}'"))
            if not result.fetchone():
                # Create database with UTF-8 encoding
                conn.execute(text(
                    f"CREATE DATABASE `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                ))
                print(f"Database '{dbname}' created successfully!")
            else:
                print(f"Database '{dbname}' already exists.")
    except Exception as e:
        print(f"Warning: Could not verify/create database: {e}")
    
    engine.dispose()
    return db_uri


def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', 
        'mysql+pymysql://root:password@localhost/oms_db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
    app.config['BACKUP_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
    
    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['BACKUP_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    csrf = CSRFProtect(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Custom decorator for role-based access control
    def role_required(role):
        def decorator(f):
            @wraps(f)
            @login_required
            def decorated_function(*args, **kwargs):
                if current_user.role != role:
                    flash('Access denied. Admin privileges required.', 'error')
                    return redirect(url_for('dashboard'))
                return f(*args, **kwargs)
            return decorated_function
        return decorator
    
    # Make decorator available to templates
    app.context_processor(lambda: dict(role_required=role_required))
    
    # Routes
    
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            remember = request.form.get('remember', False)
            
            user = User.query.filter_by(email=email).first()
            
            if user and user.check_password(password):
                login_user(user, remember=remember)
                next_page = request.args.get('next')
                return redirect(next_page if next_page else url_for('dashboard'))
            else:
                flash('Invalid email or password', 'error')
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('login'))
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        # KPIs
        today = datetime.utcnow()
        month_start = today.replace(day=1)
        
        total_orders = Order.query.count()
        total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0.0
        active_customers = Order.query.filter(
            Order.order_date >= month_start
        ).distinct(Order.customer_id).count()
        
        # Pending contacts for review (admin only)
        pending_contacts = 0
        if current_user.role == 'admin':
            pending_contacts = Customer.query.filter_by(
                contact_update_status='pending_review'
            ).count()
        
        # Unprinted orders
        unprinted_orders = Order.query.filter_by(status='pending').count()
        
        # Recent orders for chart
        recent_orders = Order.query.filter(
            Order.order_date >= today - timedelta(days=7)
        ).order_by(Order.order_date).all()
        
        chart_data = {}
        for order in recent_orders:
            date_str = order.order_date.strftime('%Y-%m-%d')
            chart_data[date_str] = chart_data.get(date_str, 0) + 1
        
        return render_template(
            'dashboard.html',
            total_orders=total_orders,
            total_revenue=total_revenue,
            active_customers=active_customers,
            pending_contacts=pending_contacts,
            unprinted_orders=unprinted_orders,
            chart_data=json.dumps(chart_data)
        )
    
    @app.route('/search_customer/<fragment>')
    @login_required
    def search_customer(fragment):
        """AJAX endpoint for customer auto-suggest"""
        if len(fragment) < 3:
            return jsonify([])
        
        customers = Customer.query.filter(
            db.or_(
                Customer.name.ilike(f'%{fragment}%'),
                Customer.phone_primary.ilike(f'%{fragment}%')
            )
        ).limit(10).all()
        
        results = [
            {
                'id': c.id,
                'name': c.name,
                'phone': c.phone_primary,
                'type': c.type,
                'discount': c.discount_percent
            }
            for c in customers
        ]
        
        return jsonify(results)
    
    @app.route('/get_products')
    @login_required
    def get_products():
        """Return all active products with pack sizes"""
        products = Product.query.filter_by(is_active=True).all()
        
        results = [
            {
                'id': p.id,
                'name': p.name,
                'retail_price': p.retail_price,
                'pack_sizes': p.get_pack_sizes()
            }
            for p in products
        ]
        
        return jsonify(results)
    
    @app.route('/order', methods=['GET', 'POST'])
    @login_required
    def create_order():
        if request.method == 'POST':
            try:
                customer_id = request.form.get('customer_id')
                items_data = request.form.get('items')
                
                if not customer_id or not items_data:
                    flash('Invalid order data', 'error')
                    return redirect(url_for('create_order'))
                
                items = json.loads(items_data)
                
                if not items:
                    flash('No items in order', 'error')
                    return redirect(url_for('create_order'))
                
                # Get customer
                customer = Customer.query.get(customer_id)
                if not customer:
                    flash('Customer not found', 'error')
                    return redirect(url_for('create_order'))
                
                # Generate order number
                order_number = Order.generate_order_number(db.session)
                
                # Create order
                order = Order(
                    order_number=order_number,
                    customer_id=customer_id,
                    total_amount=0.0,
                    created_by=current_user.id
                )
                db.session.add(order)
                db.session.flush()  # Get order ID
                
                total = 0.0
                for item in items:
                    product = Product.query.get(item['product_id'])
                    if not product:
                        continue
                    
                    pack_size = item['pack_size']
                    quantity = int(item['quantity'])
                    
                    if quantity <= 0:
                        flash('Quantities must be positive', 'error')
                        db.session.rollback()
                        return redirect(url_for('create_order'))
                    
                    # Calculate price based on pack size
                    price = product.get_price_for_pack(pack_size)
                    
                    # Apply wholesale discount if applicable
                    if customer.type == 'wholesale':
                        discount = customer.discount_percent or 15.0
                        price = price * (1 - discount / 100)
                    
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=product.id,
                        pack_size_selected=pack_size,
                        quantity_packs=quantity,
                        price_at_purchase=round(price, 2)
                    )
                    db.session.add(order_item)
                    total += price * quantity
                
                order.total_amount = round(total, 2)
                db.session.commit()
                
                flash(f'Order {order_number} created successfully!', 'success')
                return redirect(url_for('print_order', order_id=order.id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating order: {str(e)}', 'error')
                return redirect(url_for('create_order'))
        
        return render_template('order_form.html')
    
    @app.route('/order/<int:order_id>')
    @login_required
    def view_order(order_id):
        order = Order.query.get_or_404(order_id)
        return render_template('order_view.html', order=order)
    
    @app.route('/print_order/<int:order_id>')
    @login_required
    def print_order(order_id):
        order = Order.query.get_or_404(order_id)
        return render_template('print_order.html', order=order)
    
    @app.route('/order/<int:order_id>/mark_printed', methods=['POST'])
    @login_required
    def mark_order_printed(order_id):
        order = Order.query.get_or_404(order_id)
        order.status = 'printed'
        db.session.commit()
        flash('Order marked as printed', 'success')
        return redirect(url_for('view_order', order_id=order.id))
    
    @app.route('/upload_contacts', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def upload_contacts():
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file uploaded', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            
            if file and file.filename.endswith('.csv'):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                try:
                    # Process the CSV
                    from models import Customer
                    results = process_contact_upload(filepath, db.session, Customer)
                    
                    flash(
                        f"Import complete! New: {results['new']}, "
                        f"Pending Review: {results['updates_pending']}, "
                        f"Unchanged: {results['unchanged']}",
                        'success'
                    )
                except Exception as e:
                    flash(f'Error processing file: {str(e)}', 'error')
                finally:
                    # Clean up uploaded file
                    if os.path.exists(filepath):
                        os.remove(filepath)
                
                return redirect(url_for('review_contacts'))
            else:
                flash('Please upload a CSV file', 'error')
        
        return render_template('upload_contacts.html')
    
    @app.route('/review_contacts')
    @login_required
    @role_required('admin')
    def review_contacts():
        pending = Customer.query.filter_by(
            contact_update_status='pending_review'
        ).all()
        return render_template('review_contacts.html', contacts=pending)
    
    @app.route('/contact/<int:contact_id>/approve', methods=['POST'])
    @login_required
    @role_required('admin')
    def approve_contact(contact_id):
        contact = Customer.query.get_or_404(contact_id)
        
        # Get the new name from the form (could be passed as hidden field)
        new_name = request.form.get('new_name', contact.name)
        contact.name = new_name.title()
        contact.contact_update_status = 'approved'
        contact.last_updated = datetime.utcnow()
        db.session.commit()
        
        flash('Contact approved and updated', 'success')
        return redirect(url_for('review_contacts'))
    
    @app.route('/contact/<int:contact_id>/reject', methods=['POST'])
    @login_required
    @role_required('admin')
    def reject_contact(contact_id):
        contact = Customer.query.get_or_404(contact_id)
        contact.contact_update_status = 'approved'  # Keep old name
        contact.last_updated = datetime.utcnow()
        db.session.commit()
        
        flash('Contact update rejected, kept original name', 'success')
        return redirect(url_for('review_contacts'))
    
    @app.route('/products')
    @login_required
    @role_required('admin')
    def manage_products():
        products = Product.query.all()
        return render_template('products.html', products=products)
    
    @app.route('/product/add', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def add_product():
        if request.method == 'POST':
            name = request.form.get('name')
            retail_price = float(request.form.get('retail_price'))
            pack_sizes = request.form.getlist('pack_sizes')
            
            if not name or not retail_price or not pack_sizes:
                flash('All fields are required', 'error')
                return redirect(url_for('add_product'))
            
            # Convert pack sizes to floats
            pack_sizes_float = [float(ps) for ps in pack_sizes]
            
            product = Product(
                name=name,
                retail_price=retail_price,
                is_active=True
            )
            product.set_pack_sizes(pack_sizes_float)
            
            db.session.add(product)
            db.session.commit()
            
            flash('Product added successfully', 'success')
            return redirect(url_for('manage_products'))
        
        return render_template('product_form.html', product=None)
    
    @app.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
    @login_required
    @role_required('admin')
    def edit_product(product_id):
        product = Product.query.get_or_404(product_id)
        
        if request.method == 'POST':
            product.name = request.form.get('name')
            product.retail_price = float(request.form.get('retail_price'))
            pack_sizes = request.form.getlist('pack_sizes')
            product.set_pack_sizes([float(ps) for ps in pack_sizes])
            product.is_active = request.form.get('is_active') == 'on'
            
            db.session.commit()
            
            flash('Product updated successfully', 'success')
            return redirect(url_for('manage_products'))
        
        return render_template('product_form.html', product=product)
    
    @app.route('/reports')
    @login_required
    def reports():
        return render_template('reports.html')
    
    @app.route('/reports/export', methods=['POST'])
    @login_required
    def export_reports():
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        if not start_date or not end_date:
            flash('Please select date range', 'error')
            return redirect(url_for('reports'))
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        
        orders = Order.query.filter(
            Order.order_date >= start,
            Order.order_date < end
        ).all()
        
        # Prepare data for Excel
        data = []
        for order in orders:
            for item in order.items:
                data.append({
                    'Order Number': order.order_number,
                    'Order Date': order.order_date.strftime('%Y-%m-%d'),
                    'Customer': order.customer.name,
                    'Customer Type': order.customer.type,
                    'Product': item.product.name,
                    'Pack Size (kg)': item.pack_size_selected,
                    'Quantity (packs)': item.quantity_packs,
                    'Total Weight (kg)': item.total_weight,
                    'Price per Pack': item.price_at_purchase,
                    'Line Total': item.line_total,
                    'Order Total': order.total_amount,
                    'Status': order.status
                })
        
        df = pd.DataFrame(data)
        
        # Export to Excel
        filename = f'order_report_{start_date}_to_{end_date}.xlsx'
        filepath = os.path.join(app.config['BACKUP_FOLDER'], filename)
        df.to_excel(filepath, index=False, engine='openpyxl')
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
    
    return app


# Seed script to create default admin user
def seed_admin_user(app):
    with app.app_context():
        admin = User.query.filter_by(email='admin@oms.com').first()
        if not admin:
            admin = User(
                email='admin@oms.com',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print('Default admin user created: admin@oms.com / admin123')
        else:
            print('Admin user already exists')


# Seed initial products
def seed_products(app):
    with app.app_context():
        initial_products = [
            ('Jira Khakhra', 340, ['0.25', '0.5', '1.0']),
            ('Pavbhaji Khakhra', 400, ['0.25', '0.5', '1.0']),
            ('Panipuri Khakhra', 400, ['0.25', '0.5', '1.0']),
            ('Methi Khakhra', 360, ['0.25', '0.5', '1.0']),
            ('Plain Khakhra', 320, ['0.25', '0.5', '1.0']),
            ('Masala Khakhra', 340, ['0.25', '0.5', '1.0']),
            ('Thepla', 14, ['1.0']),
            ('Pure Ghee Khakhra', 740, ['0.25', '0.5', '1.0']),
        ]
        
        for name, price, sizes in initial_products:
            existing = Product.query.filter_by(name=name).first()
            if not existing:
                product = Product(
                    name=name,
                    retail_price=price,
                    is_active=True
                )
                product.set_pack_sizes(sizes)
                db.session.add(product)
        
        db.session.commit()
        print('Initial products seeded')


if __name__ == '__main__':
    # Get database URI and ensure database exists
    db_uri = os.environ.get(
        'DATABASE_URL', 
        'mysql+pymysql://root:password@localhost/oms_db'
    )
    
    # Auto-create database if it doesn't exist
    db_uri = ensure_database_exists(db_uri)
    
    # Set the URI for the app to use
    os.environ['DATABASE_URL'] = db_uri
    
    app = create_app()
    
    # Create tables and seed data
    with app.app_context():
        db.create_all()
        seed_admin_user(app)
        seed_products(app)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
