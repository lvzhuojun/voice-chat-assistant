# Documentation Standard

> **This document is the single source of truth for all documentation in this project.**
> Every contributor must read and follow it. Every code change that affects behavior, APIs,
> configuration, or user experience **requires** a corresponding documentation update.

[中文 README](../README.zh.md) | [English README](../README.md)

---

## Table of Contents

- [1. Document Inventory](#1-document-inventory)
- [2. When to Update Documentation](#2-when-to-update-documentation)
- [3. Formatting Rules](#3-formatting-rules)
- [4. Security and Privacy Rules](#4-security-and-privacy-rules)
- [5. Document Templates](#5-document-templates)
  - [5.1 README Template](#51-readme-template)
  - [5.2 API Reference Template](#52-api-reference-template)
  - [5.3 Guide Template](#53-guide-template)
  - [5.4 CHANGELOG Entry Format](#54-changelog-entry-format)
- [6. Bilingual Policy](#6-bilingual-policy)
- [7. Update Workflow](#7-update-workflow)
- [8. Review Checklist](#8-review-checklist)

---

## 1. Document Inventory

Every file below is **mandatory**. All must be kept up-to-date.

| File | Purpose | Updated When |
|------|---------|--------------|
| `README.md` | English project overview, quick start, feature list | Features added/removed, quick start steps change, tech stack changes |
| `README.zh.md` | Chinese project overview (mirrors README.md) | Same as README.md — always in sync |
| `ARCHITECTURE.md` | System design, data flow, database schema, deployment topology | Architecture changes, new services, schema changes |
| `CHANGELOG.md` | Chronological list of all notable changes | Every commit / release |
| `CONTRIBUTING.md` | How to set up the dev environment and submit changes | Dev workflow changes |
| `SECURITY.md` | Supported versions, vulnerability reporting process | Any security policy change |
| `docs/DOC_STANDARD.md` | **This file** — governs all other documentation | Documentation rules change |
| `docs/API.md` | REST API and WebSocket reference | Any endpoint added, removed, or modified |
| `docs/DEPLOY.md` | Production deployment on Linux + Docker | Deployment steps, dependencies, or config change |
| `docs/DEVELOPMENT.md` | Local development setup, hot-reload, testing | Dev tooling or workflow changes |
| `docs/VOICE_MODEL_IMPORT.md` | How to package and import a voice model | Import process or ZIP format changes |
| `docs/TROUBLESHOOTING.md` | Consolidated known issues and fixes | Any new known issue, workaround, or environment fix |

**Optional (add when relevant):**

| File | Purpose |
|------|---------|
| `docs/FAQ.md` | Frequently asked questions |

---

## 2. When to Update Documentation

### Required on every pull request

A PR **must** include documentation updates if any of the following are true:

- [ ] A new feature was added or an existing feature was removed
- [ ] An API endpoint was added, removed, renamed, or its request/response schema changed
- [ ] A configuration variable (`.env`) was added, removed, or renamed
- [ ] The startup/installation process changed
- [ ] A dependency was added, upgraded, or removed
- [ ] A bug was fixed that users could have encountered
- [ ] Any security-relevant change was made
- [ ] A known issue, workaround, or environment limitation was identified

### Required on every commit

- [ ] Add an entry to `CHANGELOG.md` (see [Section 5.4](#54-changelog-entry-format))

### Exception

Documentation-only PRs do not need a `CHANGELOG` entry beyond noting the docs update itself.

---

## 3. Formatting Rules

### 3.1 Markdown Style

- Use **ATX headings** (`#`, `##`, `###`) — never Setext (`===`, `---` underlines).
- Maximum heading depth: `####` (H4). Avoid H5/H6.
- Leave **one blank line** before and after every heading, code block, blockquote, and table.
- Leave **two blank lines** before each top-level `##` section.
- Use `---` (three dashes, own line) as a horizontal rule to separate major sections.
- Wrap long prose lines at **100 characters** (code blocks are exempt).
- No trailing whitespace on any line.
- Files end with exactly **one newline** character.

### 3.2 Code Blocks

Always specify the language identifier:

````markdown
```bash
# shell commands
```

```python
# Python code
```

```json
{ "key": "value" }
```

```typescript
const x: number = 1
```

```nginx
# nginx config
```
````

Use `bash` for shell commands, `powershell` or `bat` for Windows-specific commands.

For inline code, use backticks: `` `variable_name` ``, `` `POST /api/voices/import` ``.

### 3.3 Tables

- All tables must have a header row and separator row.
- Align column separators for readability in source.
- Keep cell content concise — link out to sections for details.

```markdown
| Column A | Column B | Column C |
|----------|----------|----------|
| value    | value    | value    |
```

### 3.4 Diagrams

Prefer **Mermaid** diagrams (rendered by GitHub):

```markdown
​```mermaid
flowchart LR
    A --> B --> C
​```
```

For ASCII art diagrams (used in ARCHITECTURE.md), keep column width ≤ 80 characters and use box-drawing characters consistently.

### 3.5 Links

- Use **relative paths** for internal document links: `[API Reference](docs/API.md)`.
- Never use absolute file system paths (`C:\Users\...`, `/home/user/...`).
- External URLs must be complete and verified before committing.
- Anchor links must exactly match heading text (lowercase, spaces → hyphens):
  - Heading: `## Quick Start` → anchor: `#quick-start`

### 3.6 Admonitions (Callouts)

Use blockquotes with bold labels for important notices:

```markdown
> **Note:** This applies only in production.

> **Warning:** This will delete all data.

> **Tip:** You can skip this step if you already ran Project 1.
```

---

## 4. Security and Privacy Rules

These rules are **non-negotiable**. Violations will block PR approval.

### 4.1 Never commit secrets

The following must **never** appear in any documentation file:

- Real API keys, tokens, or passwords
- Real database connection strings with credentials
- Real JWT secret keys
- Personal email addresses, phone numbers, or home addresses
- Absolute file system paths containing usernames (`C:\Users\alice\...`, `/home/bob/...`)

### 4.2 Placeholder format

Use angle-bracket placeholders for any value a user must supply:

```bash
JWT_SECRET_KEY=<your-secret-key>
LLM_API_KEY=<your-openai-api-key>
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>
```

Generate real random secrets with documented commands, never provide example values:

```bash
# Generate a secure JWT secret:
openssl rand -hex 32
# or:
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4.3 Example data

Example JSON in API docs must use **obviously fake** data:

```json
{
  "email": "user@example.com",
  "username": "Alice"
}
```

Never use real names, real email addresses, or real UUIDs from production systems.

### 4.4 Paths in examples

Use project-relative paths or generic placeholders:

```bash
# Good
storage/voice_models/{user_id}/{voice_id}/

# Bad — never use absolute paths
C:\Users\alice\project\storage\voice_models\
/home/alice/voice-chat-assistant/storage/
```

### 4.5 Sensitive configuration

When documenting `.env` variables:

- Document **what the variable does**, not what the value should be.
- Link to `.env.example` as the canonical reference.
- Mark variables as Required / Optional / Production-only clearly.

---

## 5. Document Templates

### 5.1 README Template

Every README (root-level or for a major sub-module) must follow this structure:

```markdown
# Project Name

[中文](README.zh.md) | **English**   ← language toggle (root README only)

> One-sentence project description.

[Badges]

---

## Overview

What does this project do? Where does it fit in the larger system?
Include a Mermaid diagram if there are external dependencies or a pipeline.

---

## Features

Bulleted list of major features. Each bullet: **Bold label** — description.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| ...   | ...        |

---

## Prerequisites

| Requirement | Version / Notes |
|------------|-----------------|
| ...         | ...             |

---

## Quick Start

Numbered steps. Each step is an H3 heading with code blocks.
Steps must be copy-paste executable without modification (except .env values).

---

## Directory Structure

Annotated tree. Keep it to one level of depth per directory.

---

## Documentation

Table linking to all docs/ files with one-line descriptions.

---

## Related Projects / Links

Links to companion repositories.

---

## License

License name © Author
```

### 5.2 API Reference Template

```markdown
# API Reference

> Version: vX.Y  ·  Base URL: `http://localhost:8000`

Auth header required on all protected endpoints:
​```
Authorization: Bearer <jwt_token>
​```

Interactive docs: http://localhost:8000/docs

---

## Table of Contents

[Auto-generated links to every endpoint]

---

## Section Name

### METHOD /api/path

One-line description. **Requires auth.** (if applicable)

**Request** (method and content-type):

​```json
{ "field": "value" }
​```

**Response** `STATUS Code`:

​```json
{ "field": "value" }
​```

**Error responses:**

| Status | Condition |
|--------|-----------|
| `400`  | reason    |
```

### 5.3 Guide Template

```markdown
# Guide Title

> **Audience:** [Who this guide is for]
> **Prerequisite:** [What the reader must have done first]

---

## Table of Contents

---

## Section 1

### Subsection 1.1

Step-by-step instructions with code blocks.

> **Warning:** Highlight important warnings.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| ...     | ...   | ... |
```

### 5.4 CHANGELOG Entry Format

Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

```markdown
## [Unreleased]

### Added
- New feature description (#PR or commit reference)

### Changed
- What changed and why

### Fixed
- Bug description — what symptom the user saw and what was fixed

### Security
- Security fix description (avoid disclosing exploit details before patching)

### Deprecated
- Feature or API being deprecated and migration path

### Removed
- What was removed and what to use instead
```

**Version bump rules:**

| Change type | Version bump |
|-------------|-------------|
| New feature, backward-compatible | MINOR (0.X.0) |
| Bug fix | PATCH (0.0.X) |
| Breaking API/config change | MAJOR (X.0.0) |
| Security fix | PATCH minimum, MINOR if behavior changes |

---

## 6. Bilingual Policy

| Document | English | Chinese |
|----------|---------|---------|
| `README.md` | Required | `README.zh.md` required, mirrors README.md |
| `ARCHITECTURE.md` | Required | Optional |
| `CHANGELOG.md` | Required | Optional |
| `CONTRIBUTING.md` | Required | Optional |
| `SECURITY.md` | Required | Optional |
| `docs/API.md` | Required | Optional |
| `docs/DEPLOY.md` | Required | Optional |
| `docs/DEVELOPMENT.md` | Required | Optional |
| `docs/VOICE_MODEL_IMPORT.md` | Required | Optional |

**When updating `README.md`, you must also update `README.zh.md`.** Both files must reflect the same information. The Chinese README may use more natural phrasing rather than a literal translation.

---

## 7. Update Workflow

### For every code change

1. Identify which documents are affected (use [Section 1](#1-document-inventory) as a checklist).
2. Update all affected documents in the **same commit** as the code change, or in the immediately following commit before the PR is merged.
3. Add a `CHANGELOG.md` entry under `[Unreleased]`.
4. Run the [Review Checklist](#8-review-checklist) before marking the PR ready for review.

### For releases

1. Move all `[Unreleased]` entries to a new version section in `CHANGELOG.md`.
2. Update version badges in `README.md` and `README.zh.md` if the version is displayed.
3. Tag the commit: `git tag -a v0.X.Y -m "Release v0.X.Y"`.

---

## 8. Review Checklist

Before submitting a PR, verify all applicable items:

**Content**
- [ ] All affected documents listed in Section 1 are updated
- [ ] CHANGELOG.md has a new entry under `[Unreleased]`
- [ ] README.md and README.zh.md are in sync
- [ ] New endpoints are documented in docs/API.md
- [ ] New config variables are documented in README quick-start table and .env.example
- [ ] New known issues or workarounds are added to docs/TROUBLESHOOTING.md

**Formatting**
- [ ] All code blocks have language identifiers
- [ ] All tables have header and separator rows
- [ ] Internal links point to correct headings (test with `#anchor` format)
- [ ] No trailing whitespace
- [ ] File ends with a single newline

**Security**
- [ ] No real API keys, tokens, or passwords
- [ ] No absolute file system paths containing usernames
- [ ] No personal email addresses or private information
- [ ] All placeholder values use `<angle-bracket>` format
- [ ] Example credentials are obviously fake (`user@example.com`, `Alice`)

**Accuracy**
- [ ] Command examples are copy-paste executable
- [ ] Port numbers match actual configuration
- [ ] File paths match actual project structure
- [ ] Version numbers in badges match `environment.yml` / `package.json`
