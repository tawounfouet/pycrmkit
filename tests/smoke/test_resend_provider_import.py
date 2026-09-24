"""Smoke coverage for the optional Resend provider adapter."""

from pycrmkit.communication import EmailProvider
from pycrmkit.providers.email.resend import ResendConfig, ResendEmailProvider


def test_resend_provider_extra_imports() -> None:
    provider = ResendEmailProvider(ResendConfig(api_key="re_smoke"))

    assert isinstance(provider, EmailProvider)
    assert provider.config.provider_name == "resend"
