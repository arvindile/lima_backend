import os
import smtplib
from email.mime.text import MIMEText

# Uses Gmail's SMTP server with an "app password" — not your real Gmail
# password. Generate one at myaccount.google.com/apppasswords (requires
# 2-Step Verification turned on for the Gmail account first). Uses
# smtplib/email from Python's standard library, so no new package is
# needed for this.
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")  # e.g. limachatsupport@gmail.com
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

RESET_CODE_EXPIRY_MINUTES = 15


def send_password_reset_email(to_email: str, code: str) -> bool:
    """
    Sends the 6-digit reset code to to_email. Returns True on success,
    False if email sending isn't configured or the send fails.

    Callers should NOT treat a False return as fatal to the request —
    /auth/forgot-password always responds the same way regardless of
    whether the email exists or sending succeeded, so this endpoint can't
    be used to find out which emails have LIMA accounts.
    """
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD):
        print("WARNING: GMAIL_ADDRESS/GMAIL_APP_PASSWORD not set — cannot send reset emails.")
        return False

    msg = MIMEText(
        f"Your LIMA password reset code is: {code}\n\n"
        f"This code expires in {RESET_CODE_EXPIRY_MINUTES} minutes. "
        "If you didn't request this, you can safely ignore this email.",
    )
    msg["Subject"] = "Your LIMA password reset code"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
        return False
