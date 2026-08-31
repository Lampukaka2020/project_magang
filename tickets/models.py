import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

#Table Kategori Gangguan atau Permintaan Layanan
class Category(models.Model):
    TYPE_CHOICES = [
        ("INCIDENT", "Gangguan"),
        ("SERVICE_REQUEST", "Permintaan Layanan"),
    ]

    name = models.CharField(max_length=100)

    ticket_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="INCIDENT",
    )

    def __str__(self):
        return f"{self.name} ({self.get_ticket_type_display()})"

#Table untuk menyimpan data tiket yang dibuat oleh pegawai
class Ticket(models.Model):
    """Model Utama untuk Tiket ITSM"""
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    STATUS_CHOICES = [
        ('OPEN', 'Open (Terdaftar)'),
        ('IN_PROGRESS', 'In Progress (Dalam Penanganan)'),
        ('RESOLVED', 'Resolved (Selesai Penanganan)'),
        ('CLOSED', 'Closed (Ditutup)'),
    ]

    # Nomor Tiket Otomatis
    ticket_number = models.CharField(max_length=25, unique=True, editable=False)
    
    # Relasi Database
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_tickets')
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    
    # Detail Masalah (Upload File Attachment)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    attachment = models.ImageField(upload_to='ticket_attachments/', blank=True, null=True)
    
    # Atribut Operasional IT
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPEN')
    
    # Pelacakan SLA & Waktu
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Generasi Nomor Tiket Unik Otomatis (Format: TKT-YYYYMMDD-XXXX)
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            today = timezone.now().strftime('%Y%m%d')
            random_code = str(uuid.uuid4().hex[:4]).upper()
            self.ticket_number = f"TKT-{today}-{random_code}"
            
        # Penyesuaian Otomatis Prioritas untuk Kategori Jaringan
        if self.category and 'jaringan' in self.category.name.lower() and self.priority == 'MEDIUM':
            self.priority = 'HIGH'

        #Menyimpan ke database
        super().save(*args, **kwargs)

    def __str__(self):  
        return f"[{self.ticket_number}] {self.subject}"

    #Menyimpan riwayat aktivitas tiket ke dalam TicketLog
class TicketLog(models.Model):
    """Pencatatan riwayat penanganan oleh 1 Agen IT"""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='logs')
    actor = models.ForeignKey(User, on_delete=models.CASCADE)
    action_note = models.TextField()
    status_changed_to = models.CharField(max_length=15, choices=Ticket.STATUS_CHOICES, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log {self.ticket.ticket_number} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    #Penilaian kepuasan layanan dari Pegawai setelah pekerjaan ditutup/selesai
class TicketFeedback(models.Model):
    """Ulasan kepuasan layanan dari Pegawai"""
    RATING_CHOICES = [(i, f"{i} Bintang") for i in range(1, 6)]
    
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='feedback')
    rating = models.IntegerField(choices=RATING_CHOICES)
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback {self.ticket.ticket_number} - {self.rating} Star"

    #Menyimpan notiffikasi untuk aktivitas tiket ke dalam Notification
class Notification(models.Model):
    """Notifikasi dalam aplikasi untuk aktivitas tiket."""

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ticket_notifications"
    )
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Notifikasi untuk {self.recipient.username}: {self.ticket.ticket_number}"
