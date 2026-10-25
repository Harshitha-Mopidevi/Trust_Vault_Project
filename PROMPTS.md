# PROMPTS.md
## TrustVault — Secure Document Sharing System

> **Purpose:** This file records how AI assistance was used while developing and debugging TrustVault, what was checked, what went wrong, and what still requires verification. It is not a claim that every listed test has passed.
>
> **Accuracy note:** The entries below reflect the TrustVault development and debugging work documented so far. Before submitting, edit anything that does not accurately represent what you actually asked or did, and add any important prompts from your own development history.

---

## 1. Project Context

**Project name:** TrustVault — Secure Document Sharing System  
**Main technology:** Python and Flask  
**Related components observed in the project:** Flask-Login, SQLAlchemy, CSRF protection, authentication and document-management blueprints, an administration blueprint, and ONLYOFFICE document-editor integration.

TrustVault is intended to provide a web application for managing users and organizations and working with documents. Authentication, permissions, secure configuration, and reliable document access are important to the project.

The implementation and feature list must be judged from the actual source code and tested application. This file does not claim that every intended feature is complete or secure.

## 2. How AI Was Used

AI assistance was used as a development aid for:
- Understanding and organizing a Flask application with separate modules.
- Investigating errors from terminal output and browser behavior.
- Reviewing environment-variable loading and Admin account setup.
- Investigating Flask-Login configuration.
- Troubleshooting the connection between the Flask application and ONLYOFFICE.
- Preparing debugging and verification steps.

AI suggestions were treated as hypotheses to check against the actual source code, configuration, database, and runtime behavior. Suggestions were not considered proof that a feature worked.

---

## 3. Prompt and Debugging Log

### Entry 1 — Understanding the Flask application structure

**Prompt / task**

"Help me understand and organize my Flask application so authentication, document routes, administration, models, extensions, and configuration are separated into appropriate modules. Check how the application factory registers blueprints and initializes extensions."

**Why I used it**

The application contains separate files such as `run.py`, `config.py`, `extensions.py`, `models.py`, `auth.py`, `documents.py`, and `admin.py`. I needed to understand how these parts fit together and how the app is initialized.

**AI limitation considered**

AI can suggest a standard Flask structure, but it may assume module names, route names, or model fields that differ from those in the actual project.

**Validation / action**

- Compare suggestions with the existing project files.
- Check that each imported module exists.
- Check that blueprints are registered only once.
- Check that `db`, `login_manager`, and `csrf` are initialized with the same Flask app.
- Keep existing working code unless a change is needed and tested.

**Result**

The application structure was reviewed while troubleshooting runtime errors. Do not mark the structure as fully validated until the app starts and the relevant routes have been tested.

### Entry 2 — Admin account not created / invalid credentials

**Prompt / task**

"Help me troubleshoot why the TrustVault Admin account is not being created and why login reports invalid credentials. Check environment variables, the `.env` path, database initialization, user lookup, role, active status, and password hashing/verification."

**Observed problem**

The Admin login returned an invalid-credentials message. A separate Admin setup script reported that the Admin email and password were missing.

**Evidence collected**

A PowerShell check in the project directory returned:

```text
Folder: C:\Users\HARSHITHA\OneDrive\Desktop\TrustVault - Copy
.env exists: False
Admin email found: False
Admin password found: False
```

This established that a file named `.env` was not present at the path being checked and the expected values were not loaded from that path.

**AI limitation considered**

A script that calls `load_dotenv(".env")` can fail to find the file if the working directory is different or the file is missing or named incorrectly. A script can also connect to a different database if configuration is loaded in the wrong order or a different database URI is used.

**Correction / action**

- Create the `.env` file in the actual TrustVault project directory.
- Check that it is named `.env`, not `.env.txt`.
- Load it using a path based on the script's directory.
- Check whether required variables exist without printing secret values.
- Run the Admin setup script and inspect the actual result.
- Verify the account using the application's real password-setting and password-verification methods.
- Confirm that the running web app uses the same database configuration.

**Verification status**

The missing `.env` file was confirmed by the command output. Do not claim Admin creation or login is fixed until the setup script succeeds and a real login test passes.

### Entry 3 — Flask-Login missing user loader

**Prompt / task**

