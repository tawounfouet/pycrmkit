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

## Supported versions

Before `1.0.0`, the latest stable development line is the primary supported line. A formal post-1.0 support matrix will be published with the stable compatibility policy.
