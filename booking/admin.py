from django.contrib import admin
from .models import Court, TimeSlot, Booking, BookingHistory
from authentication.models import CustomUser
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Admin for custom user model."""
    list_display = ('username', 'email', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('-date_joined',)


@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ('name', 'hourly_rate', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('-created_at',)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('start_time', 'end_time', 'is_active')
    list_filter = ('is_active',)
    ordering = ('start_time',)
    search_fields = ('start_time', 'end_time')  # Required for autocomplete


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'booking_id', 'player_name', 'contact_number', 'court',
        'booking_date', 'time_slot', 'status', 'total_amount'
    )
    list_filter = ('status', 'booking_date', 'court')
    search_fields = ('player_name', 'contact_number', 'booking_id')
    readonly_fields = ('total_amount', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'booking_date'
    autocomplete_fields = ['court', 'time_slot', 'user']  # ✅ Uses CustomUser


@admin.register(BookingHistory)
class BookingHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'booking', 'previous_status', 'new_status',
        'changed_by', 'changed_at'
    )
    list_filter = ('previous_status', 'new_status', 'changed_at')
    search_fields = ('booking__booking_id', 'changed_by__username')
    ordering = ('-changed_at',)
    autocomplete_fields = ['booking', 'changed_by'] 