"Explain and help fix the Flask-Login error `Missing user_loader or request_loader`. Check the login manager instance and the User model, and show how the callback should load a user from the database."

**Observed problem**

The application produced a Flask-Login error stating that a `user_loader` or `request_loader` was missing when authentication code checked the current user's authentication state.

**Why this matters**

Flask-Login needs a way to reload the authenticated user from the stored user identifier. Initializing the login manager does not, by itself, define the callback that retrieves a user.

**Correction approach**

- Inspect where `login_manager` is created and initialized.
- Register a `@login_manager.user_loader` callback on that same instance.
- Make the callback query the actual User model using the correct primary-key type.
- Confirm the callback is registered before authenticated requests occur.
- Check that the login code uses the same User model and login manager.

**Verification status**

Mark this resolved only after the application starts, valid login works, authenticated pages load, and logout behaves as expected. Suggested code alone is not evidence of a fix.

### Entry 4 — Loading configuration in the correct order

**Prompt / task**

"Review the order in which the Flask application loads `.env` and imports `Config`. Could configuration values be read before environment variables are loaded?"

**Issue identified**

In the reviewed `run.py`, `Config` was imported before `load_dotenv()` was called. If `Config` reads environment variables when the class is imported, values could be read too early.

**Correction approach**

- Load the `.env` file before importing a configuration module that reads environment variables at import time.
- Use a stable path based on `Path(__file__).resolve().parent`.
- Review the database URI and upload-folder configuration.
- Confirm that the setup script and web application point to the same database.

**Verification status**

Check the actual `config.py` implementation and confirm the resulting configuration. Do not assume that changing the import order automatically fixes a database mismatch.

### Entry 5 — Password storage and verification

**Prompt / task**

"Check how the User model stores passwords and verifies them. Make sure Admin setup uses the application's existing password-hashing mechanism instead of storing a plain-text password."

**Why I used it**

The Admin setup code assigns a password to a User object. Whether that assignment hashes the password depends on the actual model implementation.

**Correction / validation**

- Inspect the User model's password field and setter/property.
- Inspect the password verification method used by the login route.
- Use the same mechanism in the Admin setup script.
- Never print or commit real passwords.
- Test with the intended Admin account or a local test account.

**Important limitation**

A line such as `user.password = password` is safe only if the model's setter or other code hashes the password. This must be confirmed in the actual `models.py`; it must not be assumed.

**Verification status**

Verify using the application's password-verification method and then test login. Do not report this as passed without the test result.

### Entry 6 — ONLYOFFICE editor does not connect

**Prompt / task**

"Help me troubleshoot why a TrustVault document page loads but the ONLYOFFICE editor does not connect. Separate Flask page rendering from document-server connectivity and editor configuration."

**Observed problem**

The document page was displayed, but the editor did not connect successfully.

**Reasoning**

A rendered Flask page does not prove that the document editor service is reachable or that its configuration is valid. The editor may depend on a separate document server, correct URLs, reachable document and callback URLs, and matching authentication/JWT settings if JWT is enabled.

**Correction / investigation steps**

- Confirm the ONLYOFFICE Document Server is running.
- Check the configured `ONLYOFFICE_DOCUMENT_SERVER` URL from the relevant browser/server environment.
- Check whether the browser and Flask server can reach the required endpoints.
- Verify the configured public application URL and document/callback URLs.
- If JWT is enabled, verify that the application and document server use matching secrets without exposing those secrets.
- Inspect browser developer tools and Flask/Document Server logs.
- Test opening and editing a supported document, then verify the expected save behavior.

**Verification status**

The integration remains unverified until a document opens successfully and the expected workflow is tested. A page appearing is not enough to call the integration complete.

### Entry 7 — Protecting configuration and secrets

**Prompt / task**

"Help me prepare a safe `.gitignore` and an example environment file for a Flask application so local secrets are not uploaded to GitHub."

**Correction / action**

- Exclude `.env` from Git.
- Use `.env.example` for placeholder names and non-secret examples only.
- Do not put actual passwords, secret keys, or tokens in the example file.
- Review `git status` before committing.
- Check tracked files before pushing, especially after adding configuration files.
- If a real secret was already committed, remove it from the repository and rotate it; deleting the file in a later commit does not make the old secret safe.

**Example `.gitignore` entries to review against project needs**

