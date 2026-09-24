# Resend Email Provider

PyCRMKit `0.4.0b2` adds an adapter for the official Resend Python SDK while preserving the provider-neutral `EmailProvider` contract.

## Installation

Resend is optional:

```bash
pip install "pycrmkit[resend]"
```

The base `pip install pycrmkit` installation does not install or import the Resend SDK.

## Configuration

```python
from pycrmkit.providers.email.resend import ResendConfig, ResendEmailProvider

provider = ResendEmailProvider(
    ResendConfig(api_key="re_...")
)
```

`ResendConfig` does not expose the API key in its representation.

## Request mapping

The adapter maps `EmailMessage` to Resend's Send Email request:

- sender → `from`;
- recipients → `to`, retaining optional display names;
- subject → `subject`;
- text body → `text`;
- HTML body → `html`;
- PyCRMKit intent ID → `X-PyCRMKit-Intent-ID` header;
- idempotency key → Resend send options.

Generic CRM references and arbitrary Communication metadata are not forwarded automatically.

## Result mapping

A successful Resend response must contain an email `id`. PyCRMKit maps it to `provider_message_id` and records selected request/rate-limit response metadata when available.

Missing provider IDs are normalized as `resend.invalid_response`.

## Failure mapping

Resend SDK errors become failed `EmailProviderResult` values. The failure code derives from the provider error type, for example:

```text
resend.rate_limit_exceeded
resend.invalid_api_key
resend.http_client_error
```

Provider error message text is deliberately not persisted into metadata.

Client-side SDK `ValueError` failures are normalized as `resend.invalid_request`.

## SDK API-key isolation

The official synchronous SDK stores `api_key` at module level. PyCRMKit therefore serializes the set/send/restore sequence with a process-local lock and restores the previous SDK key after every call.

This prevents two `ResendEmailProvider` instances in the same process from accidentally leaving one another's key configured.

## Testing boundary

Ordinary CI never calls the live Resend API. Unit tests replace `resend.Emails.send` with controlled fakes.

Live account/domain/API-key validation is intentionally outside the mandatory release gate.
