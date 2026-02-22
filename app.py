import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary
import cloudinary.uploader
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- DATABASE CONFIG ----------------

database_url = os.environ.get("DATABASE_URL")

# For local testing fallback
if not database_url:
    database_url = "sqlite:///local.db"

# Fix Render postgres:// issue
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------- LOGIN CONFIG ----------------

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ---------------- CLOUDINARY CONFIG ----------------

cloudinary.config(
    cloud_name=os.environ.get("CLOUD_NAME"),
    api_key=os.environ.get("API_KEY"),
    api_secret=os.environ.get("API_SECRET")
)

# ---------------- MODELS ----------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300))
    file_url = db.Column(db.String(500))
    size = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if User.query.filter_by(email=email).first():
            flash("Email already exists")
            return redirect(url_for("register"))

        new_user = User(
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid credentials")

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    files = File.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", files=files)

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")

    if file:
        upload_result = cloudinary.uploader.upload(file)

        new_file = File(
            filename=file.filename,
            file_url=upload_result["secure_url"],
            size=upload_result.get("bytes", 0),
            user_id=current_user.id
        )

        db.session.add(new_file)
        db.session.commit()

    return redirect(url_for("dashboard"))

@app.route("/delete/<int:file_id>")
@login_required
def delete(file_id):
    file = File.query.get_or_404(file_id)

    if file.user_id == current_user.id:
        db.session.delete(file)
        db.session.commit()

    return redirect(url_for("dashboard"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------------- CREATE TABLES ----------------

with app.app_context():
    db.create_all()

# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)
