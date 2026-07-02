# Security Policy

## Supported versions

This is an academic / portfolio project. Security fixes are applied to the latest
`main` branch only.

| Version | Supported |
| ------- | --------- |
| `main`  | ✅        |
| older tags | ❌     |

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report privately via one of:

- GitHub's **private vulnerability reporting** (repository → *Security* →
  *Report a vulnerability*), or
- email: **nawfal.razouk@enim.ac.ma**

Include a description, reproduction steps, affected component, and any suggested
remediation. You can expect an acknowledgement within a few days.

## Automated security measures in place

The project ships with a defence-in-depth supply-chain setup:

- **Dependency audit** — `pip-audit` in CI and Dependabot updates.
- **Static analysis** — CodeQL (`.github/workflows/codeql.yml`).
- **Container scanning** — Trivy image scan (`.github/workflows/trivy.yml`).
- **Signed releases** — images are built with an SBOM and provenance and signed
  with Cosign (`.github/workflows/release.yml`).

## Handling of secrets

No real secrets are committed. `.env.example` documents required variables with
placeholder values; supply real values via environment or a secret manager.
Generated TLS/SSH material is git-ignored.
