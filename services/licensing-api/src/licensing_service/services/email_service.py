"""Server-side email notification service.

Handles dispatching license renewal alerts to configured vendor administrators.
Secrets and credentials remain strictly server-side in environment configuration.
"""

from email.message import EmailMessage
import logging
import smtplib
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from licensing_service.config import settings
from licensing_service.db.models import RenewalRequest
from licensing_service.services.setting_service import get_setting

logger = logging.getLogger("licensing_service.services.email_service")


def send_vendor_renewal_notification(
    db: Session,
    renewal: RenewalRequest,
) -> Tuple[bool, Optional[str]]:
    """Notify vendor administrator of a client license renewal request.

    Returns (success: bool, error_message: Optional[str]).
    Never leaks SMTP credentials in logs, return values, or audit events.
    """
    if not settings.SMTP_HOST:
        logger.info("SMTP_HOST not configured. Renewal request recorded for vendor portal review.")
        return False, "SMTP email provider not configured on server."

    recipient = get_setting(db, "vendor_notification_email", "vendor@apexhealth.local").strip()
    if not recipient:
        return False, "Vendor notification email address is not configured."

    try:
        msg = EmailMessage()
        msg["Subject"] = f"[MediHisaab] License Renewal Request: {renewal.store_name} ({renewal.requested_plan_code})"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = recipient

        body_lines = [
            "MediHisaab Central Licensing — Renewal Request Alert",
            "===================================================",
            "",
            f"A client has submitted a license renewal request from the desktop application:",
            "",
            f"Request ID:       #{renewal.id}",
            f"Store Name:       {renewal.store_name}",
            f"Client Code:      {renewal.client.client_code if renewal.client else 'N/A'}",
            f"Contact Person:   {renewal.contact_name}",
            f"Email Address:    {renewal.email}",
            f"Phone Number:     {renewal.phone}",
            f"Requested Plan:   {renewal.requested_plan_code}",
            f"Payment Ref (UTR): {renewal.payment_reference or 'Pending / None provided'}",
            f"Client Notes:     {renewal.notes or 'None'}",
            "",
            "Please review this renewal request in the Vendor Admin Portal to approve and generate a signed renewal license:",
            f"Portal URL:       https://licensing.apexhealth.com/vendor",
            "",
            "Note: This is an automated notification from MediHisaab Central Licensing Server.",
        ]
        msg.set_content("\n".join(body_lines))

        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        try:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
            logger.info("Renewal notification email sent to %s for request #%s", recipient, renewal.id)
            return True, None
        finally:
            server.quit()
    except Exception as exc:
        logger.warning("Failed to send renewal notification email: %s", exc)
        return False, f"Email delivery failed: {str(exc)}"
