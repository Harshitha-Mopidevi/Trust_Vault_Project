import uuid
import os
from pathlib import Path
from urllib.parse import quote
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    send_file,
    current_app,
    jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import or_

from extensions import db
from models import User, Document, DocumentShare, ActivityLog
from security import (
    roles_required,
    log_activity,
    can_view_document,
    can_download_document,
    can_edit_document,
)

documents_bp = Blueprint("documents", __name__)

CATEGORIES = [
    "General",
    "Business",
    "Finance",
    "HR",
    "Legal",
    "Operations",
    "Education",
    "Personal",
    "Other",
]


# ---------------------------------------------------------
# FILE VALIDATION
# ---------------------------------------------------------

def allowed(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


# ---------------------------------------------------------
# DOCUMENT VISIBILITY
# Admin: all documents in their organization.
# Owner: documents they own and documents shared with them.
# Viewer: documents explicitly shared with them.
# ---------------------------------------------------------

def visible_query():
    shared = (
        db.session.query(DocumentShare.document_id)
        .filter_by(user_id=current_user.id, can_view=True)
    )

    query = Document.query.filter_by(
        organization_id=current_user.organization_id
    )

    if current_user.role == "admin":
        return query

    return query.filter(
        or_(
            Document.owner_id == current_user.id,
            Document.id.in_(shared),
        )
    )


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

@documents_bp.route("/dashboard")
@login_required
def dashboard():

    if not current_user.active:
        abort(403)

    docs = (
        visible_query()
        .order_by(Document.uploaded_at.desc())
        .limit(6)
        .all()
    )

    if current_user.role == "admin":

        users_count = User.query.filter_by(
            organization_id=current_user.organization_id
        ).count()

        shared_count = (
            DocumentShare.query
            .join(Document)
            .filter(
                Document.organization_id
                == current_user.organization_id
            )
            .count()
        )

        activity = (
            ActivityLog.query
            .filter_by(
                organization_id=current_user.organization_id
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(6)
            .all()
        )

        total = visible_query().count()

    else:
        users_count = None
        shared_count = None
        activity = []

        total = Document.query.filter_by(
            owner_id=current_user.id,
            organization_id=current_user.organization_id,
        ).count()

    return render_template(
        "dashboard.html",
        docs=docs,
        users_count=users_count,
        shared_count=shared_count,
        activity=activity,
        total=total,
        categories=CATEGORIES,
    )


# ---------------------------------------------------------
# MY DOCUMENTS
# ---------------------------------------------------------

@documents_bp.route("/documents")
@login_required
def my_documents():

    if not current_user.active:
        abort(403)

    query = visible_query()

    search_text = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    if search_text:
        query = query.filter(
            or_(
                Document.title.ilike(f"%{search_text}%"),
                Document.original_name.ilike(f"%{search_text}%"),
            )
        )

    if category in CATEGORIES:
        query = query.filter_by(category=category)

    docs = query.order_by(
        Document.uploaded_at.desc()
    ).all()

    # Only active, non-admin users in the same organization
    # can appear as recipients in the sharing dropdown.
    # Exclude the current user.
    users = (
        User.query
        .filter(
            User.organization_id == current_user.organization_id,
            User.id != current_user.id,
            User.active.is_(True),
            User.role.in_(["owner", "viewer"]),
        )
        .order_by(User.name)
        .all()
    )

    # Load existing shares only for documents the current user
    # is allowed to manage.
    shares_by_doc = {}

    for doc in docs:
        can_manage = (
            current_user.role == "admin"
            or doc.owner_id == current_user.id
        )

        if can_manage:
            shares_by_doc[doc.id] = (
                DocumentShare.query
                .filter_by(document_id=doc.id)
                .all()
            )

    return render_template(
        "my_documents.html",
        docs=docs,
        categories=CATEGORIES,
        users=users,
        shares_by_doc=shares_by_doc,
    )


# ---------------------------------------------------------
# UPLOAD DOCUMENT
# ---------------------------------------------------------

@documents_bp.route("/upload", methods=["GET", "POST"])
@roles_required("owner", "admin")
def upload():

    if not current_user.active:
        abort(403)

    if request.method == "POST":

        file = request.files.get("file")
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "General")

        if (
            not file
            or not file.filename
            or not allowed(file.filename)
            or not title
            or len(title) > 180
        ):
            flash(
                "Choose an allowed file and enter a valid document title.",
                "danger",
            )
            return redirect(url_for("documents.upload"))

        from werkzeug.utils import secure_filename

        original_name = secure_filename(file.filename)

        if not original_name:
            flash("Invalid filename.", "danger")
            return redirect(url_for("documents.upload"))

        upload_folder = Path(
            current_app.config["UPLOAD_FOLDER"]
        )
        upload_folder.mkdir(parents=True, exist_ok=True)

        stored_name = uuid.uuid4().hex + "_" + original_name
        file_path = upload_folder / stored_name

        try:
            file.save(file_path)

            document = Document(
                title=title,
                original_name=original_name,
                stored_name=stored_name,
                category=(
                    category if category in CATEGORIES
                    else "General"
                ),
                owner_id=current_user.id,
                organization_id=current_user.organization_id,
            )

            db.session.add(document)
            log_activity("Uploaded", title)
            db.session.commit()

            flash("Document uploaded securely.", "success")

            return redirect(
                url_for("documents.my_documents")
            )

        except Exception:
            db.session.rollback()

            # Remove the saved file if database insertion failed.
            if file_path.exists():
                file_path.unlink()

            current_app.logger.exception(
                "Document upload failed."
            )

            flash(
                "Upload failed. Please try again.",
                "danger",
            )

            return redirect(url_for("documents.upload"))

    return render_template(
        "upload.html",
        categories=CATEGORIES,
    )


# ---------------------------------------------------------
# VIEW DOCUMENT / OPEN EDITOR
# ---------------------------------------------------------

OFFICE_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".txt", ".csv"}
INLINE_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _document_path(doc):
    return Path(current_app.config["UPLOAD_FOLDER"]) / doc.stored_name


