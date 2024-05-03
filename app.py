import os

#from cs50 import SQL
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

import datetime

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'


''' Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")'''

db = SQLAlchemy(app)


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


alert_start = '<div class="alert alert-info" role="alert">'
alert_end = '</div>'


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    transactions = db.execute(
        "SELECT symbol, SUM(shares) AS shares, price, SUM(shares)*price AS balance FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    # return jsonify(transactions): helps to understand that transactions is a list of ditionaries
    # eg: [{"price":428.74,"shares":5,"symbol":"MSFT"}]

    # Cash from database eg: [{"cash":7856.3}]
    username_db = db.execute("SELECT username FROM users WHERE id = ?", user_id)
    username = username_db[0]["username"]
    cash_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_balance[0]["cash"]
    total_transactions = db.execute(
        "SELECT SUM(total_balance) AS grand_total FROM (SELECT SUM(shares) * price AS total_balance from transactions WHERE user_id = ? GROUP BY symbol)", user_id)
    grand_total = 0
    grand_total = total_transactions[0]["grand_total"]
    if not grand_total:  # check if grand_total is None
        grand_total = 0
    grand_total = grand_total + cash
    # return jsonify(total_transactions)
    # return jsonify(transactions)
    return render_template("index.html", transactions=transactions, cash=cash, grand_total=grand_total, username=username)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Share not allowed, must be a positive integer", 400)
        if not symbol:
            return apology("Must provide Symbol", 403)
        elif not shares:
            return apology("Must provide number of shares", 403)

        symbol = symbol.upper()

        stock = lookup(symbol)

        if stock == None:
            return apology("Symbol Does not exist", 400)
        if shares < 0 or not isinstance(shares, int):
            return apology("Share not allowed, must be positive integer", 400)

        user_id = session["user_id"]
        transaction_value = shares * stock["price"]  # i.e. total amount to buy the shares
        user_cash_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        # jsonify helps here : jsonify(user_cash_balance)
        user_cash = user_cash_balance[0]["cash"]

        if user_cash < transaction_value:
            return apology("Cannot afford")

        updated_cash = user_cash - transaction_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, user_id)

        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date, total) VALUES (?, ?, ?, ?, ?, ?)",
                   user_id, symbol, shares, stock["price"], date, transaction_value)

        flash("Bought!")

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions = db.execute(
        "SELECT symbol, shares, price, date FROM transactions WHERE user_id = ?", user_id)
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    elif not request.form.get("symbol"):
        return apology("Must Provide Symbol", 400)
    else:
        symbol = request.form.get("symbol")
        symbol = symbol.upper()

        stock = lookup(symbol)

        if stock == None:
            return apology("Symbol Does not exist")

        return render_template("quoted.html", symbol=stock["symbol"], price=stock["price"], alert_start=alert_start, alert_end=alert_end)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        username = username.strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")
        if confirm_password != password:
            return apology("Invalid Password, password must be same", 400)
        # Ensure username was submitted
        elif not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)
        elif not confirm_password:
            return apology("Must Confirm Password!", 400)

        special_characters = '!@#$%^&*()-+?_=,<>/"'
        if not any(c in special_characters for c in password):
            return apology("Password Must Contain a special Character", 403)
        elif not any(c.isalnum() for c in password):
            return apology("Password must contain letters and numbers", 403)

        hash = generate_password_hash(password)

        try:
            # Add username to the database
            db.execute(
                "INSERT INTO users (username, hash) VALUES( ?, ?)", username, hash
            )
        except:
            return apology("Username Already Exists")

        # Redirect User to Log In page to proceed with their actions
        redirect_message = 'Registered! Log In to proceed'
        return render_template("login.html", register_message=redirect_message, alert_start=alert_start, alert_end=alert_end)
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Must provide Symbol", 403)
        elif not shares:
            return apology("Must provide number of shares", 400)

        symbol = symbol.upper()

        stock = lookup(symbol)

        if stock == None:
            return apology("Symbol Does not exist")
        if shares < 0:
            return apology("Share not allowed, must be positive integer")
        transaction_value = shares * stock["price"]
        user_id = session["user_id"]

        existing_shares_db = db.execute(
            "SELECT SUM(shares) AS shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)
        existing_shares = existing_shares_db[0]["shares"]
        if shares > existing_shares:
            return apology("Too many shares!", 400)

        user_cash_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_balance[0]["cash"]

        updated_cash = user_cash + transaction_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, user_id)

        date = datetime.datetime.now()
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price, date, total) VALUES (?, ?, ?, ?, ?, ?)", user_id, symbol, (-1 *
                                                                                                                                  shares), stock["price"], date, transaction_value
        )
        flash("Sold!")
        return redirect("/")

    else:
        user_id = session["user_id"]
        user_symbols = db.execute(
            "SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        # return jsonify(user_symbols)
        return render_template("sell.html", user_symbols=user_symbols)


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        password = request.form.get("password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        user_id = session["user_id"]
        if not password:
            return apology("Must Provide Password!", 403)
        elif not new_password:
            return apology("Must Provide New Password!", 403)
        elif not confirm_password:
            return apology("Must Confirm New Password!", 403)
        user_data = db.execute("SELECT hash FROM users WHERE id = ?", user_id)
        hash_old = user_data[0]["hash"]
        if not check_password_hash(hash_old, password):
            return apology("Incorrect Password!")
        if new_password != confirm_password:
            return apology("Invalid Confirmation!", 403)
        if new_password == password:
            return apology("New Password is same as your password", 403)
        special_characters = '!@#$%^&*()-+?_=,<>/"'
        if not any(c in special_characters for c in new_password):
            return apology("Password Must Contain a special Character", 403)
        elif not any(c.isalnum() for c in new_password):
            return apology("Password must contain letters and numbers", 403)
        new_hash = generate_password_hash(new_password)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", new_hash, user_id)
        redirect_message = "Password Changed!"
        return redirect("/")
        # return render_template("index.html", alert_start=alert_start, alert_end=alert_end, change_password_message=redirect_message)

    else:
        return render_template("change-password.html")


@app.route("/add-cash", methods=["GET", "POST"])
@login_required
def add_cash():
    if request.method == "POST":
        user_id = session["user_id"]
        add_cash = request.form.get("add_cash")
        password = request.form.get("password")
        if not password:
            return apology("Must Provide Password", 403)
        if not add_cash:
            return apology("Must Provide Cash to add", 403)
        add_cash = float(add_cash)
        hash_db = db.execute("SELECT hash FROM users WHERE id = ?", user_id)
        if not check_password_hash(hash_db[0]["hash"], password):
            return apology("Incorrect Password!", 403)
        if add_cash > 10000:
            return apology("Cannot add more than $10,000 once", 403)


        flash("Cash Added!")
        return redirect("/")
    else:
        return render_template("add-cash.html")
