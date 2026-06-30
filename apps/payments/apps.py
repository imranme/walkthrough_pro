# from django.apps import AppConfig


# class PaymentsConfig(AppConfig):
#     name               = "apps.payments"
#     label              = "payments"
#     verbose_name       = "WalkthroughPro – Payments & Subscriptions"
#     default_auto_field = "django.db.models.BigAutoField"

#     def ready(self):
#         import logging
#         from django.conf import settings
#         logger = logging.getLogger(__name__)

#         missing = []
#         for key in ("STRIPE_SECRET_KEY", "STRIPE_PRO_PRICE_ID", "STRIPE_WEBHOOK_SECRET"):
#             if not getattr(settings, key, ""):
#                 missing.append(key)

#         if missing:
#             logger.warning(
#                 "[payments] Missing Stripe config: %s — "
#                 "billing endpoints will return 503.",
#                 ", ".join(missing),
#             ) 


from django.apps import AppConfig

class PaymentsConfig(AppConfig):
    name               = "apps.payments"
    label              = "payments"
    verbose_name       = "WalkthroughPro – Payments & Subscriptions"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import logging
        from django.conf import settings
        logger = logging.getLogger(__name__)

        missing = []
        for key in ("STRIPE_SECRET_KEY", "STRIPE_PRO_PRICE_ID", "STRIPE_WEBHOOK_SECRET"):
            if not getattr(settings, key, ""):
                missing.append(key)

        if missing:
            logger.warning(
                "[payments] Missing Stripe config: %s — "
                "billing endpoints will return 503.",
                ", ".join(missing),
            )