def _editor_serializer():
    secret = current_app.config.get("SECRET_KEY")
    if not secret or secret == "change-this-secret-before-deployment":
        raise RuntimeError("Set a strong SECRET_KEY before enabling document editing.")
    return URLSafeTimedSerializer(secret, salt="trustvault-document-editor")


def _editor_url_token(doc_id, purpose):
    return _editor_serializer().dumps({"doc_id": doc_id, "purpose": purpose})


def _verify_editor_url_token(token, doc_id, purpose, max_age=3600):
    try:
        data = _editor_serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired, TypeError):
        return False
    return data.get("doc_id") == doc_id and data.get("purpose") == purpose


@documents_bp.route("/document/<int:doc_id>/view")
@login_required
def view_document(doc_id):
    """Show browser-supported files inline without requiring ONLYOFFICE."""
    if not current_user.active:
        abort(403)

    doc = db.get_or_404(Document, doc_id)
    if (
        not can_view_document(doc)
        or doc.organization_id != current_user.organization_id
    ):
        abort(403)

    path = _document_path(doc)
    if not path.is_file():
        abort(404)

    extension = Path(doc.original_name).suffix.lower()
    log_activity("Viewed", doc.title)
    db.session.commit()

    # PDFs, text/CSV files, and common images can be displayed by browsers.
    # Do not redirect these files to ONLYOFFICE, so they work without it.
    mimetype = INLINE_MIME_TYPES.get(extension)
    if mimetype:
        response = send_file(
            path,
            mimetype=mimetype,
            as_attachment=False,
            conditional=True,
        )
        response.headers["Content-Disposition"] = (
            "inline; filename*=UTF-8''" + quote(doc.original_name)
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "private, no-store"
        return response

    # Office formats need ONLYOFFICE or another viewer for in-app preview.
    # If no viewer is configured, download a copy instead of showing a broken page.
    office_extensions = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
    if extension in office_extensions:
        if not can_download_document(doc):
            abort(403)
        response = send_file(
            path,
            as_attachment=True,
            download_name=doc.original_name,
        )
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return render_template(
        "document_preview_unavailable.html",
        doc=doc,
        can_download=can_download_document(doc),
    ), 415


@documents_bp.route("/document/<int:doc_id>/editor")
@login_required
def edit_document_content(doc_id):
    """Render the ONLYOFFICE editor page. Editing is permission-checked server-side."""
    if not current_user.active:
        abort(403)

    doc = db.get_or_404(Document, doc_id)
    if doc.organization_id != current_user.organization_id or not can_view_document(doc):
        abort(403)

    # TrustVault viewing is always read-only. To make changes, users must
    # download the file and edit their own local copy.
    read_only = True

    server_url = (current_app.config.get("ONLYOFFICE_DOCUMENT_SERVER") or "").rstrip("/")
    public_url = (current_app.config.get("ONLYOFFICE_PUBLIC_URL") or request.url_root).rstrip("/")
    jwt_secret = current_app.config.get("ONLYOFFICE_JWT_SECRET", "")
    if not server_url:
        flash("The online document editor is not configured yet.", "warning")
        return redirect(url_for("documents.view_document", doc_id=doc.id))

    extension = Path(doc.original_name).suffix.lower().lstrip(".")
    if extension not in {"docx", "xlsx", "pptx", "pdf", "txt", "csv"}:
        flash("This file type is not supported by the online editor.", "warning")
        return redirect(url_for("documents.my_documents"))

    # Document Server downloads the file using this short-lived signed URL.
    # No callback URL is configured because this editor is strictly read-only.
    file_token = _editor_url_token(doc.id, "file")
    file_url = public_url + url_for("documents.editor_file", doc_id=doc.id, token=file_token)

    config = {
        "document": {
            "fileType": extension,
            "key": f"trustvault-{doc.id}-{int(doc.uploaded_at.timestamp()) if doc.uploaded_at else doc.id}",
            "title": doc.original_name,
            "url": file_url,
            "permissions": {
                "edit": False,
                "download": bool(can_download_document(doc)),
                "print": bool(can_download_document(doc)),
                "review": False,
                "comment": False,
                "fillForms": False,
            },
        },
        "documentType": (
            "word" if extension in {"doc", "docx", "txt"}
            else "cell" if extension in {"xls", "xlsx", "csv"}
            else "slide" if extension in {"ppt", "pptx"}
            else "pdf"
        ),
        "editorConfig": {
            "mode": "view",
            "user": {"id": str(current_user.id), "name": current_user.name},
            "customization": {
                "forcesave": False,
                "reviewDisplay": "original",
            },
        },
    }

    # ONLYOFFICE expects a signed config token when JWT is enabled on Document Server.
    if jwt_secret:
        try:
            import jwt
        except ImportError:
            current_app.logger.exception("PyJWT is required when ONLYOFFICE_JWT_SECRET is set.")
            abort(500, description="Install PyJWT to enable the document editor.")
        config["token"] = jwt.encode(config, jwt_secret, algorithm="HS256")

    log_activity("Opened editor", doc.title)
    db.session.commit()
    return render_template(
        "document_editor.html",
        doc=doc,
        document_server_url=server_url,
        editor_config=config,
        read_only=read_only,
    )


@documents_bp.route("/document/<int:doc_id>/editor-file")
def editor_file(doc_id):
    """Temporary, signed file URL consumed by ONLYOFFICE Document Server."""
    token = request.args.get("token", "")
    if not _verify_editor_url_token(token, doc_id, "file"):
        abort(403)

    doc = db.get_or_404(Document, doc_id)
    path = _document_path(doc)
    if not path.is_file():
        abort(404)

    response = send_file(path, as_attachment=False, download_name=doc.original_name)
    response.headers["Cache-Control"] = "no-store"
    return response


@documents_bp.route("/document/<int:doc_id>/editor-callback", methods=["POST"])
def editor_callback(doc_id):
    """
    Compatibility endpoint for older editor sessions.

    TrustVault viewing is read-only, so callbacks must never overwrite the
    original uploaded document. This endpoint intentionally does not save files.
    """
    current_app.logger.info(
        "Ignored ONLYOFFICE callback for read-only document %s.", doc_id
    )
    return jsonify({"error": 0})


# ---------------------------------------------------------
# DOWNLOAD DOCUMENT
# ---------------------------------------------------------

@documents_bp.route("/document/<int:doc_id>/download")
@login_required
def download_document(doc_id):

    if not current_user.active:
        abort(403)

    doc = db.get_or_404(Document, doc_id)

    if not can_download_document(doc):
        abort(403)

    path = (
        Path(current_app.config["UPLOAD_FOLDER"])
        / doc.stored_name
    )

    if not path.is_file():
        abort(404)

    log_activity("Downloaded", doc.title)
    db.session.commit()

    return send_file(
        path,
        as_attachment=True,
        download_name=doc.original_name,
    )


# ---------------------------------------------------------
# EDIT DOCUMENT DETAILS
# Owners/Admins can manage permitted documents.
# Viewers can edit only when the owner granted edit access.
# ---------------------------------------------------------

@documents_bp.route(
    "/document/<int:doc_id>/edit",
    methods=["POST"],
)
@login_required
def edit_document(doc_id):

    if not current_user.active:
        abort(403)

    doc = db.get_or_404(Document, doc_id)

    if not can_edit_document(doc):
        abort(403)

    # Prevent cross-organization edits.
    if doc.organization_id != current_user.organization_id:
        abort(403)

    title = request.form.get("title", "").strip()
    category = request.form.get("category", "General")

    if not title or len(title) > 180:
        flash("Enter a valid document title.", "danger")

    else:
        doc.title = title
        doc.category = (
            category if category in CATEGORIES
            else "General"
        )

        log_activity("Edited document metadata", doc.title)
        db.session.commit()

        flash("Document details updated.", "success")

    return redirect(
        request.referrer
        or url_for("documents.my_documents")
    )


# ---------------------------------------------------------
# GRANT OR UPDATE ACCESS
# Only the document owner or organization Admin can share.
# ---------------------------------------------------------

@documents_bp.route(
    "/document/<int:doc_id>/share",
    methods=["POST"],
)
@roles_required("owner", "admin")
def share_document(doc_id):

    if not current_user.active:
        abort(403)

    doc = db.get_or_404(Document, doc_id)

    if doc.organization_id != current_user.organization_id:
        abort(403)

    if (
        current_user.role != "admin"
        and doc.owner_id != current_user.id
    ):
        abort(403)

    recipient_id = request.form.get("user_id", type=int)

    if recipient_id is None:
        flash("Please select a user.", "danger")
        return redirect(
            request.referrer
            or url_for("documents.my_documents")
        )

    user = db.session.get(User, recipient_id)

    # Validate the recipient on the server.
    if (
        not user
        or not user.active
        or user.organization_id != doc.organization_id
        or user.role not in ["owner", "viewer"]
        or user.id == doc.owner_id
    ):
        flash(
            "Choose an active Owner or Viewer from your company "
            "who is not the document owner.",
            "danger",
        )

        return redirect(
            request.referrer
            or url_for("documents.my_documents")
        )

    share = DocumentShare.query.filter_by(
        document_id=doc.id,
        user_id=user.id,
    ).first()

    if share is None:
        share = DocumentShare(
            document_id=doc.id,
            user_id=user.id,
        )
        db.session.add(share)

    share.can_view = True
    share.can_edit = request.form.get("can_edit") == "on"
    share.can_download = (
        request.form.get("can_download") == "on"
    )

    log_activity(
        "Shared",
        f"{doc.title} with {user.email}; "
        f"edit={share.can_edit}, "
        f"download={share.can_download}",
    )

    db.session.commit()

    flash(
        f"Access granted to {user.name}.",
        "success",
    )

    return redirect(
        request.referrer
        or url_for("documents.my_documents")
    )


# ---------------------------------------------------------
# REVOKE ACCESS
# Only the document owner or organization Admin can revoke.
# ---------------------------------------------------------

@documents_bp.route(
    "/document/<int:doc_id>/revoke/<int:user_id>",
    methods=["POST"],
)
@roles_required("owner", "admin")
def revoke_share(doc_id, user_id):

    if not current_user.active:
        abort(403)

    doc = db.get_or_404(Document, doc_id)

    if doc.organization_id != current_user.organization_id:
        abort(403)

    if (
        current_user.role != "admin"
        and doc.owner_id != current_user.id
    ):
        abort(403)

    share = DocumentShare.query.filter_by(
        document_id=doc.id,
        user_id=user_id,
    ).first()

    if share:
        db.session.delete(share)

        log_activity(
            "Access revoked",
            f"{doc.title}: user id {user_id}",
        )

        db.session.commit()

        flash("Access revoked successfully.", "success")

    else:
        flash(
            "No matching access permission was found.",
            "warning",
        )

    return redirect(
        request.referrer
        or url_for("documents.my_documents")
    )


# ---------------------------------------------------------
# DELETE DOCUMENT
# Only the document owner or organization Admin can delete.
# ---------------------------------------------------------

@documents_bp.route(
    "/document/<int:doc_id>/delete",
    methods=["POST"],
)
@roles_required("owner", "admin")
def delete_document(doc_id):

    if not current_user.active:
        abort(403)

    doc = db.get_or_404(Document, doc_id)

    if doc.organization_id != current_user.organization_id:
        abort(403)

    if (
        current_user.role != "admin"
        and doc.owner_id != current_user.id
    ):
        abort(403)

    path = (
        Path(current_app.config["UPLOAD_FOLDER"])
        / doc.stored_name
    )

    title = doc.title

    try:
        # Delete the database record and its shares first.
        # If DocumentShare does not cascade automatically,
        # remove its related records explicitly.
        DocumentShare.query.filter_by(
            document_id=doc.id
        ).delete(synchronize_session=False)

        db.session.delete(doc)

        log_activity("Deleted", title)
        db.session.commit()

        # Remove the physical file after a successful commit.
        if path.exists():
            path.unlink()

        flash("Document deleted successfully.", "success")

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Document deletion failed."
        )

        flash(
            "Could not delete the document. Please try again.",
            "danger",
        )

    return redirect(
        url_for("documents.my_documents")
    )


