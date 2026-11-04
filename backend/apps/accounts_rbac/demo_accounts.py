"""Local demo studio credentials (Designer / Admin portals)."""

from django.conf import settings

from apps.accounts_rbac.models import CustomUser, UserRole

STUDIO_DEMO_EMAIL = "designer@demo.local"
STUDIO_DEMO_PASSWORD = "demo12345"

ADMIN_DEMO_EMAIL = "admin@demo.local"
ADMIN_DEMO_PASSWORD = "admin12345"

CLIENT_DEMO_EMAIL = "client@demo.local"
CLIENT_DEMO_PASSWORD = "demo12345"


def _ensure_demo_user(
    *, email: str, username: str, role: str, password: str, reset_password: bool
) -> CustomUser:
    user, created = CustomUser.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "role": role,
            "is_active": True,
        },
    )
    changed = created
    if user.role != role:
        user.role = role
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if reset_password or created or not user.has_usable_password():
        user.set_password(password)
        changed = True
    if changed:
        user.save()
    return user


def ensure_studio_demo_user(*, reset_password: bool = False) -> CustomUser:
    """Create or refresh the local designer demo account."""
    return _ensure_demo_user(
        email=STUDIO_DEMO_EMAIL,
        username="designer",
        role=UserRole.DESIGNER,
        password=STUDIO_DEMO_PASSWORD,
        reset_password=reset_password,
    )


def ensure_admin_demo_user(*, reset_password: bool = False) -> CustomUser:
    """Create or refresh the local admin demo account."""
    return _ensure_demo_user(
        email=ADMIN_DEMO_EMAIL,
        username="admin",
        role=UserRole.ADMIN,
        password=ADMIN_DEMO_PASSWORD,
        reset_password=reset_password,
    )


def ensure_client_demo_user(*, reset_password: bool = False) -> CustomUser:
    return _ensure_demo_user(
        email=CLIENT_DEMO_EMAIL,
        username="client",
        role=UserRole.CLIENT,
        password=CLIENT_DEMO_PASSWORD,
        reset_password=reset_password,
    )


DEMO_ACCOUNTS = {
    STUDIO_DEMO_EMAIL: (STUDIO_DEMO_PASSWORD, ensure_studio_demo_user),
    ADMIN_DEMO_EMAIL: (ADMIN_DEMO_PASSWORD, ensure_admin_demo_user),
    CLIENT_DEMO_EMAIL: (CLIENT_DEMO_PASSWORD, ensure_client_demo_user),
}


def try_resolve_studio_login(email: str, password: str) -> CustomUser | None:
    """
    Return the user when email/password are valid.
    In DEBUG, auto-provision or reset the known demo accounts so local login works
    without manually running seed_demo.
    """
    normalized = (email or "").strip().lower()
    if not normalized or password is None:
        return None

    user = CustomUser.objects.filter(email__iexact=normalized).first()
    if user is not None and user.check_password(password):
        return user

    if not settings.DEBUG:
        return None

    demo = DEMO_ACCOUNTS.get(normalized)
    if demo is None or password != demo[0]:
        return None

    demo_user = demo[1](reset_password=True)
    if demo_user.check_password(password):
        return demo_user
    return None
