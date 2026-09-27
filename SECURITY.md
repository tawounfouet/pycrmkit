# Security Policy

## Reporting a vulnerability

Please do not disclose suspected security vulnerabilities in public issues before a coordinated fix is available.

Use GitHub's private security reporting facilities when available, or contact the repository owner through an appropriate private channel.

## Scope

PyCRMKit handles CRM data and therefore treats the following as security-sensitive:

- credentials and connection strings;
- webhook secrets and signatures;
- customer personal information;
- destructive merge/delete operations;
- external provider inputs;
- dependency vulnerabilities.

## V1 hardening baseline

The current V1 prerelease security baseline is documented in
[`Security & Privacy Hardening`](docs/security/privacy-hardening.md).

It includes privacy-safe public error serialization, secret-safe
representations, webhook HMAC/replay-age verification, audited webhook secret
rotation, explicit destructive-operation boundaries, merge safeguards and
event-payload minimization.

PyCRMKit does not provide application authentication/RBAC or transparent
database encryption. Embedding applications and operators remain responsible
for authorization, database encryption/access control, backup protection and
secure secret distribution.

## Supported versions

Before `1.0.0`, the latest stable development line is the primary supported
line, while V1 prereleases are qualification candidates. A formal post-1.0
support matrix will be published with the stable compatibility policy.
