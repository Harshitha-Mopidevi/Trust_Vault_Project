# TrustVault

White-and-blue Flask document portal with Admin, Owner, and Viewer roles.

## Setup (Windows PowerShell)

1. Create a virtual environment and install dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env`. Set a long random `SECRET_KEY`, a unique administrator email/password, a company name, and a private company invite code.
3. Run `python run.py`.
4. Open http://127.0.0.1:5000.
5. Register Owner/Viewer accounts using the company invitation code shown in `.env` (or in Admin Console).

The initial admin is created only if `TRUSTVAULT_ADMIN_EMAIL` and `TRUSTVAULT_ADMIN_PASSWORD` are set and that email is not already registered. If the database already exists, the startup migration adds the new organization/profile/edit columns and assigns legacy records to the configured default organization.

## Permission model

- Admin: company-scoped user, document, sharing, and activity administration.
- Owner: upload, edit metadata, delete own documents, and grant/revoke access to own documents.
- Viewer: view shared documents, edit metadata only when granted, and download only when granted.
- All document and sharing access is tenant/company scoped.
- Uploads are stored outside `static/`; do not expose the uploads folder as a static directory.

## Notes

- "Edit" permission allows editing the document's title/category metadata. It does not edit the contents of arbitrary PDF/Office files.
- Set a unique, high-entropy secret key and use HTTPS, backups, malware scanning, and production-grade deployment settings before handling confidential data.
- Company invitation codes are join credentials: distribute them only to intended users and rotate them if exposed.


## Role creation and permissions

- **Admin:** created during initial setup from `TRUSTVAULT_ADMIN_EMAIL` and `TRUSTVAULT_ADMIN_PASSWORD` in `.env`. Do not let public registration choose Admin.
- **Owner:** public registration creates an Owner account by default. Owners upload and manage their own documents and may grant or revoke access to those documents.
- **Viewer:** an Admin assigns this role from Admin Console. Viewers cannot grant/revoke shares, upload, delete, or manage users. A Viewer can view shared files and can edit document metadata/download only when the document owner explicitly grants those permissions.
- Share-management routes enforce permissions on the server; hiding a button in HTML is not the security boundary. Unauthorized requests return HTTP 403.
