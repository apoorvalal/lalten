"""Set the upload password without placing plaintext in shell history or files."""

import getpass
import hashlib
from pathlib import Path


password = getpass.getpass("New Quomodoc upload password: ")
confirmation = getpass.getpass("Confirm password: ")
if not password or password != confirmation:
    raise SystemExit("Passwords did not match or were empty")

digest = hashlib.sha256(password.encode()).hexdigest()
Path("/etc/quomodoc.env").write_text(
    f"QUOMODOC_UPLOAD_PASSWORD_SHA256={digest}\n",
    encoding="utf-8",
)
Path("/etc/quomodoc.env").chmod(0o600)
print("Password verifier updated. Restart with: systemctl restart quomodoc")

