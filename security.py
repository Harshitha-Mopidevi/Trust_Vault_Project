from functools import wraps
from flask import abort
from flask_login import current_user, login_required
from extensions import db
from models import ActivityLog, DocumentShare

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.active or current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def log_activity(action, details=""):
    org_id = current_user.organization_id if current_user.is_authenticated else None
    if org_id:
        db.session.add(ActivityLog(organization_id=org_id,
            user_id=current_user.id, action=action, details=(details or "")[:255]))

def same_tenant(document):
    return current_user.is_authenticated and current_user.organization_id == document.organization_id

def can_view_document(document):
    if not current_user.is_authenticated or not current_user.active or not same_tenant(document):
        return False
    if current_user.role == "admin" or document.owner_id == current_user.id:
        return True
    share = DocumentShare.query.filter_by(document_id=document.id, user_id=current_user.id, can_view=True).first()
    return bool(share)

def can_download_document(document):
    if not can_view_document(document): return False
    if current_user.role == "admin" or document.owner_id == current_user.id: return True
    share = DocumentShare.query.filter_by(document_id=document.id, user_id=current_user.id, can_view=True, can_download=True).first()
    return bool(share)

def can_edit_document(document):
    if not current_user.is_authenticated or not current_user.active or not same_tenant(document): return False
    if current_user.role == "admin" or document.owner_id == current_user.id: return True
    share = DocumentShare.query.filter_by(document_id=document.id, user_id=current_user.id, can_edit=True).first()
    return bool(share)
