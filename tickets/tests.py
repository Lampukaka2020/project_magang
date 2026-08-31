from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Category, Notification, Ticket, TicketFeedback, TicketLog


class TicketFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("pegawai", password="test-password")
        self.other_user = User.objects.create_user("pegawai-lain", password="test-password")
        self.staff = User.objects.create_user("agent", password="test-password", is_staff=True)
        self.category = Category.objects.create(name="Aplikasi", ticket_type="INCIDENT")
        self.service_category = Category.objects.create(
            name="Permintaan Akses", ticket_type="SERVICE_REQUEST"
        )
        self.ticket = Ticket.objects.create(
            reporter=self.user,
            category=self.category,
            subject="Aplikasi tidak dapat dibuka",
            description="Muncul pesan kesalahan saat login.",
        )

    def test_login_is_required(self):
        response = self.client.get(reverse("tickets:list"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('tickets:list')}")

    def test_new_user_can_register_as_regular_user(self):
        response = self.client.post(
            reverse("tickets:register"),
            {
                "username": "user-baru",
                "first_name": "User",
                "last_name": "Baru",
                "email": "user-baru@example.com",
                "password1": "PasswordBaru#2026",
                "password2": "PasswordBaru#2026",
            },
        )
        self.assertRedirects(response, reverse("login"))
        new_user = User.objects.get(username="user-baru")
        self.assertFalse(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertTrue(new_user.check_password("PasswordBaru#2026"))

    def test_duplicate_email_cannot_register(self):
        self.user.email = "pegawai@example.com"
        self.user.save()
        response = self.client.post(
            reverse("tickets:register"),
            {
                "username": "user-duplikat",
                "first_name": "User",
                "email": "PEGAWAI@example.com",
                "password1": "PasswordBaru#2026",
                "password2": "PasswordBaru#2026",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="user-duplikat").exists())

    def test_user_only_sees_own_tickets(self):
        Ticket.objects.create(
            reporter=self.other_user,
            category=self.category,
            subject="Tiket pengguna lain",
            description="Tidak boleh terlihat.",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("tickets:list"))
        self.assertContains(response, self.ticket.subject)
        self.assertNotContains(response, "Tiket pengguna lain")

    def test_create_ticket_assigns_logged_in_reporter(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("tickets:create"),
            {
                "category": self.category.pk,
                "subject": "Printer bermasalah",
                "description": "Kertas selalu tersangkut.",
                "priority": "MEDIUM",
            },
        )
        ticket = Ticket.objects.get(subject="Printer bermasalah")
        self.assertRedirects(response, reverse("tickets:detail", args=[ticket.pk]))
        self.assertEqual(ticket.reporter, self.user)
        self.assertTrue(ticket.ticket_number.startswith("TKT-"))
        self.assertTrue(TicketLog.objects.filter(ticket=ticket, actor=self.user).exists())
        self.assertTrue(Notification.objects.filter(ticket=ticket, recipient=self.staff).exists())

    def test_non_staff_cannot_update_ticket(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("tickets:update", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, 302)

    def test_regular_user_cannot_create_service_request(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("tickets:create"),
            {
                "category": self.service_category.pk,
                "subject": "Minta akses aplikasi",
                "description": "Permintaan layanan tidak diizinkan untuk pengguna biasa.",
                "priority": "MEDIUM",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].errors.as_data()["category"][0].code,
            "invalid_choice",
        )
        self.assertFalse(Ticket.objects.filter(subject="Minta akses aplikasi").exists())

    def test_staff_can_create_service_request(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("tickets:create"),
            {
                "category": self.service_category.pk,
                "subject": "Buat akun pegawai",
                "description": "Administrator memiliki akses ke seluruh jenis tiket.",
                "priority": "LOW",
            },
        )
        ticket = Ticket.objects.get(subject="Buat akun pegawai")
        self.assertRedirects(response, reverse("tickets:detail", args=[ticket.pk]))

    def test_staff_can_resolve_ticket_and_log_action(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("tickets:update", args=[self.ticket.pk]),
            {"status": "RESOLVED", "priority": "HIGH", "action_note": "Masalah diperbaiki."},
        )
        self.assertRedirects(response, reverse("tickets:detail", args=[self.ticket.pk]))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "RESOLVED")
        self.assertIsNotNone(self.ticket.resolved_at)
        self.assertTrue(TicketLog.objects.filter(ticket=self.ticket, actor=self.staff).exists())
        self.assertTrue(Notification.objects.filter(ticket=self.ticket, recipient=self.user).exists())

    def test_user_can_only_mark_own_notification_as_read(self):
        notification = Notification.objects.create(
            recipient=self.user, ticket=self.ticket, message="Tiket diperbarui."
        )
        self.client.force_login(self.other_user)
        response = self.client.post(reverse("tickets:notification_read", args=[notification.pk]))
        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_notification_read_rejects_get_request(self):
        notification = Notification.objects.create(
            recipient=self.user, ticket=self.ticket, message="Tiket diperbarui."
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("tickets:notification_read", args=[notification.pk])
        )
        self.assertEqual(response.status_code, 405)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_user_can_read_notification_and_open_ticket_detail(self):
        notification = Notification.objects.create(
            recipient=self.user,
            ticket=self.ticket,
            message="Tiket diperbarui.",
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("tickets:notification_read", args=[notification.pk])
        )
        self.assertRedirects(
            response,
            reverse("tickets:detail", args=[self.ticket.pk]),
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_user_cannot_open_another_users_ticket(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("tickets:detail", args=[self.ticket.pk]))
        self.assertEqual(response.status_code, 404)

    def test_reporter_can_submit_feedback_after_ticket_is_resolved(self):
        self.ticket.status = "RESOLVED"
        self.ticket.save()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("tickets:feedback", args=[self.ticket.pk]),
            {"rating": 5, "comments": "Pelayanan sangat baik."},
        )
        self.assertRedirects(response, reverse("tickets:detail", args=[self.ticket.pk]))
        feedback = TicketFeedback.objects.get(ticket=self.ticket)
        self.assertEqual(feedback.rating, 5)
        self.assertTrue(
            Notification.objects.filter(ticket=self.ticket, recipient=self.staff).exists()
        )

    def test_feedback_is_rejected_before_ticket_is_resolved(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("tickets:feedback", args=[self.ticket.pk]),
            {"rating": 4, "comments": "Belum selesai."},
        )
        self.assertRedirects(response, reverse("tickets:detail", args=[self.ticket.pk]))
        self.assertFalse(TicketFeedback.objects.filter(ticket=self.ticket).exists())

    def test_other_user_and_staff_cannot_submit_feedback(self):
        self.ticket.status = "RESOLVED"
        self.ticket.save()
        feedback_url = reverse("tickets:feedback", args=[self.ticket.pk])
        for user in (self.other_user, self.staff):
            self.client.force_login(user)
            response = self.client.post(feedback_url, {"rating": 5, "comments": "Tidak sah."})
            self.assertEqual(response.status_code, 404)
        self.assertFalse(TicketFeedback.objects.filter(ticket=self.ticket).exists())

    def test_feedback_can_only_be_submitted_once(self):
        self.ticket.status = "CLOSED"
        self.ticket.save()
        TicketFeedback.objects.create(ticket=self.ticket, rating=4, comments="Sudah dinilai.")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("tickets:feedback", args=[self.ticket.pk]),
            {"rating": 1, "comments": "Penilaian kedua."},
        )
        self.assertRedirects(response, reverse("tickets:detail", args=[self.ticket.pk]))
        self.assertEqual(TicketFeedback.objects.filter(ticket=self.ticket).count(), 1)
