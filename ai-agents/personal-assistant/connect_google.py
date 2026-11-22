"""Connect your Google account (Calendar + Drive) — run once.

Needs google_credentials.json in this folder (see README.md, "Google setup").
A browser window opens; sign in and allow access. The login is saved to
google_token.json on this computer only.
"""

import sys

from integrations import GOOGLE_CLIENT_FILE, GOOGLE_SCOPES, GOOGLE_TOKEN_FILE


def main() -> None:
    if not GOOGLE_CLIENT_FILE.exists():
        sys.exit(f"Missing {GOOGLE_CLIENT_FILE.name}. Follow 'Google setup' in README.md first.")
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CLIENT_FILE), GOOGLE_SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    GOOGLE_TOKEN_FILE.write_text(creds.to_json())
    print("Google connected. Calendar and Drive actions are ready.")


if __name__ == "__main__":
    main()
