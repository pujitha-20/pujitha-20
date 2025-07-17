from flask import Flask, render_template, request, redirect, session, url_for, Response, jsonify
from models import db, Transaction, DailyLimit, User, Budget, Streak
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from collections import defaultdict
import os
import csv

app = Flask(__name__)
app.secret_key = "twinklee-secret-key"

# ------------------ DATABASE CONFIG ------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# ------------------ RECEIPT UPLOAD CONFIG ------------------
RECEIPT_FOLDER = os.path.join('static', 'receipts')
os.makedirs(RECEIPT_FOLDER, exist_ok=True)

# ------------------ HOME ------------------
@app.route('/')
def home():
    if 'user_id' not in session:
        return render_template('landing.html')

    user_id = session['user_id']
    username = session['username']
    income = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=user_id, type='income').scalar() or 0
    expense = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=user_id, type='expense').scalar() or 0
    count = Transaction.query.filter_by(user_id=user_id).count()
    streak_data = Streak.query.filter_by(user_id=user_id).first()
    streak_count = streak_data.streak_count if streak_data else 0

    return render_template('home.html', income=income, expense=expense, count=count, username=username, streak=streak_count)

# ------------------ AUTH ------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('register.html', error="Username already exists 😢")

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            today = date.today()
            streak = Streak.query.filter_by(user_id=user.id).first()
            if not streak:
                db.session.add(Streak(user_id=user.id, last_logged_date=today, streak_count=1))
            else:
                if streak.last_logged_date == today:
                    pass
                elif streak.last_logged_date == today - timedelta(days=1):
                    streak.streak_count += 1
                    streak.last_logged_date = today
                else:
                    streak.streak_count = 1
                    streak.last_logged_date = today
            db.session.commit()
            return redirect('/')
        else:
            error = 'Invalid credentials. Try again.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ------------------ TRANSACTIONS ------------------
@app.route('/add', methods=['GET', 'POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        amount = float(request.form['amount'])
        txn_type = request.form['type']
        category = request.form.get('category', '').strip()
        date_val = request.form['date']
        note = request.form.get('note', '').lower()
        tag = request.form.get('tag', '').lower()

        if not category:
            if 'salary' in note or 'salary' in tag:
                category = 'Salary'
            elif 'grocery' in note or 'grocery' in tag:
                category = 'Groceries'
            elif 'fuel' in note or 'fuel' in tag:
                category = 'Transport'
            elif 'rent' in note or 'rent' in tag:
                category = 'Rent'
            elif 'restaurant' in note or 'dining' in note or 'restaurant' in tag:
                category = 'Dining'
            else:
                category = 'Miscellaneous'

        receipt_filename = None
        if 'receipt' in request.files:
            file = request.files['receipt']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(RECEIPT_FOLDER, filename)
                file.save(filepath)
                receipt_filename = filename

        new_txn = Transaction(
            user_id=session['user_id'],
            amount=amount,
            type=txn_type,
            category=category,
            date=date_val,
            note=note,
            tag=tag,
            receipt=receipt_filename
        )
        db.session.add(new_txn)
        db.session.commit()
        return redirect('/transactions')

    return render_template('add.html')

@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect('/login')
    txns = Transaction.query.filter_by(user_id=session['user_id']).order_by(Transaction.date.desc()).all()
    return render_template('view.html', txns=txns)

@app.route("/delete/<int:txn_id>", methods=["POST"])
def delete_transaction(txn_id):
    txn = Transaction.query.get_or_404(txn_id)
    db.session.delete(txn)
    db.session.commit()
    return redirect("/transactions")

# ------------------ CATEGORY SUGGESTIONS ------------------
@app.route('/category_suggestions')
def category_suggestions():
    if 'user_id' not in session:
        return jsonify([])
    q = request.args.get('q', '').lower()
    user_categories = db.session.query(Transaction.category).filter_by(user_id=session['user_id']).distinct()
    user_categories = [cat[0] for cat in user_categories if q in cat[0].lower()]
    common_cats = ['Salary', 'Groceries', 'Rent', 'Transport', 'Dining', 'Miscellaneous']
    common_filtered = [cat for cat in common_cats if q in cat.lower()]
    suggestions = user_categories + [cat for cat in common_filtered if cat not in user_categories]
    return jsonify(suggestions[:8])

# ------------------ SUMMARY ------------------
@app.route('/summary')
def summary():
    if 'user_id' not in session:
        return redirect('/login')
    txns = Transaction.query.filter_by(user_id=session['user_id']).all()
    summary = defaultdict(float)
    for txn in txns:
        summary[txn.category] += txn.amount if txn.type == 'income' else -txn.amount
    return render_template('summary.html', summary=summary)

# ------------------ MONTHLY ------------------
@app.route('/monthly')
def monthly():
    if 'user_id' not in session:
        return redirect('/login')
    selected_month = request.args.get('month') or date.today().strftime('%Y-%m')
    user_id = session['user_id']

    income = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=user_id, type='income').filter(Transaction.date.like(f"{selected_month}%")).scalar() or 0
    expense = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=user_id, type='expense').filter(Transaction.date.like(f"{selected_month}%")).scalar() or 0
    budget = Budget.query.filter_by(user_id=user_id, month=selected_month).first()
    limit = budget.limit if budget else None
    over_budget = limit is not None and expense > limit

    return render_template('monthly.html', month=selected_month, income=income, expense=expense, budget_limit=limit, over_budget=over_budget)

