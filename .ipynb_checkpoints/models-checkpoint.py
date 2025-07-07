# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128)) # Store hash, not plain text
    toll_records = db.relationship('TollRecord', backref='user', lazy=True)
    queries = db.relationship('Query', backref='user', lazy=True)

    # Flask-Login requires this method if your primary key isn't named 'id'
    # def get_id(self):
    #    return str(self.id) # Must return a string

    def __repr__(self):
        return f'<User {self.username}>'

class TollRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    entry_lat = db.Column(db.Float)
    entry_lon = db.Column(db.Float)
    entry_address = db.Column(db.String(255))
    entry_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    exit_lat = db.Column(db.Float)
    exit_lon = db.Column(db.Float)
    exit_address = db.Column(db.String(255))
    exit_timestamp = db.Column(db.DateTime)
    distance_km = db.Column(db.Float)
    amount_due = db.Column(db.Float)
    paid = db.Column(db.Boolean, default=False)
    payment_timestamp = db.Column(db.DateTime, nullable=True)
    # Add a flag to know if this record represents an entry event only
    is_entry_only = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<TollRecord {self.id} for User {self.user_id}>'

class Query(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Submitted') # e.g., Submitted, In Progress, Resolved

    def __repr__(self):
        return f'<Query {self.id} from User {self.user_id}>'

# You might add more models, e.g., for Toll Plazas if using polygons