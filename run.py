import os, secrets
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from pathlib import Path
from flask import Flask, render_template
load_dotenv()  # Load .env before Config reads environment variables.
from config import Config
from extensions import db, login_manager, csrf
from models import User, Organization

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    db.init_app(app); login_manager.init_app(app); csrf.init_app(app)
    login_manager.login_view = "auth.login"
    @login_manager.user_loader
    def load_user(user_id): return db.session.get(User, int(user_id))
    import auth, documents, admin
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(documents.documents_bp)
    app.register_blueprint(admin.admin_bp)
    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403, title="Access denied",
          message="You do not have permission to access this resource."), 403
    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, title="Not found",
          message="The requested page or document could not be found."), 404
    @app.errorhandler(413)
    def too_large(error):
        return render_template("error.html", code=413, title="File too large",
          message="The upload exceeds the 16 MB limit."), 413
    with app.app_context():
        db.create_all()
        
        # Lightweight SQLite migration for databases created by the earlier TrustVault starter.
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        org_name = os.getenv("TRUSTVAULT_ORG_NAME", "Demo Company").strip()
        invite_code = os.getenv("TRUSTVAULT_ORG_CODE", "DEMO-TRUSTVAULT").strip()
        org = Organization.query.filter_by(name=org_name).first()
        if not org:
            org = Organization(name=org_name, invite_code=invite_code)
            db.session.add(org); db.session.commit()
        additions = {
            "user": {"organization_id": "INTEGER", "profile_image": "VARCHAR(255)"},
            "document": {"organization_id": "INTEGER"},
            "activity_log": {"organization_id": "INTEGER"},
            "document_share": {"can_edit": "BOOLEAN NOT NULL DEFAULT 0"},
        }
        for table, columns in additions.items():
            if table not in tables:
                continue
            present = {c["name"] for c in inspect(db.engine).get_columns(table)}
            for column, sql_type in columns.items():
                if column not in present:
                    db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
        db.session.commit()
        # Assign records from a legacy single-workspace database to the configured company.
        db.session.execute(text("UPDATE user SET organization_id=:org WHERE organization_id IS NULL"), {"org": org.id})
        db.session.execute(text("UPDATE document SET organization_id=:org WHERE organization_id IS NULL"), {"org": org.id})
        db.session.execute(text("UPDATE activity_log SET organization_id=:org WHERE organization_id IS NULL"), {"org": org.id})
        db.session.commit()
        admin_email = os.getenv("TRUSTVAULT_ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("TRUSTVAULT_ADMIN_PASSWORD", "")
        if admin_email and admin_password:
            existing_admin = User.query.filter(db.func.lower(User.email) == admin_email).first()
            if not existing_admin:
                db.session.add(User(name="TrustVault Admin", email=admin_email,
                    organization_id=org.id, role="admin", active=True, password=admin_password))
                db.session.commit()
            elif existing_admin.role != "admin":
                existing_admin.role = "admin"
                db.session.commit()
    return app
app = create_app()
if __name__ == "__main__":
    app.run(debug=True)
