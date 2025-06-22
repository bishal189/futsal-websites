# forms.py
from django import forms
from django.core.validators import RegexValidator
from .models import Booking, Court, TimeSlot
from datetime import date

class BookingForm(forms.ModelForm):
    """Form for creating bookings"""
    
    phone_regex = RegexValidator(
        regex=r'^(\+977)?[9][6-9]\d{8}$',
        message="Phone number must be entered in the format: '9841234567' or '+9779841234567'"
    )
    
    player_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'input-field w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
            'placeholder': 'Enter your full name',
            'required': True
        }),
        label='Full Name'
    )
    
    contact_number = forms.CharField(
        validators=[phone_regex],
        max_length=17,
        widget=forms.TextInput(attrs={
            'class': 'input-field w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
            'placeholder': '9841234567',
            'required': True
        }),
        label='Phone Number'
    )
    
    booking_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'input-field w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
            'min': date.today().isoformat(),
            'required': True
        }),
        label='Booking Date'
    )
    
    court = forms.ModelChoiceField(
        queryset=Court.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'input-field w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
            'required': True
        }),
        label='Select Court'
    )
    
    time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'input-field w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
            'required': True
        }),
        label='Select Time Slot'
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'input-field w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
            'placeholder': 'Any special requests or notes...',
            'rows': 3
        }),
        label='Additional Notes'
    )

    class Meta:
        model = Booking
        fields = ['court', 'booking_date', 'time_slot', 'player_name', 'contact_number', 'notes']

    def clean_booking_date(self):
        """Validate that booking date is not in the past"""
        booking_date = self.cleaned_data.get('booking_date')
        if booking_date and booking_date < date.today():
            raise forms.ValidationError("Cannot book for past dates.")
        return booking_date

    def clean(self):
        """Additional validation for the entire form"""
        cleaned_data = super().clean()
        court = cleaned_data.get('court')
        booking_date = cleaned_data.get('booking_date')
        time_slot = cleaned_data.get('time_slot')

        # Check if the time slot is already booked
        if court and booking_date and time_slot:
            existing_booking = Booking.objects.filter(
                court=court,
                booking_date=booking_date,
                time_slot=time_slot,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if existing_booking:
                raise forms.ValidationError("This time slot is already booked. Please select a different time.")

        return cleaned_data


class BookingSearchForm(forms.Form):
    """Form for searching bookings"""
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='From Date'
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='To Date'
    )
    
    court = forms.ModelChoiceField(
        queryset=Court.objects.filter(is_active=True),
        required=False,
        empty_label="All Courts",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Court'
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Booking.BOOKING_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Status'
    )
    
    player_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by player name...'
        }),
        label='Player Name'
    )


class TimeSlotForm(forms.ModelForm):
    """Form for creating/editing time slots"""
    
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control'
        }),
        label='Start Time'
    )
    
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'form-control'
        }),
        label='End Time'
    )

    class Meta:
        model = TimeSlot
        fields = ['start_time', 'end_time', 'is_active']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def clean(self):
        """Validate that end time is after start time"""
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time:
            if end_time <= start_time:
                raise forms.ValidationError("End time must be after start time.")

        return cleaned_data


class CourtForm(forms.ModelForm):
    """Form for creating/editing courts"""
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter court name'
        }),
        label='Court Name'
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter court description...',
            'rows': 3
        }),
        label='Description'
    )
    
    hourly_rate = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '1000.00',
            'step': '0.01'
        }),
        label='Hourly Rate (NPR)'
    )

    class Meta:
        model = Court
        fields = ['name', 'description', 'hourly_rate', 'is_active']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }