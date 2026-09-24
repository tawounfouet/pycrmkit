"""Concrete email provider adapters that do not require third-party SDKs."""

from pycrmkit.providers.email.smtp import SMTPConfig, SMTPEmailProvider, SMTPSecurity

__all__ = ["SMTPConfig", "SMTPEmailProvider", "SMTPSecurity"]
