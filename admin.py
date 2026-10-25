
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    current_app
)
from flask_login import current_user
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import User, Document, DocumentShare, ActivityLog
from security import roles_required, log_activity


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------
@admin_bp.route("/")
@roles_required("admin")
def dashboard():

    if not current_user.active:
        abort(403)

    org_id = current_user.organization_id

    users = (
        User.query
        .filter_by(organization_id=org_id)
        .order_by(User.created_at.desc())
        .all()
    )

    documents = (
        Document.query
        .filter_by(organization_id=org_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    shares = (
        DocumentShare.query
        .join(Document)
        .filter(Document.organization_id == org_id)
        .order_by(DocumentShare.created_at.desc())
        .all()
    )

    activity = (
        ActivityLog.query
        .filter_by(organization_id=org_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
        .all()
    )

    # Configuration checks
    secret_key = current_app.config.get("SECRET_KEY", "")

    security_checks = [
        (
            "Application secret",
            bool(secret_key)
            and secret_key != "change-this-secret-before-deployment"
        ),
        (
            "Private upload storage",
            bool(current_app.config.get("UPLOAD_FOLDER"))
            and not str(
                current_app.config.get("UPLOAD_FOLDER", "")
            ).startswith(str(current_app.static_folder))
        ),
        (
            "Read-only Office viewer",
            bool(current_app.config.get("ONLYOFFICE_DOCUMENT_SERVER"))
        ),
    ]

    return render_template(
        "admin_dashboard.html",
        users=users,
        documents=documents,
        shared_count=len(shares),
        activity=activity,
        shares=shares,
        organization=current_user.organization,
        security_checks=security_checks
    )


# --------------------------------------------------
# CREATE ADMIN / OWNER / VIEWER ACCOUNT
# --------------------------------------------------
@admin_bp.route("/create-user", methods=["GET", "POST"])
@roles_required("admin")
def create_user():

    if not current_user.active:
        abort(403)

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip().lower()

        # Validate required fields
        if not name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("admin.create_user"))

        # Validate role
        if role not in {"admin", "owner", "viewer"}:
            flash("Please select a valid role.", "danger")
            return redirect(url_for("admin.create_user"))

        # Validate password
        if len(password) < 8:
            flash(
                "Password must contain at least 8 characters.",
                "danger"
            )
            return redirect(url_for("admin.create_user"))

        # Check for an existing account
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash(
                "An account with this email already exists.",
                "danger"
            )
            return redirect(url_for("admin.create_user"))

        try:
            # Create account in the administrator's organization
            new_user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                active=True,
                organization_id=current_user.organization_id
            )

            db.session.add(new_user)
            db.session.flush()

            # Record the account creation in the audit log
            log_activity(
                "User created",
                f"Created account for {email} with role {role}"
            )

            db.session.commit()

            flash(
                f"{role.title()} account created successfully.",
                "success"
            )

            return redirect(url_for("admin.dashboard"))

        except IntegrityError:
            db.session.rollback()

            flash(
                "This email may already be registered. Please try another.",
                "danger"
            )

            return redirect(url_for("admin.create_user"))

        except Exception:
            db.session.rollback()

            current_app.logger.exception(
                "Failed to create a TrustVault user account"
            )

            flash(
                "Unable to create the account. Check the application logs.",
                "danger"
            )

            return redirect(url_for("admin.create_user"))

    return render_template("create_user.html")


# --------------------------------------------------
# CHANGE USER ROLE
# --------------------------------------------------
@admin_bp.route(
    "/user/<int:user_id>/role",
    methods=["POST"]
)
@roles_required("admin")
def change_role(user_id):

    if not current_user.active:
        abort(403)

    user = db.get_or_404(User, user_id)

    # Restrict changes to the current organization
    if user.organization_id != current_user.organization_id:
        abort(403)

    role = request.form.get("role", "").strip().lower()

    if role not in {"admin", "owner", "viewer"}:

        flash("Invalid role selected.", "danger")

    elif user.id == current_user.id and role != "admin":

        flash(
            "You cannot remove your own administrator role.",
            "danger"
        )

    elif (
        user.role == "admin"
        and role != "admin"
        and User.query.filter_by(
            organization_id=current_user.organization_id,
            role="admin",
            active=True
        ).count() <= 1
    ):

        flash(
            "Keep at least one active administrator in the company.",
            "danger"
        )

    else:

        old_role = user.role
        user.role = role

        log_activity(
            "Role changed",
            f"{user.email}: {old_role} -> {role}"
        )

        db.session.commit()

        flash("User role updated successfully.", "success")

    return redirect(url_for("admin.dashboard"))


# --------------------------------------------------
# ACTIVATE / DEACTIVATE USER
# --------------------------------------------------
@admin_bp.route(
    "/user/<int:user_id>/status",
    methods=["POST"]
)
@roles_required("admin")
def toggle_user(user_id):

    if not current_user.active:
        abort(403)

    user = db.get_or_404(User, user_id)

    # Restrict changes to the current organization
    if user.organization_id != current_user.organization_id:
        abort(403)

    if user.id == current_user.id:

        flash(
            "You cannot disable your own account.",
            "danger"
        )

    elif (
        user.active
        and user.role == "admin"
        and User.query.filter_by(
            organization_id=current_user.organization_id,
            role="admin",
            active=True
        ).count() <= 1
    ):

        flash(
            "You cannot disable the last active administrator.",
            "danger"
        )

    else:

        user.active = not user.active

        log_activity(
            "User status changed",
            f"{user.email}: "
            f"{'activated' if user.active else 'deactivated'}"
        )

        db.session.commit()

        flash("User status updated successfully.", "success")

    return redirect(url_for("admin.dashboard"))


# --------------------------------------------------
# ACTIVITY LOGS
# --------------------------------------------------
@admin_bp.route("/activity")
@roles_required("admin")
def activity_logs():

    if not current_user.active:
        abort(403)

    logs = (
        ActivityLog.query
        .filter_by(
            organization_id=current_user.organization_id
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(500)
        .all()
    )

    return render_template(
        "activity_logs.html",
        logs=logs
    )