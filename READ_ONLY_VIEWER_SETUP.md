# TrustVault: read-only document viewing setup

## Supported formats in the app

- Browser inline preview: PDF, TXT, CSV, PNG, JPG/JPEG, GIF, WEBP, BMP.
- ONLYOFFICE read-only viewer: DOC, DOCX, XLS, XLSX, PPT, PPTX, and optionally PDF/TXT/CSV.
- Other formats are rejected by upload validation.

## 1. Install and configure

1. Back up your project folder and database before replacing files.
2. Copy `.env.example` to `.env`. Set a unique, long random `SECRET_KEY`, admin credentials, organization settings, and invite code. Never commit `.env`.
3. Install dependencies with `pip install -r requirements.txt`.
4. Start Flask with `python run.py`.

## 2. ONLYOFFICE is required for Word/Excel/PowerPoint in-browser viewing

Run or deploy an ONLYOFFICE Docs server and configure `ONLYOFFICE_DOCUMENT_SERVER` to its real URL. The URL must be reachable from the user's browser. Configure `ONLYOFFICE_PUBLIC_URL` to a TrustVault URL that the ONLYOFFICE server itself can reach to download a document. If Flask and ONLYOFFICE run in separate containers, do not use `localhost` for one service to reach the other. Configure `ONLYOFFICE_JWT_SECRET` to match the server's JWT secret. If JWT is enabled, install `PyJWT` with `pip install PyJWT` (and add it to requirements before deployment).

The sample addresses in `.env.example` are examples only. They will not necessarily work in your environment. If the viewer cannot reach the server, the page will show a clear error instead of silently opening an editor.

## 3. Reading-only behavior

The ONLYOFFICE configuration sets `editorConfig.mode` to `view`, disables editing, and does not configure a save callback. The callback endpoint intentionally does not save or overwrite files. Users who need to change a document should use the permission-checked Download button and edit their downloaded copy.

## 4. Test checklist

1. Log in as Admin and upload a PDF, DOCX, XLSX, PPTX, TXT, CSV, and an image.
2. Click the eye/View action for each file. Confirm PDF/TXT/CSV/images render inline. Confirm Office files open in ONLYOFFICE view mode.
3. Confirm no editing toolbar or save-to-original workflow is available in the Office viewer.
4. Log in as a Viewer who has view permission but not download permission. Confirm viewing works and the Download button/route is denied.
5. Log in as a Viewer without a share. Confirm direct view and download URLs return 403.
6. Test admin-only routes such as `/admin/` and `/activity` with a regular account; they should return 403.
7. Test each search filter individually and combined: name, category, owner, and upload date.

## Notes

- The app's current upload size limit is 16 MB.
- Viewing Word/Excel/PowerPoint in the browser is not possible from Flask templates alone; a document rendering service is required.
- Use HTTPS, secure secrets, backups, and production deployment settings before storing confidential documents.
