from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification_read"),
    path("notifications/read-all/", views.notification_read_all, name="notification_read_all"),
    path("", views.ticket_list, name="list"),
    path("tickets/new/", views.ticket_create, name="create"),
    path("tickets/<int:pk>/", views.ticket_detail, name="detail"),
    path("tickets/<int:pk>/update/", views.ticket_update, name="update"),
    path("tickets/<int:pk>/feedback/", views.ticket_feedback, name="feedback"),
]
