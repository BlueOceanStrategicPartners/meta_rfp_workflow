from django.apps import AppConfig


class DynamicPricingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dynamic_pricing"
    label = "dynamic_pricing"
