"""
Order Management System (OMS) - Database Models
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum('admin', 'order_taker'), nullable=False, default='order_taker')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    orders_created = db.relationship('Order', backref='creator', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'


class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone_primary = db.Column(db.String(20), unique=True, nullable=False, index=True)
    phone_secondary = db.Column(db.String(20), nullable=True)
    type = db.Column(db.Enum('wholesale', 'retail'), nullable=False, default='retail')
    discount_percent = db.Column(db.Float, default=0.0)
    contact_update_status = db.Column(
        db.Enum('approved', 'pending_review'), 
        nullable=False, 
        default='approved'
    )
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    
    def __repr__(self):
        return f'<Customer {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    retail_price = db.Column(db.Float, nullable=False)
    pack_sizes = db.Column(db.Text, nullable=False)  # JSON string storing available sizes
    is_active = db.Column(db.Boolean, default=True)
    
    def get_pack_sizes(self):
        """Return pack sizes as a list of floats"""
        if self.pack_sizes:
            return json.loads(self.pack_sizes)
        return []
    
    def set_pack_sizes(self, sizes):
        """Set pack sizes from a list"""
        self.pack_sizes = json.dumps(sizes)
    
    def get_price_for_pack(self, pack_size):
        """Calculate price for a specific pack size based on retail price per kg"""
        try:
            size_float = float(pack_size)
            return round(self.retail_price * size_float, 2)
        except (ValueError, TypeError):
            return self.retail_price
    
    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(
        db.Enum('pending', 'printed', 'delivered'), 
        nullable=False, 
        default='pending'
    )
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    
    def generate_order_number(cls, session):
        """Generate unique order number like ORD-YYYYMMDD-001"""
        today = datetime.utcnow().strftime('%Y%m%d')
        prefix = f'ORD-{today}-'
        
        # Get the highest order number for today
        last_order = session.query(cls).filter(
            cls.order_number.like(f'{prefix}%')
        ).order_by(cls.order_number.desc()).first()
        
        if last_order:
            # Extract the sequence number and increment
            last_seq = int(last_order.order_number.split('-')[-1])
            new_seq = last_seq + 1
        else:
            new_seq = 1
        
        return f'{prefix}{new_seq:03d}'
    
    def __repr__(self):
        return f'<Order {self.order_number}>'


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    pack_size_selected = db.Column(db.String(20), nullable=False)  # e.g., '0.5' for 500g
    quantity_packs = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Float, nullable=False)
    
    # Relationships
    product = db.relationship('Product', backref='order_items')
    
    @property
    def total_weight(self):
        """Calculate total weight for this line item"""
        try:
            pack_size = float(self.pack_size_selected)
            return round(pack_size * self.quantity_packs, 2)
        except (ValueError, TypeError):
            return 0.0
    
    @property
    def line_total(self):
        """Calculate line total"""
        return round(self.price_at_purchase * self.quantity_packs, 2)
    
    def __repr__(self):
        return f'<OrderItem {self.product.name} x {self.quantity_packs}>'
