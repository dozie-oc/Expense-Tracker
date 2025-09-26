from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, SelectField, EmailField, DateField
from wtforms.validators import DataRequired, NumberRange, Email, Length
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
import csv
from io import StringIO
import os
import requests
from cachetools import TTLCache
import logging  # Added for debugging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Load configuration from environment variables for render
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///expenses.db')
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['EXCHANGE_RATE_API_KEY'] = os.getenv('EXCHANGE_RATE_API_KEY', 'fallback-api-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///expenses.db")

# app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config['MAIL_SERVER'] = 'smtp.gmail.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USERNAME'] = 'email@gmail.com'  # Replace with your Gmail address
# app.config['MAIL_PASSWORD'] = 'random'  # Replace with your 16-character app-specific-password
# app.config['EXCHANGE_RATE_API_KEY'] = 'apikey'  # Replace with your exchangerate-api.com API key
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
cache = TTLCache(maxsize=100, ttl=604800)  # Cache exchange rates for 7 days

SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'NGN']
BASE_CURRENCY = 'USD'

# WTForms (unchanged)
class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=80)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1)])
    currency = SelectField('Currency', choices=[('USD', 'US Dollar (USD)'), ('EUR', 'Euro (EUR)'), 
                                               ('GBP', 'British Pound (GBP)'), ('NGN', 'Nigerian Naira (NGN)')], 
                          validators=[DataRequired()])

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class ForgotPasswordForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1)])

class AddExpenseForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    category = SelectField('Category', choices=[('Food', 'Food'), ('Transport', 'Transport'), 
                                               ('Entertainment', 'Entertainment'), ('Bills', 'Bills'), 
                                               ('Other', 'Other')], validators=[DataRequired()])
    description = StringField('Description', validators=[Length(max=200)])
    date = DateField('Date', validators=[DataRequired()], default=datetime.utcnow)

class AddIncomeForm(FlaskForm):
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    category = SelectField('Category', choices=[('Salary', 'Salary'), ('Bonus', 'Bonus'), 
                                               ('Freelance', 'Freelance'), ('Gift', 'Gift'), 
                                               ('Other', 'Other')], validators=[DataRequired()])
    description = StringField('Description', validators=[Length(max=200)])
    date = DateField('Date', validators=[DataRequired()], default=datetime.utcnow)

class UpdateCurrencyForm(FlaskForm):
    currency = SelectField('Currency', choices=[('USD', 'US Dollar (USD)'), ('EUR', 'Euro (EUR)'), 
                                               ('GBP', 'British Pound (GBP)'), ('NGN', 'Nigerian Naira (NGN)')], 
                          validators=[DataRequired()])

class PeriodForm(FlaskForm):
    month = SelectField('Month', choices=[
        ('All', 'All'), ('1', 'January'), ('2', 'February'), ('3', 'March'), 
        ('4', 'April'), ('5', 'May'), ('6', 'June'), ('7', 'July'), 
        ('8', 'August'), ('9', 'September'), ('10', 'October'), 
        ('11', 'November'), ('12', 'December')
    ], validators=[DataRequired()])
    year = SelectField('Year', choices=[], validators=[DataRequired()])

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    currency = db.Column(db.String(3), default='USD')

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, nullable=False)

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, nullable=False)

class ExchangeRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_currency = db.Column(db.String(3), nullable=False)
    to_currency = db.Column(db.String(3), nullable=False)
    rate = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper Functions
def refresh_rates():
    try:
        url = f"https://v6.exchangerate-api.com/v6/{app.config['EXCHANGE_RATE_API_KEY']}/latest/{BASE_CURRENCY}"
        logger.debug(f"Fetching all exchange rates from {url}")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data['result'] == 'success':
            now = datetime.utcnow()
            for to_currency in SUPPORTED_CURRENCIES:
                rate = data['conversion_rates'].get(to_currency, 1.0 if to_currency == BASE_CURRENCY else None)
                if rate is not None:
                    new_rate = ExchangeRate(from_currency=BASE_CURRENCY, to_currency=to_currency, rate=rate, timestamp=now)
                    db.session.add(new_rate)
                    cache[f"{BASE_CURRENCY}_{to_currency}"] = rate
            db.session.commit()
            logger.debug("Exchange rates refreshed successfully")
        else:
            logger.error(f"API error: {data.get('error-type', 'Unknown error')}")
    except Exception as e:
        logger.error(f"Error refreshing exchange rates: {str(e)}")

