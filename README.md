```markdown
# 📊 Expense Tracker with User Authentication

A **Flask** web application that lets users securely manage their incomes and expenses, view detailed financial reports, and visualize their spending/saving patterns with interactive charts.

---

## 🚀 Features

- **User Authentication**
  - Register, Login, Logout
  - Password reset via secure token
- **Income & Expense Management**
  - Add, edit, and delete expenses
  - Add and delete incomes
- **Dynamic Financial Reports**
  - Interactive pie chart toggle (switch between **Income** and **Expenses** without reloading)
  - Summary of total income, total expenses, and balance
- **Responsive UI**
  - TailwindCSS for a clean, mobile-friendly design

---

## 📂 Project Structure

expense-tracker/
│
├── static/                # Static assets (CSS, JS, images)
├── templates/             # HTML templates (Flask Jinja2)
│   ├── base.html
│   ├── dashboard.html
│   ├── financial_report.html
│   ├── login.html
│   ├── register.html
│   ├── reset_password.html
│   └── ...
│
├── main.py                 # Main Flask application
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation

---
```

### ⚙️ Installation & Setup

### 1️⃣ Clone the repository
```bash
git clone https://github.com/yourusername/expense-tracker.git
cd expense-tracker
```

### 2️⃣ Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate     # Mac/Linux
venv\Scripts\activate        # Windows
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Set environment variables (for development)

**Mac/Linux:**

```bash
export FLASK_APP=main.py
export FLASK_ENV=development
export SECRET_KEY='yoursecretkey'
```

**Windows (PowerShell):**

```powershell
set FLASK_APP=main.py
set FLASK_ENV=development
set SECRET_KEY=yoursecretkey
```

### 5️⃣ Initialize the database

```bash
flask shell
>>> from main import db
>>> db.create_all()
>>> exit()
```

### 6️⃣ Run the application

```bash
flask run
```

### 7️⃣ Open in your browser

```
http://127.0.0.1:5000
```

---

## 📊 Financial Report Page

The **Financial Report** page includes:

* A dropdown to toggle between **Income** and **Expense** pie charts instantly (no page reload)
* Total income, expenses, and balance
* Delete button for incomes & expenses directly from the dashboard

---

## 📦 Dependencies

* Flask
* Flask-Login
* Flask-WTF
* Flask-SQLAlchemy
* Werkzeug
* TailwindCSS
* Chart.js

> Install via:

```bash
pip install -r requirements.txt
```

---

## 🔒 Security

* Passwords are hashed before storage.
* Reset links are time-limited and token-based.
* CSRF protection enabled via Flask-WTF.

---

