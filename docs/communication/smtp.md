# SMTP Email Provider

PyCRMKit `0.4.0b1` includes a concrete email adapter based only on Python's standard-library `smtplib`, `ssl`, and `email` packages.

## Configuration

```python
from pycrmkit.providers.email import SMTPConfig, SMTPEmailProvider, SMTPSecurity

provider = SMTPEmailProvider(
    SMTPConfig(
        host="smtp.example.com",
        port=587,
        security=SMTPSecurity.STARTTLS,
        username="user",
        password="secret",
    )
)
```

Supported connection modes are `plain`, `starttls`, and implicit `tls`.

## Message mapping

The adapter maps `EmailMessage` into a standard MIME message with:

- `From` and `To`;
- optional `Subject`;
- generated `Message-ID`;
- `X-PyCRMKit-Intent-ID`;
- optional `X-PyCRMKit-Idempotency-Key`;
- plain-text, HTML, or multipart alternative bodies.

The generated RFC Message-ID is returned as the SMTP adapter's `provider_message_id`.

## Failure mapping

Authentication, recipient rejection, sender rejection, connection errors, disconnects, timeouts, network errors, and generic SMTP failures are normalized into `EmailProviderResult(status="failed")` with typed failure codes.

Ordinary CI does not make live network calls. Adapter tests replace the SMTP client with controlled fakes.

## Partial recipient refusal

SMTP can accept some recipients while rejecting others. In that case PyCRMKit returns `accepted` because the transport accepted at least part of the submission, and records accepted/refused recipient counts in provider metadata. Per-recipient delivery history is deferred to the later Communication delivery-history milestone.
