import jdatetime
from django.db.models import Q
from .models import SubscriptionHistory


def get_active_subscription(user):
    if not user or not user.is_authenticated:
        return None

    today = jdatetime.date.today()

    return (
        SubscriptionHistory.objects
        .filter(user_profile__user=user)
        .filter(
            Q(start_date__lte=today),
            Q(end_date__gte=today) | Q(end_date__isnull=True)
        )
        .select_related("subscription")
        .order_by("-start_date")
        .first()
    )


def user_has_stream_access(user):
    sub = get_active_subscription(user)
    if not sub:
        return False
    return sub.subscription.subscription_type in ["online", "both", "all"]


def user_has_download_access(user):
    sub = get_active_subscription(user)
    if not sub:
        return False
    return sub.subscription.subscription_type in ["download", "both", "all"]


def user_has_video_stream_access(user):
    sub = get_active_subscription(user)
    if not sub:
        return False
    return sub.subscription.subscription_type in ["videos", "all"]


def user_has_all_access(user):
    sub = get_active_subscription(user)
    if not sub:
        return False
    return sub.subscription.subscription_type == "all"
