from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .demo_accounts import try_resolve_studio_login


class CsrfCookieView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"detail": "ok", "csrfToken": get_token(request)})


class SessionLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.data
        if not isinstance(payload, dict) or not payload.get("email"):
            try:
                import json

                payload = json.loads(request.body.decode("utf-8") or "{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {}

        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password")
        if password is None:
            password = ""
        elif not isinstance(password, str):
            password = str(password)

        user = try_resolve_studio_login(email, password)
        if user is None:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        request.session.modified = True
        request.session.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "email": user.email,
                "role": user.role,
                "id": str(user.id),
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )


class SessionLogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def post(self, request):
        if request.user.is_authenticated:
            logout(request)
        return Response({"detail": "logged out"})


class SessionMeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"authenticated": False})
        return Response(
            {
                "authenticated": True,
                "email": request.user.email,
                "role": request.user.role,
                "id": str(request.user.id),
            }
        )


class AuthTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    authentication_classes = []
