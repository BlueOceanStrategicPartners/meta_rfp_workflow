from django.urls import path

from .views import CardMutationView

urlpatterns = [
    path("mutate/", CardMutationView.as_view()),
]