```gitignore
.env
.venv/
venv/
__pycache__/
*.py[cod]
```

Other exclusions should be selected based on the actual project. Do not blindly ignore a database or uploaded files if the application requires sample data for evaluation; instead, ensure no private or sensitive information is included.

**Verification status**

Review the actual repository and confirm that no real secrets are tracked before submission.

### Entry 8 — Testing the application before submission

**Prompt / task**

"Create a practical test checklist for TrustVault that checks authentication, user permissions, document operations, configuration, and deployment. Separate tests that passed from tests that still need to be performed."

**Validation checklist**

| Area | Test to perform | Evidence to record |
|---|---|---|
| Application startup | Start Flask with the documented command | Terminal output and absence of startup errors |
| Authentication | Test valid and invalid credentials | Actual login result |
| User loading | Open an authenticated page and log out | Actual browser result |
| Admin setup | Run setup script and verify the saved account | Script output and successful login |
| Authorization | Try restricted routes with the wrong role or without logging in | Actual denial or redirect |
| Documents | Test document operations implemented in the app | Actual result for each operation |
| ONLYOFFICE | Open a document and test the expected save workflow | Successful editor and save test |
| Configuration | Check required variables without displaying secrets | Presence/absence checks |
| Repository | Inspect files and Git status before push | No `.env` or sensitive data committed |
| Deployment | Open the live URL in a private window and another device | Actual availability and feature test |

**Verification status**

This table is a test plan, not a statement that every test has passed. Record the date and actual result after each test.

---

## 4. Examples of AI Limitations and How I Evaluated Them

The development process showed why AI suggestions must be checked against the real project:

1. **Assuming an environment file exists:** A setup process cannot read configuration from a file that is not present at the expected path. I checked this with PowerShell, which reported `.env exists: False`.
2. **Assuming model methods and fields:** Example code may use methods such as `verify_password()` or fields such as `active` that need to be confirmed in the actual User model and database schema.
3. **Assuming an account was created because code ran:** Account creation must be confirmed by checking the database and performing a real login.
4. **Treating the editor page as proof of editor functionality:** The Flask page and ONLYOFFICE service need separate checks.
5. **Treating a proposed fix as a completed fix:** The change must be tested in the actual application before it is described as resolved.

These are practical lessons from the issues investigated. Do not add claims about additional AI errors unless they occurred during your work.

## 5. Security Considerations

Because TrustVault handles users and documents, the following areas deserve particular attention:

- Passwords must be hashed using a suitable password-hashing method.
- Authentication and role-based authorization are different; restricted routes must enforce authorization on the server.
- User-supplied filenames and document paths must be handled safely.
- Document access must be checked for the requesting user and their permissions.
- CSRF protection should be enabled for applicable state-changing form requests.
- Secret keys, passwords, JWT secrets, and other credentials must not be committed to GitHub.
- Production configuration should use strong secrets and secure transport where appropriate.
- Error messages and logs must not disclose secrets or sensitive document contents.

These are security checks to perform, not claims that every item has already been implemented or audited.

## 6. Known Issues and Current Status

Update this section immediately before submission based on the latest tests.

| Item | Status based on currently documented evidence |
|---|---|
| `.env` file | A check reported that `.env` was absent from the expected project directory. Confirm the file now exists. |
| Admin account creation | Not confirmed as successful in the documented output. Run the setup script and test login. |
| Flask-Login user loader | An error was previously reported. Confirm the callback is implemented and test authentication. |
| ONLYOFFICE integration | The document page appeared but the editor did not connect. Test and record the current result. |
| Authorization checks | Requires verification against the actual routes and roles. |
| Deployment | Add the actual live URL and test results after deployment. |

Do not leave an outdated status in this table. Replace it with the current result, including any remaining limitations.

## 7. Final Reflection

AI was used to assist with code organization, debugging, configuration checks, and preparation of tests. The most important lesson was to use the actual error output and project files to validate suggestions instead of accepting generated code without checking it.

For TrustVault, environment configuration, the Admin account workflow, Flask-Login user loading, and the external document-editor integration need to be tested independently. A successful submission should accurately distinguish working features from unfinished work.

The final project and this log should reflect the real development process. I am responsible for understanding the code, validating changes, documenting actual results, and explaining the implementation during evaluation.
