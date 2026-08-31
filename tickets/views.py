from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import FeedbackForm, RegistrationForm, TicketForm, TicketUpdateForm
from .models import Notification, Ticket, TicketLog

#Pendaftaran akun baru untuk pegawai
@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("tickets:list")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Akun berhasil dibuat. Silakan masuk.")
        return redirect("login")
    return render(request, "registration/register.html", {"form": form})

#Nofikasi untuk pegawai yang sudah login, menampilkan daftar notifikasi tiket yang diterima, menandai notifikasi sebagai sudah dibaca, dan menandai semua notifikasi sebagai sudah dibaca.
@login_required
@require_GET
def notification_list(request):
    notifications = request.user.ticket_notifications.select_related("ticket")
    return render(request, "tickets/notification_list.html", {"notifications": notifications})

#menandai notifikasi sebagai sudah dibaca dan mengarahkan pengguna ke detail tiket terkait.
@login_required
@require_POST
def notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return redirect("tickets:details", pk=notification.ticket_id)

#menandai semua notifikasi yang belum dibaca sebagai sudah dibaca dan mengarahkan pengguna ke daftar notifikasi.
@login_required
@require_POST
def notification_read_all(request):
    request.user.ticket_notifications.filter(is_read=False).update(is_read=True)
    return redirect("tickets:notifications")


def _ticket_for_user(user, pk):
    queryset = Ticket.objects.select_related("reporter", "category")
    if not user.is_staff:
        queryset = queryset.filter(reporter=user)
    return get_object_or_404(queryset, pk=pk)


@login_required
@require_GET
def ticket_list(request):
    tickets = Ticket.objects.select_related("reporter", "category")
    if not request.user.is_staff:
        tickets = tickets.filter(reporter=request.user)

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        tickets = tickets.filter(
            Q(ticket_number__icontains=query)
            | Q(subject__icontains=query)
            | Q(description__icontains=query)
        )
    if status in dict(Ticket.STATUS_CHOICES):
        tickets = tickets.filter(status=status)

    context = {
        "tickets": tickets.order_by("-created_at"),
        "status_choices": Ticket.STATUS_CHOICES,
        "query": query,
        "selected_status": status,
    }
    return render(request, "tickets/ticket_list.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def ticket_create(request):
    form = TicketForm(request.POST or None, request.FILES or None,)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.reporter = request.user
        ticket.save()
        TicketLog.objects.create(
            ticket=ticket,
            
            actor=request.user,
            action_note="Tiket dibuat.",
            status_changed_to=ticket.status,
        )
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        Notification.objects.bulk_create([
            Notification(
                recipient=staff,
                ticket=ticket,
                message=f"Tiket baru {ticket.ticket_number} dibuat oleh {request.user.username}.",
            )
            for staff in staff_users
            if staff.pk != request.user.pk
        ])
        messages.success(request, f"Tiket {ticket.ticket_number} berhasil dibuat.")
        return redirect("tickets:details", pk=ticket.pk)
    return render(request, "tickets/ticket_form.html", {"form": form})


@login_required
@require_GET
def ticket_detail(request, pk):
    ticket = _ticket_for_user(request.user, pk)
    return render(request, "tickets/ticket_detail.html", {"ticket": ticket})


@login_required
@user_passes_test(lambda user: user.is_staff)
@require_http_methods(["GET", "POST"])
def ticket_update(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    old_status = ticket.status
    form = TicketUpdateForm(request.POST or None, instance=ticket)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        if ticket.status == "RESOLVED" and old_status != "RESOLVED":
            ticket.resolved_at = timezone.now()
        elif ticket.status not in ("RESOLVED", "CLOSED"):
            ticket.resolved_at = None
        ticket.save()
        TicketLog.objects.create(
            ticket=ticket,
            actor=request.user,
            action_note=form.cleaned_data["action_note"],
            status_changed_to=ticket.status if old_status != ticket.status else None,
        )
        Notification.objects.create(
            recipient=ticket.reporter,
            ticket=ticket,
            message=f"Tiket {ticket.ticket_number} diperbarui: {ticket.get_status_display()}.",
        )
        messages.success(request, "Penanganan tiket berhasil diperbarui.")
        return redirect("tickets:details", pk=ticket.pk)
    return render(request, "tickets/ticket_update.html", {"form": form, "ticket": ticket})


@login_required
@require_http_methods(["GET", "POST"])
def ticket_feedback(request, pk):
    # Feedback hanya boleh dikirim oleh pengguna yang membuat tiket.
    ticket = get_object_or_404(
        Ticket.objects.select_related("reporter", "category"),
        pk=pk,
        reporter=request.user,
    )
    if ticket.status not in ("RESOLVED", "CLOSED"):
        messages.warning(
            request,
            "Feedback hanya dapat diberikan setelah tiket selesai atau ditutup.",
        )
        return redirect("tickets:details", pk=ticket.pk)
    if hasattr(ticket, "feedback"):
        messages.info(request, "Feedback untuk tiket ini sudah pernah diberikan.")
        return redirect("tickets:detail", pk=ticket.pk)

    form = FeedbackForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        feedback = form.save(commit=False)
        feedback.ticket = ticket
        feedback.save()
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        Notification.objects.bulk_create([
            Notification(
                recipient=staff,
                ticket=ticket,
                message=(
                    f"{request.user.username} memberi feedback "
                    f"{feedback.rating} bintang untuk {ticket.ticket_number}."
                ),
            )
            for staff in staff_users
        ])
        messages.success(request, "Terima kasih atas feedback Anda.")
        return redirect("tickets:detail", pk=ticket.pk)
    return render(request, "tickets/feedback_form.html", {"form": form, "ticket": ticket})