def rates_are_fresh():
    # Check if all supported rates from BASE_CURRENCY are present and not older than 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    for to_currency in SUPPORTED_CURRENCIES:
        latest_rate = ExchangeRate.query.filter_by(from_currency=BASE_CURRENCY, to_currency=to_currency).order_by(ExchangeRate.timestamp.desc()).first()
        if not latest_rate or latest_rate.timestamp < seven_days_ago:
            return False
    return True

def get_exchange_rate(from_currency, to_currency):
    if from_currency == to_currency:
        return 1.00
    
    # Ensure rates are fresh
    if not rates_are_fresh():
        refresh_rates()
    
    # Get rate from BASE to from and BASE to to
    base_to_from = get_base_rate(from_currency)
    base_to_to = get_base_rate(to_currency)
    
    if base_to_from == 0:
        logger.error(f"Invalid base rate for {from_currency}")
        return 1.00  # Fallback
    
    rate = base_to_to / base_to_from
    logger.debug(f"Calculated rate {from_currency} to {to_currency}: {rate}")
    return rate

def get_base_rate(to_currency):
    cache_key = f"{BASE_CURRENCY}_{to_currency}"
    if cache_key in cache:
        logger.debug(f"Using cached base rate for {to_currency}: {cache[cache_key]}")
        return cache[cache_key]
    
    latest_rate = ExchangeRate.query.filter_by(from_currency=BASE_CURRENCY, to_currency=to_currency).order_by(ExchangeRate.timestamp.desc()).first()
    if latest_rate:
        cache[cache_key] = latest_rate.rate
        logger.debug(f"Using DB base rate for {to_currency}: {latest_rate.rate}")
        return latest_rate.rate
    else:
        logger.warning(f"No rate found for {BASE_CURRENCY} to {to_currency}, using 1.0")
        return 1.00 if to_currency == BASE_CURRENCY else 0.0  # Error if not base

def convert_currency(amount, from_currency, to_currency):
    if from_currency == to_currency:
        return amount
    rate = get_exchange_rate(from_currency, to_currency)
    converted_amount = amount * rate
    logger.debug(f"Converting {amount} {from_currency} to {to_currency} with rate {rate}: {converted_amount}")
    return converted_amount

def get_currency_symbol(currency):
    symbols = {'USD': '$', 'EUR': '€', 'GBP': '£', 'NGN': '₦'}
    return symbols.get(currency, '$')

def send_reset_email(user):
    token = serializer.dumps(user.email, salt='password-reset')
    reset_url = url_for('reset_password', token=token, _external=True)
    msg = Message('Password Reset Request', sender=app.config['MAIL_USERNAME'], recipients=[user.email])
    msg.body = f'Click this link to reset your password: {reset_url}\nThis link expires in 30 minutes.'
    mail.send(msg)