# ------------------ SET BUDGET ------------------
@app.route('/set-budget', methods=['GET', 'POST'])
def set_budget():
    if 'user_id' not in session:
        return redirect('/login')
    message = None
    if request.method == 'POST':
        month = request.form['month']
        limit = float(request.form['limit'])
        user_id = session['user_id']
        budget = Budget.query.filter_by(user_id=user_id, month=month).first()
        if budget:
            budget.limit = limit
        else:
            budget = Budget(user_id=user_id, month=month, limit=limit)
            db.session.add(budget)
        db.session.commit()
        message = "Budget set successfully!"
    return render_template('set_budget.html', message=message)

# ------------------ DAILY LIMIT ------------------
@app.route('/daily')
def daily():
    if 'user_id' not in session:
        return redirect('/login')
    today = date.today()
    user_id = session['user_id']
    limit_entry = DailyLimit.query.filter_by(user_id=user_id, date=today).first()
    limit = limit_entry.limit if limit_entry else 0
    total_spent = db.session.query(db.func.sum(Transaction.amount)).filter_by(user_id=user_id, type='expense').filter_by(date=str(today)).scalar() or 0
    return render_template('daily.html', date=today, total=total_spent, limit=limit, over_limit=total_spent > limit)

# ------------------ CHART ------------------
@app.route('/chart')
def chart():
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    today = date.today()
    month_prefix = today.strftime('%Y-%m')
    txns = Transaction.query.filter_by(user_id=user_id, type='expense').filter(Transaction.date.like(f"{month_prefix}%")).all()

    category_totals = defaultdict(float)
    for txn in txns:
        category_totals[txn.category] += txn.amount

    total = sum(category_totals.values())
    slices = []
    colors = ['#5c6bc0', '#66bb6a', '#ef5350', '#ffa726', '#26a69a', '#8d6e63', '#42a5f5', '#ab47bc']
    for idx, (category, amount) in enumerate(category_totals.items()):
        percent = round((amount / total) * 100, 2) if total > 0 else 0
        slices.append({'category': category, 'percent': percent, 'color': colors[idx % len(colors)]})

    gradient = ', '.join(f"{slice['color']} {sum(s['percent'] for s in slices[:i]):.2f}% {sum(s['percent'] for s in slices[:i+1]):.2f}%" for i, slice in enumerate(slices))
    return render_template('chart.html', slices=slices, gradient=gradient)

# ------------------ PROFILE ------------------
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

# ------------------ RUN ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Available routes:")
        for rule in app.url_map.iter_rules():
            print(rule)
    app.run(debug=True)
