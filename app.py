from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from pathlib import Path
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-secret-key-for-production"
DB_PATH = Path(__file__).with_name("marketplace.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('farmer', 'customer', 'admin')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            price REAL NOT NULL CHECK(price >= 0),
            quantity INTEGER NOT NULL CHECK(quantity >= 0),
            unit TEXT NOT NULL DEFAULT 'kg',
            image_url TEXT DEFAULT '',
            FOREIGN KEY (farmer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Placed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS supplies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            quantity TEXT NOT NULL,
            notes TEXT DEFAULT '',
            supplied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (farmer_id) REFERENCES users(id)
        );
        """)

        # Demo data lets you explore the website immediately.
        admin = db.execute("SELECT id FROM users WHERE email = ?", ("admin@farmbridge.local",)).fetchone()
        if not admin:
            db.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                ("Platform Admin", "admin@farmbridge.local", "admin123", "admin")
            )
        farmer = db.execute("SELECT id FROM users WHERE email = ?", ("farmer@example.com",)).fetchone()
        if not farmer:
            cur = db.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                ("Ravi Kumar", "farmer@example.com", "farmer123", "farmer")
            )
            farmer_id = cur.lastrowid
        else:
            farmer_id = farmer["id"]

        customer = db.execute("SELECT id FROM users WHERE email = ?", ("customer@example.com",)).fetchone()
        if not customer:
            db.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                ("Sita", "customer@example.com", "customer123", "customer")
            )

        count = db.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
        if count == 0:
            sample_products = [
                (farmer_id, "Tomatoes", "Vegetables", "Fresh farm-grown tomatoes.", 35, 50, "kg", ""),
                (farmer_id, "Spinach", "Leafy Greens", "Fresh green spinach leaves.", 25, 30, "bunch", ""),
                (farmer_id, "Mangoes", "Fruits", "Seasonal mangoes, subject to availability.", 90, 20, "kg", ""),
                (farmer_id, "Carrots", "Vegetables", "Crunchy carrots from the farm.", 45, 25, "kg", "")
            ]
            db.executemany(
                """INSERT INTO products
                (farmer_id, name, category, description, price, quantity, unit, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                sample_products
            )


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as db:
        return db.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if user["role"] not in roles:
                flash("You do not have permission to open that page.", "danger")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_user():
    return {"logged_in_user": current_user()}


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql = """SELECT products.*, users.name AS farmer_name
             FROM products JOIN users ON products.farmer_id = users.id
             WHERE products.quantity > 0"""
    params = []
    if search:
        sql += " AND (products.name LIKE ? OR products.description LIKE ? OR users.name LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])
    if category:
        sql += " AND products.category = ?"
        params.append(category)
    sql += " ORDER BY products.id DESC"
    with get_db() as db:
        products = db.execute(sql, params).fetchall()
        categories = db.execute("SELECT DISTINCT category FROM products ORDER BY category").fetchall()
    return render_template("index.html", products=products, categories=categories, search=search, selected_category=category)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        if not name or not email or len(password) < 6 or role not in ("farmer", "customer"):
            flash("Enter all details. Password must be at least 6 characters.", "danger")
            return render_template("register.html")
        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                    (name, email, password, role)
                )
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ? AND password = ?",
                (email, password)
            ).fetchone()
        if user:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    with get_db() as db:
        if user["role"] == "farmer":
            products = db.execute("SELECT * FROM products WHERE farmer_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
            orders = db.execute("""
                SELECT orders.*, products.name AS product_name, users.name AS customer_name
                FROM orders JOIN products ON orders.product_id = products.id
                JOIN users ON orders.customer_id = users.id
                WHERE products.farmer_id = ? ORDER BY orders.id DESC
            """, (user["id"],)).fetchall()
            supplies = db.execute("SELECT * FROM supplies WHERE farmer_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
            return render_template("farmer_dashboard.html", user=user, products=products, orders=orders, supplies=supplies)
        if user["role"] == "customer":
            orders = db.execute("""
                SELECT orders.*, products.name AS product_name, users.name AS farmer_name
                FROM orders JOIN products ON orders.product_id = products.id
                JOIN users ON products.farmer_id = users.id
                WHERE orders.customer_id = ? ORDER BY orders.id DESC
            """, (user["id"],)).fetchall()
            return render_template("customer_dashboard.html", user=user, orders=orders)
        users = db.execute("SELECT id, name, email, role, created_at FROM users ORDER BY id DESC").fetchall()
        products = db.execute("""
            SELECT products.*, users.name AS farmer_name FROM products
            JOIN users ON products.farmer_id = users.id ORDER BY products.id DESC
        """).fetchall()
        orders = db.execute("""
            SELECT orders.*, products.name AS product_name, users.name AS customer_name
            FROM orders JOIN products ON orders.product_id = products.id
            JOIN users ON orders.customer_id = users.id ORDER BY orders.id DESC
        """).fetchall()
        return render_template("admin_dashboard.html", users=users, products=products, orders=orders)


@app.route("/product/new", methods=["GET", "POST"])
@role_required("farmer")
def new_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        unit = request.form.get("unit", "kg").strip()
        image_url = request.form.get("image_url", "").strip()
        try:
            price = float(request.form.get("price", "0"))
            quantity = int(request.form.get("quantity", "0"))
        except ValueError:
            flash("Price and quantity must be valid numbers.", "danger")
            return render_template("product_form.html")
        if not name or not category or price < 0 or quantity < 0:
            flash("Complete all required fields with valid values.", "danger")
            return render_template("product_form.html")
        user = current_user()
        with get_db() as db:
            db.execute("""
                INSERT INTO products (farmer_id, name, category, description, price, quantity, unit, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user["id"], name, category, description, price, quantity, unit, image_url))
        flash("Product listed successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("product_form.html")


@app.route("/product/<int:product_id>/edit", methods=["GET", "POST"])
@role_required("farmer")
def edit_product(product_id):
    user = current_user()
    with get_db() as db:
        product = db.execute("SELECT * FROM products WHERE id = ? AND farmer_id = ?", (product_id, user["id"])).fetchone()
        if not product:
            flash("Product not found or not yours to edit.", "danger")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            description = request.form.get("description", "").strip()
            unit = request.form.get("unit", "kg").strip()
            image_url = request.form.get("image_url", "").strip()
            try:
                price = float(request.form.get("price", "0"))
                quantity = int(request.form.get("quantity", "0"))
            except ValueError:
                flash("Price and quantity must be valid numbers.", "danger")
                return render_template("product_form.html", product=product)
            if not name or not category or price < 0 or quantity < 0:
                flash("Complete all required fields with valid values.", "danger")
                return render_template("product_form.html", product=product)
            db.execute("""
                UPDATE products SET name=?, category=?, description=?, price=?, quantity=?, unit=?, image_url=?
                WHERE id=? AND farmer_id=?
            """, (name, category, description, price, quantity, unit, image_url, product_id, user["id"]))
        else:
            return render_template("product_form.html", product=product)
    flash("Product updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/order/<int:product_id>", methods=["POST"])
@role_required("customer")
def place_order(product_id):
    user = current_user()
    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        quantity = 0
    if quantity < 1:
        flash("Choose a quantity of at least 1.", "danger")
        return redirect(url_for("index"))
    with get_db() as db:
        product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product or product["quantity"] < quantity:
            flash("Sorry, that quantity is not currently available.", "danger")
            return redirect(url_for("index"))
        total = product["price"] * quantity
        db.execute(
            "INSERT INTO orders (customer_id, product_id, quantity, total) VALUES (?, ?, ?, ?)",
            (user["id"], product_id, quantity, total)
        )
        db.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (quantity, product_id))
    flash("Order placed successfully. This demo does not process real payments.", "success")
    return redirect(url_for("dashboard"))


@app.route("/order/<int:order_id>/status", methods=["POST"])
@role_required("farmer", "admin")
def update_order_status(order_id):
    status = request.form.get("status", "")
    allowed = {"Placed", "Accepted", "Packed", "Delivered", "Cancelled"}
    if status not in allowed:
        flash("Invalid order status.", "danger")
        return redirect(url_for("dashboard"))
    user = current_user()
    with get_db() as db:
        order = db.execute("""
            SELECT orders.id, products.farmer_id FROM orders
            JOIN products ON orders.product_id = products.id WHERE orders.id = ?
        """, (order_id,)).fetchone()
        if not order or (user["role"] == "farmer" and order["farmer_id"] != user["id"]):
            flash("Order not found or you cannot update it.", "danger")
            return redirect(url_for("dashboard"))
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    flash("Order status updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/supplies/new", methods=["POST"])
@role_required("admin")
def add_supply():
    farmer_id = request.form.get("farmer_id", type=int)
    item_type = request.form.get("item_type", "")
    item_name = request.form.get("item_name", "").strip()
    quantity = request.form.get("quantity", "").strip()
    notes = request.form.get("notes", "").strip()
    if not farmer_id or item_type not in ("Seeds", "Packaging") or not item_name or not quantity:
        flash("Complete all supply fields.", "danger")
        return redirect(url_for("dashboard"))
    with get_db() as db:
        farmer = db.execute("SELECT id FROM users WHERE id=? AND role='farmer'", (farmer_id,)).fetchone()
        if not farmer:
            flash("Select a valid farmer.", "danger")
            return redirect(url_for("dashboard"))
        db.execute(
            "INSERT INTO supplies (farmer_id, item_type, item_name, quantity, notes) VALUES (?, ?, ?, ?, ?)",
            (farmer_id, item_type, item_name, quantity, notes)
        )
    flash("Farmer supply record added.", "success")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
