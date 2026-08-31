from django.contrib import admin
from .models import Category, Notification, Ticket, TicketLog, TicketFeedback

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'ticket_type')
    list_filter = ('ticket_type',)

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'subject', 'reporter', 'category', 'priority', 'status', 'created_at')
    list_filter = ('status', 'priority', 'category')
    search_fields = ('ticket_number', 'subject', 'description')

admin.site.register(TicketLog)
@admin.register(TicketFeedback)
class TicketFeedbackAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('ticket__ticket_number', 'ticket__subject', 'comments')
    readonly_fields = ('ticket', 'rating', 'comments', 'created_at')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'ticket', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('recipient__username', 'ticket__ticket_number', 'message')