def get_year_choices():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    incomes = Income.query.filter_by(user_id=current_user.id).all()
    years = set([e.date.year for e in expenses] + [i.date.year for i in incomes])
    now = datetime.utcnow() + timedelta(hours=1)
    years.add(now.year)
    return [(str(y), str(y)) for y in sorted(years)]

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        currency = form.currency.data
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists!')
            return redirect(url_for('register'))
        user = User(username=username, email=email, password_hash=generate_password_hash(password), 
                    currency=currency)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password!')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
            flash('Password reset email sent! Check your inbox.')
        else:
            flash('Email not found!')
        return redirect(url_for('login'))
    return render_template('forgot_password.html', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset', max_age=1800)
    except:
        flash('The reset link is invalid or has expired.')
        return redirect(url_for('forgot_password'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()
        user.password_hash = generate_password_hash(form.password.data)
        db.session.commit()
        flash('Password reset successfully! Please log in.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form, token=token)

@app.route('/dashboard')
@login_required
def dashboard():
    now = datetime.utcnow() + timedelta(hours=1)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    
    expenses = Expense.query.filter_by(user_id=current_user.id).filter(
        Expense.date >= month_start, Expense.date < next_month).order_by(Expense.date.desc()).all()
    incomes = Income.query.filter_by(user_id=current_user.id).filter(
        Income.date >= month_start, Income.date < next_month).order_by(Income.date.desc()).all()
    
    currency = current_user.currency
    symbol = get_currency_symbol(currency)
    
    total_spent = sum(expense.amount for expense in expenses if expense.currency == currency)
    total_income = sum(income.amount for income in incomes if income.currency == currency)
    balance = total_income - total_spent
    
    transactions = [(expense, expense.amount, 'Expense') for expense in expenses if expense.currency == currency] + \
                   [(income, income.amount, 'Income') for income in incomes if income.currency == currency]
    transactions = sorted(transactions, key=lambda x: x[0].date, reverse=True)
    
    currency_form = UpdateCurrencyForm(currency=currency)
    return render_template(
        'dashboard.html',
        transactions=transactions,
        total_spent=total_spent,
        balance=balance,
        currency_symbol=symbol,
        total_income=total_income,
        currency_form=currency_form,
        month=now.strftime('%B %Y')
    )

@app.route('/update_currency', methods=['POST'])
@login_required
def update_currency():
    form = UpdateCurrencyForm()
    if form.validate_on_submit():
        old_currency = current_user.currency
        new_currency = form.currency.data
        logger.debug(f"Updating currency from {old_currency} to {new_currency} for user {current_user.id}")
        if old_currency != new_currency:
            try:
                # Convert existing expenses
                expenses = Expense.query.filter_by(user_id=current_user.id, currency=old_currency).all()
                logger.debug(f"Found {len(expenses)} expenses to convert")
                for expense in expenses:
                    new_amount = convert_currency(expense.amount, old_currency, new_currency)
                    logger.debug(f"Converting expense {expense.id}: {expense.amount} {old_currency} to {new_amount} {new_currency}")
                    expense.amount = new_amount
                    expense.currency = new_currency
                # Convert existing incomes
                incomes = Income.query.filter_by(user_id=current_user.id, currency=old_currency).all()
                logger.debug(f"Found {len(incomes)} incomes to convert")
                for income in incomes:
                    new_amount = convert_currency(income.amount, old_currency, new_currency)
                    logger.debug(f"Converting income {income.id}: {income.amount} {old_currency} to {new_amount} {new_currency}")
                    income.amount = new_amount
                    income.currency = new_currency
                # Update user's currency
                current_user.currency = new_currency
                db.session.commit()
                flash(f'Currency updated to {new_currency}. All transactions converted.')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating currency: {str(e)}")
                flash(f'Error updating currency: {str(e)}', 'error')
        else:
            flash('Currency unchanged.')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {field}: {error}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    form = AddExpenseForm()
    if form.validate_on_submit():
        amount = form.amount.data
        category = form.category.data
        description = form.description.data
        date = form.date.data
        expense = Expense(
            user_id=current_user.id,
            amount=amount,
            currency=current_user.currency,
            category=category,
            description=description,
            date=date
        )
        db.session.add(expense)
        db.session.commit()
        flash('Expense added successfully!')
        return redirect(url_for('dashboard'))
    return render_template('add_expense.html', form=form, currency_symbol=get_currency_symbol(current_user.currency))

@app.route('/add_income', methods=['GET', 'POST'])
@login_required
def add_income():
    form = AddIncomeForm()
    if form.validate_on_submit():
        amount = form.amount.data
        category = form.category.data
        description = form.description.data
        date = form.date.data
        income = Income(
            user_id=current_user.id,
            amount=amount,
            currency=current_user.currency,
            category=category,
            description=description,
            date=date
        )
        db.session.add(income)
        db.session.commit()
        flash('Income added successfully!')
        return redirect(url_for('dashboard'))
    return render_template('add_income.html', form=form, currency_symbol=get_currency_symbol(current_user.currency))

@app.route('/financial_report', methods=['GET', 'POST'])
@login_required
def financial_report():
    form = PeriodForm()
    now = datetime.utcnow() + timedelta(hours=1)
    form.year.choices = get_year_choices()
    form.month.data = str(now.month)
    form.year.data = str(now.year)
    
    month = str(now.month)
    year = str(now.year)
    if form.validate_on_submit():
        month = form.month.data
        year = form.year.data
    
    year = int(year)
    if month == 'All':
        start_date = datetime(year, 1, 1)
        end_date = datetime(year + 1, 1, 1)
        period_display = f"Year: {year}"
    else:
        month = int(month)
        start_date = datetime(year, month, 1)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
        period_display = start_date.strftime('%B %Y')
    
    currency = current_user.currency
    symbol = get_currency_symbol(currency)
    
    expenses = Expense.query.filter_by(user_id=current_user.id).filter(
        Expense.date >= start_date, Expense.date < end_date, Expense.currency == currency).order_by(Expense.date.desc()).all()
    incomes = Income.query.filter_by(user_id=current_user.id).filter(
        Income.date >= start_date, Income.date < end_date, Income.currency == currency).order_by(Income.date.desc()).all()
    
    converted_expenses = [(e, e.amount) for e in expenses]
    converted_incomes = [(i, i.amount) for i in incomes]
    
    # Expense chart data
    expense_chart_data = db.session.query(Expense.category, db.func.sum(Expense.amount)).filter_by(
        user_id=current_user.id).filter(
        Expense.date >= start_date, Expense.date < end_date, Expense.currency == currency).group_by(Expense.category).all()
    expense_chart_labels = [cat[0] for cat in expense_chart_data]
    expense_chart_values = [float(cat[1]) for cat in expense_chart_data]
    
    # Income chart data
    income_chart_data = db.session.query(Income.category, db.func.sum(Income.amount)).filter_by(
        user_id=current_user.id).filter(
        Income.date >= start_date, Income.date < end_date, Income.currency == currency).group_by(Income.category).all()
    income_chart_labels = [cat[0] for cat in income_chart_data]
    income_chart_values = [float(cat[1]) for cat in income_chart_data]
    
    if not expenses and not incomes:
        flash('No transactions found for the selected period.', 'warning')
    
    return render_template(
        'financial_report.html',
        form=form,
        expenses=converted_expenses,
        incomes=converted_incomes,
        expense_chart_labels=expense_chart_labels,
        expense_chart_values=expense_chart_values,
        income_chart_labels=income_chart_labels,
        income_chart_values=income_chart_values,
        period=period_display,
        currency_symbol=symbol,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=(end_date - timedelta(days=1)).strftime('%Y-%m-%d')
    )


@app.route('/delete_expense/<int:id>')
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id == current_user.id:
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted!')
    return redirect(url_for('dashboard'))

@app.route('/delete_income/<int:id>')
@login_required
def delete_income(id):
    income = Income.query.get_or_404(id)
    if income.user_id == current_user.id:
        db.session.delete(income)
        db.session.commit()
        flash('Income deleted!')
    return redirect(url_for('dashboard'))

@app.route('/export_expenses')
@login_required
def export_expenses():
    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    incomes = Income.query.filter_by(user_id=current_user.id).all()
    currency = current_user.currency
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Type', 'Amount', 'Currency', 'Category', 'Description', 'Date'])
    for expense in expenses:
        writer.writerow([expense.id, 'Expense', expense.amount, expense.currency, expense.category, expense.description, expense.date.strftime('%Y-%m-%d')])
    for income in incomes:
        writer.writerow([income.id, 'Income', income.amount, income.currency, income.category, income.description, income.date.strftime('%Y-%m-%d')])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=transactions_{currency}.csv'}
    )

if __name__ == '__main__':
    app.run(debug=True)
