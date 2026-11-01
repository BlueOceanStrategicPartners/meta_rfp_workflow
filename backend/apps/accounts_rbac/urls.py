from django.urls import path

from .views import (
    AuthTokenRefreshView,
    CsrfCookieView,
    SessionLoginView,
    SessionLogoutView,
    SessionMeView,
)

urlpatterns = [
    path("csrf/", CsrfCookieView.as_view()),
    path("login/", SessionLoginView.as_view()),
    path("logout/", SessionLogoutView.as_view()),
    path("me/", SessionMeView.as_view()),
    path("token/refresh/", AuthTokenRefreshView.as_view()),
]
