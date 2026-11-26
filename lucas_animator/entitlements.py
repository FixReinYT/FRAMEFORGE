"""Subscription boundary for FRAMEFORGE.

No payment provider is configured in this release. The service therefore never
pretends that a checkout or PRO entitlement succeeded. A real provider can be
injected later and must verify signed server-side entitlements.
"""

class BillingUnavailable(RuntimeError):
    pass


PRO_FEATURES = (
    {
        "id": "pro_filters",
        "title": "Пакет художественных фильтров",
        "description": "Glow, Duotone и Film Grain с настройкой интенсивности.",
    },
)


class BillingProvider:
    """Provider contract. Implementations must validate purchases server-side."""

    def begin_checkout(self, account):
        raise BillingUnavailable("Платёжный провайдер не настроен.")

    def open_subscription_management(self, account):
        raise BillingUnavailable("Управление подпиской пока недоступно.")

    def has_entitlement(self, account, feature_id):
        return False


class EntitlementService:
    def __init__(self, provider=None):
        self.provider = provider

    def has(self, feature_id, account=None):
        if self.provider is None or account is None:
            return False
        try:
            return bool(self.provider.has_entitlement(account, feature_id))
        except Exception:
            return False

    def begin_checkout(self, account=None):
        if self.provider is None:
            raise BillingUnavailable("Покупка FRAMEFORGE PRO пока недоступна: платёжная система не подключена.")
        return self.provider.begin_checkout(account)

    def manage_subscription(self, account=None):
        if self.provider is None:
            raise BillingUnavailable("Управление подпиской пока недоступно: платёжная система не подключена.")
        return self.provider.open_subscription_management(account)
