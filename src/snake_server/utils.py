from __future__ import annotations

import secrets
import string


_INVITE_CODE_CHARACTERS = list(
    set(string.ascii_letters + string.digits) - set("01iIlLoO")
)


def generate_invite_code() -> str:
    return "".join(secrets.choice(_INVITE_CODE_CHARACTERS) for _ in range(4))
