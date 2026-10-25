
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)
from sqlalchemy import func
from pathlib import Path
import uuid

from werkzeug.utils import secure_filename

from extensions import db
from models import User, Organization
from security import log_activity


auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("documents.dashboard"))

    return redirect(url_for("auth.login"))


# ---------------------------------------------------------
# REGISTER
# Roles available in the form: Admin, Owner, Viewer
# ---------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("documents.dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Read the role selected in register.html.
        role = request.form.get("role", "owner").strip().lower()

        # Validate the required fields.
        if not name or not email or not password:
            flash(
                "Please enter your name, email address, and password.",
                "danger",
            )
            return render_template("register.html")

        if len(name) > 100:
            flash("Your name cannot exceed 100 characters.", "danger")
            return render_template("register.html")

        if len(email) > 255:
            flash("Your email address is too long.", "danger")
            return render_template("register.html")

        if len(password) < 8:
            flash(
                "Password must contain at least 8 characters.",
                "danger",
            )
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        # Accept only the three recognized role values.
        allowed_roles = {"admin", "owner", "viewer"}

        if role not in allowed_roles:
            flash("Invalid role selected.", "danger")
            return render_template("register.html")

        # Prevent duplicate email addresses, ignoring letter case.
        existing_user = User.query.filter(
            func.lower(User.email) == email
        ).first()

        if existing_user:
            flash(
                "An account with this email already exists.",
                "danger",
            )
            return render_template("register.html")

        # The existing database schema requires an organization.
        # Assign the user to the first available organization.
        # For multi-company registration, use an approved invitation
        # or an explicit organization-selection/approval workflow.
        organization = Organization.query.order_by(
            Organization.id
        ).first()

        if organization is None:
            flash(
                "No company workspace is configured yet. "
                "Please ask the administrator to configure TrustVault.",
                "danger",
            )
            return render_template("register.html")

        try:
            user = User(
                name=name,
                email=email,
                organization_id=organization.id,
                role=role,
                active=True,
                password=password,
            )

            db.session.add(user)
            db.session.flush()

            log_activity(
                "Registered",
                f"New {role} account registered: {email}",
            )

            db.session.commit()

            flash(
                f"{role.capitalize()} account created successfully. "
                "Please sign in.",
                "success",
            )

            return redirect(url_for("auth.login"))

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "TrustVault registration failed."
            )

            flash(
                "Registration failed. Please try again.",
                "danger",
            )

    return render_template("register.html")


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("documents.dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        user = User.query.filter(
            func.lower(User.email) == email
        ).first()

        if (
            user
            and user.verify_password(password)
            and user.active
        ):
            login_user(user, remember=remember)

            log_activity(
                "Login",
                "Successful sign-in",
            )

            db.session.commit()

            return redirect(url_for("documents.dashboard"))

        flash(
            "Invalid credentials or account disabled.",
            "danger",
        )

    return render_template("login.html")


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():

    log_activity(
        "Logout",
        "Signed out",
    )

    db.session.commit()

    logout_user()

    flash("You have been signed out.", "success")

    return redirect(url_for("auth.login"))


# ---------------------------------------------------------
# PROFILE
# Update display name, password, and profile image.
# ---------------------------------------------------------

@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        current_password = request.form.get(
            "current_password", ""
        )
        new_password = request.form.get(
            "new_password", ""
        )
        confirm_password = request.form.get(
            "confirm_password", ""
        )

        # Validate name.
        if not name:
            flash("Name cannot be empty.", "danger")
            return render_template("profile.html")

        if len(name) > 100:
            flash(
                "Name cannot exceed 100 characters.",
                "danger",
            )
            return render_template("profile.html")

        # Validate password changes.
        if new_password:

            if not current_user.verify_password(current_password):
                flash(
                    "Current password is incorrect.",
                    "danger",
                )
                return render_template("profile.html")

            if len(new_password) < 8:
                flash(
                    "New password must contain at least 8 characters.",
                    "danger",
                )
                return render_template("profile.html")

            if new_password != confirm_password:
                flash(
                    "New passwords do not match.",
                    "danger",
                )
                return render_template("profile.html")

        # Validate and save the optional profile image.
        photo = request.files.get("profile_image")
        new_image_filename = None

        if photo and photo.filename:

            extension = (
                photo.filename.rsplit(".", 1)[-1].lower()
                if "." in photo.filename
                else ""
            )

            allowed_extensions = {
                "png",
                "jpg",
                "jpeg",
                "webp",
            }

            if extension not in allowed_extensions:
                flash(
                    "Profile photo must be PNG, JPG, JPEG, or WEBP.",
                    "danger",
                )
                return render_template("profile.html")

            image_directory = (
                Path(current_app.root_path)
                / "static"
                / "profile_images"
            )

            image_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            safe_filename = secure_filename(photo.filename)

            new_image_filename = (
                uuid.uuid4().hex + "_" + safe_filename
            )

            photo.save(
                image_directory / new_image_filename
            )

        try:
            # Apply profile changes.
            current_user.name = name

            if new_password:
                current_user.password = new_password

            if new_image_filename:
                current_user.profile_image = new_image_filename

            log_activity(
                "Profile updated",
                "Profile/password settings changed",
            )

            db.session.commit()

            flash(
                "Profile updated successfully.",
                "success",
            )

            return redirect(url_for("auth.profile"))

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "TrustVault profile update failed."
            )

            flash(
                "Could not update your profile. Please try again.",
                "danger",
            )

    return render_template("profile.html")