# ---------------------------------------------------------
# SEARCH DOCUMENTS
# ---------------------------------------------------------

@documents_bp.route("/search")
@login_required
def search_documents():

    if not current_user.active:
        abort(403)

    query = visible_query()

    search_text = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    owner = request.args.get("owner", "").strip()
    date = request.args.get("date", "").strip()

    if search_text:
        query = query.filter(
            or_(
                Document.title.ilike(f"%{search_text}%"),
                Document.original_name.ilike(
                    f"%{search_text}%"
                ),
            )
        )

    if category in CATEGORIES:
        query = query.filter_by(category=category)

    if owner:
        query = (
            query.join(User, Document.owner_id == User.id)
            .filter(User.name.ilike(f"%{owner}%"))
        )

    if date:
        query = query.filter(
            db.func.date(Document.uploaded_at) == date
        )

    docs = query.order_by(
        Document.uploaded_at.desc()
    ).all()

    return render_template(
        "search_documents.html",
        docs=docs,
        categories=CATEGORIES,
    )


# ---------------------------------------------------------
# CATEGORIES
# ---------------------------------------------------------

@documents_bp.route("/categories")
@login_required
def categories():

    if not current_user.active:
        abort(403)

    query = visible_query()

    counts = [
        (category, query.filter_by(category=category).count())
        for category in CATEGORIES
    ]

    return render_template(
        "categories.html",
        counts=counts,
    )


# ---------------------------------------------------------
# ACTIVITY LOGS
# Admin only.
# ---------------------------------------------------------
@documents_bp.route("/activity")
@login_required
@roles_required("admin")
def activity_logs():

    # Block inactive users
    if not current_user.active:
        abort(403)

    # Fetch the latest 500 logs for the current organization
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