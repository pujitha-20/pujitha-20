from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ------------------ USER ------------------
class User(db.Model):
    __tablename__ = 'user'  # 👈 Required for correct ForeignKey references
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    transactions = db.relationship('Transaction', backref='user', lazy=True)
    budgets = db.relationship('Budget', backref='user', lazy=True)
    daily_limits = db.relationship('DailyLimit', backref='user', lazy=True)
    streak = db.relationship('Streak', backref='user', uselist=False)

# ------------------ TRANSACTION ------------------
class Transaction(db.Model):
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(10), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    note = db.Column(db.Text)
    tag = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receipt = db.Column(db.String(200))  # 🧾 Optional: file name for receipt

# ------------------ BUDGET ------------------
class Budget(db.Model):
    __tablename__ = 'budget'
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), nullable=False)  # Format: YYYY-MM
    limit = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ------------------ DAILY LIMIT ------------------
class DailyLimit(db.Model):
    __tablename__ = 'daily_limit'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    limit = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ------------------ STREAK ------------------
class Streak(db.Model):
    __tablename__ = 'streak'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    last_logged_date = db.Column(db.Date)
    streak_count = db.Column(db.Integer, default=0)
