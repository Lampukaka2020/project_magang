from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from .models import Category, Ticket, TicketLog, Notification


class TicketCreationTest(TestCase):
    def setUp(self):
        # Reporter (user biasa) and two staff users
        self.reporter = User.objects.create_user(username='reporter', password='pass')
        self.staff1 = User.objects.create_user(username='staff1', password='pass', is_staff=True)
        self.staff2 = User.objects.create_user(username='staff2', password='pass', is_staff=True)

        # Category for INCIDENT (doesn't contain "jaringan" so priority stays as sent)
        self.category = Category.objects.create(name='Email', ticket_type='INCIDENT')

    def test_ticket_creation_creates_ticket_log_and_notifications(self):
        self.client.force_login(self.reporter)
        data = {
            'category': self.category.pk,
            'subject': 'Test subject',
            'description': 'Detailed description',
            'priority': 'MEDIUM',
        }
        response = self.client.post(reverse('tickets:create'), data)
        # should redirect to detail page after successful creation
        self.assertEqual(response.status_code, 302)

        ticket = Ticket.objects.get(subject='Test subject')
        self.assertEqual(ticket.reporter, self.reporter)

        # TicketLog was created with expected action note
        logs = TicketLog.objects.filter(ticket=ticket)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().action_note, 'Tiket dibuat.')

        # Notifications created for each active staff user
        notifs = Notification.objects.filter(ticket=ticket)
        self.assertEqual(notifs.count(), 2)
        recipients = set(n.recipient for n in notifs)
        self.assertIn(self.staff1, recipients)
        self.assertIn(self.staff2, recipients)

    def test_ticket_number_format(self):
        self.client.force_login(self.reporter)
        data = {
            'category': self.category.pk,
            'subject': 'Number format',
            'description': 'desc',
            'priority': 'MEDIUM',
        }
        self.client.post(reverse('tickets:create'), data)
        ticket = Ticket.objects.get(subject='Number format')

        # Expected format: TKT-YYYYMMDD-XXXX (XXXX are hex uppercase characters)
        import re

        pattern = r'^TKT-\d{8}-[0-9A-F]{4}$'
        self.assertRegex(ticket.ticket_number, pattern)
