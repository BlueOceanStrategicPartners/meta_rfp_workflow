"""Local demo studio credentials (Designer / Map Studio portals)."""

from django.conf import settings

from apps.accounts_rbac.models import CustomUser, UserRole

STUDIO_DEMO_EMAIL = "designer@demo.local"
STUDIO_DEMO_PASSWORD = "demo12345"


def ensure_studio_demo_user(*, reset_password: bool = False) -> CustomUser:
    """Create or refresh the local designer demo account."""
    user, created = CustomUser.objects.get_or_create(
        email=STUDIO_DEMO_EMAIL,
        defaults={
            "username": "designer",
            "role": UserRole.DESIGNER,
            "is_active": True,
        },
    )
    changed = created
    if user.role != UserRole.DESIGNER:
        user.role = UserRole.DESIGNER
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if reset_password or created or not user.has_usable_password():
        user.set_password(STUDIO_DEMO_PASSWORD)
        changed = True
    if changed:
        user.save()
    return user


def try_resolve_studio_login(email: str, password: str) -> CustomUser | None:
    """
    Return the user when email/password are valid.
    In DEBUG, auto-provision or reset the known demo account so local login works
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

    demo_email = STUDIO_DEMO_EMAIL
    demo_password = STUDIO_DEMO_PASSWORD
    if normalized != demo_email or password != demo_password:
        return None

    demo_user = ensure_studio_demo_user(reset_password=True)
    if demo_user.check_password(password):
        return demo_user
    return None
