
import os
from pathlib import Path

from dotenv import load_dotenv


# ---------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE, override=True)


# ---------------------------------------------------------
# IMPORT APPLICATION AND DATABASE
# ---------------------------------------------------------

from run import app
from extensions import db
from models import User, Organization


# ---------------------------------------------------------
# CREATE OR REPAIR ADMIN ACCOUNT
# ---------------------------------------------------------

def create_or_repair_admin():
    print("=" * 55)
    print("TRUSTVAULT ADMIN ACCOUNT SETUP")
    print("=" * 55)

    print("Project directory:", BASE_DIR)
    print(".env file exists:", ENV_FILE.is_file())

    with app.app_context():

        # -------------------------------------------------
        # READ ADMIN CONFIGURATION
        # -------------------------------------------------

        email = os.getenv(
            "TRUSTVAULT_ADMIN_EMAIL", ""
        ).strip().lower()

        password = os.getenv(
            "TRUSTVAULT_ADMIN_PASSWORD", ""
        )

        org_name = os.getenv(
            "TRUSTVAULT_ORG_NAME",
            "Demo Company"
        ).strip() or "Demo Company"

        org_code = os.getenv(
            "TRUSTVAULT_ORG_CODE",
            "CHANGE-THIS-COMPANY-INVITE-CODE"
        ).strip()

        if not email or not password:
            print("\nERROR: Admin email or password is missing.")
            print("Check these settings in your .env file:")
            print("TRUSTVAULT_ADMIN_EMAIL")
            print("TRUSTVAULT_ADMIN_PASSWORD")
            return

        if len(password) < 8:
            print("\nERROR: Admin password must be at least 8 characters.")
            return

        # -------------------------------------------------
        # FIND OR CREATE ORGANIZATION
        # -------------------------------------------------

        try:
            org = Organization.query.filter_by(
                name=org_name
            ).first()

            if org is None:
                org = Organization.query.order_by(
                    Organization.id
                ).first()

            if org is None:
                print("\nNo organization found.")
                print("Creating the default organization...")

                org = Organization(
                    name=org_name,
                    invite_code=org_code
                )

                db.session.add(org)
                db.session.flush()

                print("Organization created:", org_name)

            # -------------------------------------------------
            # FIND EXISTING ACCOUNT
            # -------------------------------------------------

            user = User.query.filter(
                db.func.lower(User.email) == email
            ).first()

            if user is None:

                # ---------------------------------------------
                # CREATE NEW ADMIN
                # ---------------------------------------------

                print("\nAdmin account does not exist.")
                print("Creating a new Admin account...")

                user = User(
                    name="TrustVault Admin",
                    email=email,
                    organization_id=org.id,
                    role="admin",
                    active=True,
                    password=password
                )

                db.session.add(user)

            else:

                # ---------------------------------------------
                # REPAIR EXISTING ACCOUNT
                # ---------------------------------------------

                print("\nAccount already exists.")
                print("Updating its Admin access and password...")

                user.role = "admin"
                user.active = True
                user.password = password

            # -------------------------------------------------
            # SAVE TO DATABASE
            # -------------------------------------------------

            db.session.commit()

            print("\nAccount information saved.")

            # -------------------------------------------------
            # VERIFY SAVED ACCOUNT
            # -------------------------------------------------

            saved_user = User.query.filter(
                db.func.lower(User.email) == email
            ).first()

            if saved_user is None:
                print("ERROR: Could not find the saved account.")
                return

            print("\n" + "-" * 40)
            print("ADMIN ACCOUNT DETAILS")
            print("-" * 40)

            print("Email:", saved_user.email)
            print("Role:", saved_user.role)
            print("Active:", saved_user.active)

            # Verify password if the model provides this method.
            if not hasattr(saved_user, "verify_password"):
                print(
                    "\nWARNING: User.verify_password() was not found."
                )
                print(
                    "Check the password verification method "
                    "in models.py."
                )
                return

            password_valid = saved_user.verify_password(password)

            if (
                saved_user.active
                and str(saved_user.role).lower() == "admin"
                and password_valid
            ):
                print("\nSUCCESS: Admin account is ready.")
                print("Password verification: successful")
                print("\nLogin URL: http://127.0.0.1:5000/login")
                print("Use the configured Admin email and password.")

            else:
                print("\nERROR: Admin verification failed.")
                print("Active:", saved_user.active)
                print("Role:", saved_user.role)
                print("Password valid:", password_valid)

        except Exception as error:
            db.session.rollback()

            print("\nADMIN SETUP FAILED")
            print("Error type:", type(error).__name__)
            print("Error details:", str(error))

            raise


# ---------------------------------------------------------
# RUN SCRIPT
# ---------------------------------------------------------

if __name__ == "__main__":
    create_or_repair_admin()