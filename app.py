from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# IMPORTANT: Use /tmp for Render
UPLOAD_FOLDER = "/tmp/uploads"
DATABASE = "/tmp/users.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB max upload

STORAGE_LIMIT_MB = 100
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "txt", "docx"}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ---------------- DATABASE ---------------- #

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ---------------- USER CLASS ---------------- #

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user["id"], user["username"])
    return None


# ---------------- HELPERS ---------------- #

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------- ROUTES ---------------- #

@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        try:
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            login_user(User(user["id"], user["username"]))
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials")

    return render_template("login.html")


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    user_folder = os.path.join(app.config["UPLOAD_FOLDER"], current_user.username)
    os.makedirs(user_folder, exist_ok=True)

    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            flash("No file selected")
            return redirect(url_for("dashboard"))

        if not allowed_file(file.filename):
            flash("File type not allowed")
            return redirect(url_for("dashboard"))

        filename = secure_filename(file.filename)
        file_path = os.path.join(user_folder, filename)

        # Check storage size
        file.seek(0, os.SEEK_END)
        file_size = file.tell() / (1024 * 1024)
        file.seek(0)

        current_size = sum(
            os.path.getsize(os.path.join(user_folder, f))
            for f in os.listdir(user_folder)
        ) / (1024 * 1024)

        if current_size + file_size > STORAGE_LIMIT_MB:
            flash("Storage limit exceeded")
        else:
            file.save(file_path)

    files = os.listdir(user_folder)

    total_size = sum(
        os.path.getsize(os.path.join(user_folder, f))
        for f in files
    ) / (1024 * 1024)

    total_size = round(total_size, 2)
    remaining = round(STORAGE_LIMIT_MB - total_size, 2)

    return render_template(
        "dashboard.html",
        files=files,
        used=total_size,
        remaining=remaining,
        username=current_user.username
    )


@app.route("/download/<filename>")
@login_required
def download_file(filename):
    filename = secure_filename(filename)
    user_folder = os.path.join(app.config["UPLOAD_FOLDER"], current_user.username)
    file_path = os.path.join(user_folder, filename)

    if not os.path.exists(file_path):
        abort(404)

    return send_from_directory(user_folder, filename, as_attachment=True)


@app.route("/delete/<filename>")
@login_required
def delete_file(filename):
    filename = secure_filename(filename)
    user_folder = os.path.join(app.config["UPLOAD_FOLDER"], current_user.username)
    file_path = os.path.join(user_folder, filename)

    if os.path.exists(file_path):
        os.remove(file_path)

    return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run()