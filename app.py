import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "d93kL!2kL0x9$8sZpQ7"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB limit

bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "zip"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect("users.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.close()

init_db()

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1])
    return None

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
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")

        try:
            conn = sqlite3.connect("users.db")
            conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()

            os.makedirs(os.path.join(UPLOAD_FOLDER, username), exist_ok=True)

            flash("Account created! Please login.")
            return redirect(url_for("login"))

        except:
            flash("Username already exists!")
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db")
        cur = conn.cursor()
        cur.execute("SELECT id, username, password FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user[2], password):
            login_user(User(user[0], user[1]))
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials!")

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    user_folder = os.path.join(UPLOAD_FOLDER, current_user.username)
    files = os.listdir(user_folder)
    return render_template("dashboard.html", files=files)

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files["file"]
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        user_folder = os.path.join(UPLOAD_FOLDER, current_user.username)
        file.save(os.path.join(user_folder, filename))
        flash("File uploaded successfully!")
    else:
        flash("Invalid file type!")

    return redirect(url_for("dashboard"))

@app.route("/delete/<filename>")
@login_required
def delete_file(filename):
    user_folder = os.path.join(UPLOAD_FOLDER, current_user.username)
    os.remove(os.path.join(user_folder, filename))
    flash("File deleted!")
    return redirect(url_for("dashboard"))

@app.route("/download/<filename>")
@login_required
def download_file(filename):
    user_folder = os.path.join(UPLOAD_FOLDER, current_user.username)
    return send_from_directory(user_folder, filename, as_attachment=True)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)