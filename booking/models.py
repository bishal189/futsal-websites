# models.py
from django.db import models
from  authentication.models import CustomUser
from django.core.validators import RegexValidator
from datetime import datetime, timedelta
import uuid

class Court(models.Model):
    """Model for futsal courts"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=1000.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Court"
        verbose_name_plural = "Courts"


class TimeSlot(models.Model):
    """Model for available time slots"""
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"

    class Meta:
        ordering = ['start_time']
        unique_together = ['start_time', 'end_time']


class Booking(models.Model):
    """Main booking model"""
    BOOKING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    # Booking identification
    booking_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Court and timing details
    court = models.ForeignKey(Court, on_delete=models.CASCADE, related_name='bookings')
    booking_date = models.DateField()
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='bookings')
    
    # Customer details
    player_name = models.CharField(max_length=100)
    phone_regex = RegexValidator(
        regex=r'^(\+977)?[9][6-9]\d{8}$',
        message="Phone number must be entered in the format: '9841234567' or '+9779841234567'"
    )
    contact_number = models.CharField(validators=[phone_regex], max_length=17)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')
    
    # Booking details
    duration_hours = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending')
    
    # Additional fields
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Auto-calculate total amount
        if not self.total_amount and self.court:
            self.total_amount = self.court.hourly_rate * self.duration_hours
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.player_name} - {self.booking_date} ({self.time_slot})"

    @property
    def booking_datetime(self):
        """Combine date and start time for easier sorting"""
        return datetime.combine(self.booking_date, self.time_slot.start_time)

    @property
    def end_datetime(self):
        """Calculate end datetime"""
        return datetime.combine(self.booking_date, self.time_slot.end_time)

    @property
    def is_past(self):
        """Check if booking is in the past"""
        return self.booking_datetime < datetime.now()

    @classmethod
    def get_booked_slots(cls, date, court=None):
        """Get all booked time slots for a specific date and court"""
        bookings = cls.objects.filter(
            booking_date=date,
            status__in=['pending', 'confirmed']
        )
        if court:
            bookings = bookings.filter(court=court)
        
        return bookings.values_list('time_slot__start_time', flat=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['court', 'booking_date', 'time_slot']
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"


class BookingHistory(models.Model):
    """Track booking status changes"""
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='history')
    previous_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    change_reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.booking.booking_id} - {self.previous_status} to {self.new_status}"

    class Meta:
        ordering = ['-changed_at']
        verbose_name = "Booking History"
        verbose_name_plural = "Booking Histories"