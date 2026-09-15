import json
import os
import urllib.error
import urllib.request

# Render (like most PaaS platforms) blocks outbound SMTP ports (465/587)
# entirely, at the network level, to prevent the platform from being
# abused for spam. That's true for every app hosted there, not just this
# one, and there's no config change that gets around it — direct Gmail
# SMTP (smtplib) will never work from Render.
#
# The fix: send over HTTPS instead, via Brevo's transactional email API.
# HTTPS traffic isn't blocked the way raw SMTP is. Uses Python's built-in
# urllib rather than the `requests` package, so no new dependency is
# needed for this.
#
# Setup (once): sign up free at brevo.com (300 emails/day, no card
# needed), add EMAIL_FROM_ADDRESS as a verified sender there — Brevo
# emails a 6-digit code to that address to confirm you own it, no domain
# or DNS ownership required — then generate an API key under
# Settings -> SMTP & API -> API Keys.

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
# Reuses the GMAIL_ADDRESS env var as the "From" identity — same address
# as before, just no longer used for an SMTP login. Must be verified as a
# sender in Brevo's dashboard before sending will work.
EMAIL_FROM_ADDRESS = os.getenv("GMAIL_ADDRESS")

RESET_CODE_EXPIRY_MINUTES = 15

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


def send_password_reset_email(to_email: str, code: str) -> bool:
    """
    Sends the 6-digit reset code to to_email via Brevo. Returns True on
    success, False if sending isn't configured or the send fails.

    Callers should NOT treat a False return as fatal to the request —
    /auth/forgot-password always responds the same way regardless of
    whether the email exists or sending succeeded, so this endpoint can't
    be used to find out which emails have LIMA accounts.
    """
    if not (BREVO_API_KEY and EMAIL_FROM_ADDRESS):
        print("WARNING: BREVO_API_KEY/GMAIL_ADDRESS not set — cannot send reset emails.")
        return False

    payload = {
        "sender": {"email": EMAIL_FROM_ADDRESS, "name": "LIMA"},
        "to": [{"email": to_email}],
        "subject": "Your LIMA password reset code",
        "textContent": (
            f"Your LIMA password reset code is: {code}\n\n"
            f"This code expires in {RESET_CODE_EXPIRY_MINUTES} minutes. "
            "If you didn't request this, you can safely ignore this email."
        ),
    }

    request = urllib.request.Request(
        BREVO_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as e:
        # Brevo returned an error response (bad API key, unverified
        # sender, over quota, etc.) — log the body, since it usually says
        # exactly what's wrong.
        body = e.read().decode("utf-8", errors="replace")
        print(f"Brevo rejected the email send ({e.code}): {body}")
        return False
    except Exception as e:
        print(f"Failed to send password reset email via Brevo: {e}")
        return False
