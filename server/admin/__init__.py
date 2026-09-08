"""Operator-facing `/admin` portal: login + session, status, recordings review,
and manual deletes. Server-rendered HTML, gated by a signed cookie. The whole
portal is off unless ISAFAN_ADMIN_USER + ISAFAN_ADMIN_PASSWORD_HASH are set."""
