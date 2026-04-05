# Security Policy

---

## Supported Versions

Only the latest commit on the `master` branch is actively maintained.
Security fixes are applied directly to `master` and not backported to older tags.

| Version | Status |
|---------|--------|
| Latest (`master`) | Actively maintained — security fixes applied |
| Any tagged release older than the latest | Not maintained |

---

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately by emailing the maintainer. If a public contact
is not listed in this repository, open a GitHub Security Advisory:

1. Go to the repository on GitHub.
2. Click **Security** → **Advisories** → **Report a vulnerability**.
3. Fill in the template with as much detail as possible.

### What to include in your report

- A clear description of the vulnerability and its potential impact.
- Steps to reproduce (proof of concept, if possible).
- Affected component(s) and file paths.
- Any relevant log output or error messages (with secrets redacted).
- Suggested remediation, if you have one.

### Response timeline

| Stage | Target time |
|-------|-------------|
| Initial acknowledgement | Within 3 business days |
| Triage and severity assessment | Within 7 business days |
| Fix or mitigation released | Depends on severity — critical issues prioritized |
| Public disclosure | After fix is released and users have had time to update |

---

## Security Architecture

Understanding the security model helps assess the impact of potential vulnerabilities.

### Authentication

- **JWT tokens** are used for all API and WebSocket authentication.
- Tokens are signed with `JWT_SECRET_KEY` (HS256 algorithm, configurable expiry via `JWT_EXPIRE_DAYS`).
- WebSocket connections pass the token as a URL query parameter (`?token=`) because
  browser WebSocket APIs do not support custom headers. This is acceptable in a
  TLS-encrypted environment; ensure HTTPS is enabled in production.
- Passwords are hashed with **bcrypt** before storage. Raw passwords are never logged or stored.

### Authorization

- All resources (conversations, voice models, messages) are scoped to the authenticated user.
  The `user_id` from the JWT claim is always used as the filter — client-supplied user IDs
  are never trusted.

### Input Validation

- Uploaded ZIP files are validated server-side: required files must be present, the
  `base_model_version` field in `metadata.json` must equal `"GPT-SoVITS v2"`.
- Audio input from the browser is converted by ffmpeg before processing.
  ffmpeg is invoked with fixed arguments — user-controlled data is never injected
  into shell commands.
- File upload size is limited by `MAX_UPLOAD_SIZE_MB` (default 500 MB).

### Data Storage

- **PostgreSQL** stores user accounts, voice model metadata, conversations, and messages.
  No raw audio is stored in the database.
- **Redis** stores the active voice selection (per user) and LLM context (last 10 turns per conversation).
  Redis should be configured with authentication (`REDIS_PASSWORD`) in production.
- **Filesystem** stores voice model weights and reference audio under `storage/`.
  This directory should not be publicly accessible.

### Rate Limiting

- All REST API endpoints are protected by `slowapi` rate limits.
- WebSocket connections are rate-limited at the connection level.

---

## Deployment Security Recommendations

These recommendations apply when running this project in a production or
internet-facing environment.

### Essential

- [ ] **Use HTTPS.** Configure TLS termination at Nginx (see `docs/DEPLOY.md`).
      Never run in production over plain HTTP.
- [ ] **Set a strong `JWT_SECRET_KEY`.** Generate with `openssl rand -hex 32`.
      Minimum 32 characters.
- [ ] **Set a strong database password.** Change the default `POSTGRES_PASSWORD` in `.env`.
- [ ] **Set a Redis password** (`REDIS_PASSWORD`) and enable `requirepass` in Redis config.
- [ ] **Restrict CORS origins.** Set `CORS_ORIGINS` to your actual domain(s) only.
      Do not use `*` in production.
- [ ] **Keep `storage/` private.** The storage directory must not be served by a web server
      directly. Nginx configuration should only proxy `/api/*` and `/ws/*` to the backend.
- [ ] **Do not expose the backend port (8000) publicly.** All traffic should go through Nginx.
- [ ] **Do not expose PostgreSQL or Redis ports publicly.** Use Docker network isolation.

### Recommended

- [ ] Set up automatic security updates for the host OS.
- [ ] Enable Docker Content Trust.
- [ ] Rotate `JWT_SECRET_KEY` periodically (invalidates all existing sessions).
- [ ] Monitor the health endpoint (`GET /api/health`) with an external uptime checker.
- [ ] Review application logs regularly for unusual activity.
- [ ] Use a firewall (e.g., `ufw`) to restrict incoming traffic to ports 80 and 443 only.

---

## Known Limitations

| Limitation | Notes |
|-----------|-------|
| Audio replay is in-memory only | TTS audio chunks are stored in browser memory for the current session and not persisted server-side. Replay is not available after page reload. |
| JWT invalidation | There is no token revocation mechanism. Tokens remain valid until expiry. Changing `JWT_SECRET_KEY` invalidates all tokens immediately. |
| No CAPTCHA on registration | Automated account creation is not rate-limited beyond the API rate limiter. |
| WebSocket token in URL | JWT is passed as a query parameter for WebSocket connections. Ensure server access logs are restricted to prevent token leakage via log files. |
