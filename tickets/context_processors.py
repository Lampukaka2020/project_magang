def notifications(request):
    if not request.user.is_authenticated:
        return {"unread_notification_count": 0}
    return {
        "unread_notification_count": request.user.ticket_notifications.filter(
            is_read=False
        ).count()
    }
