# TrustVault role rules

## Admin
- Created only through the initial setup credentials in `.env` / environment variables.
- Can view and manage documents, users, and shares within their company workspace.
- Can assign `owner`, `viewer`, or `admin` roles to users in the same company.
- Can view that company's activity logs.
- Cannot disable or demote their own account, and the last active admin cannot be demoted.

## Owner
- Public registration creates an Owner by default.
- Can upload, view, edit metadata, download, and delete documents they own.
- Can grant and revoke access to documents they own.
- Cannot manage users, view admin activity logs, or change other owners' documents or shares.

## Viewer
- Created when an Admin changes a user's role to Viewer.
- Can see documents explicitly shared with them (plus any document they own if the Admin has not changed their role away from Owner).
- Can edit document metadata or download only if the owner grants the corresponding permission.
- Cannot upload, delete, share, revoke access, manage users, or view activity logs. Unauthorized attempts should receive HTTP 403.

## Important
The role selector is intentionally not shown on public registration. If visitors could choose Admin themselves, anyone could grant themselves administrative privileges. Admin is bootstrapped from setup credentials, Owners self-register, and Admin assigns Viewer roles.
