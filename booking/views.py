# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime, date, timedelta
import json
from .models import Court, TimeSlot, Booking, BookingHistory
from .forms import BookingForm

def booking_page(request):
    """Main booking page view"""
    courts = Court.objects.filter(is_active=True)
    time_slots = TimeSlot.objects.filter(is_active=True)
    
    context = {
        'courts': courts,
        'time_slots': time_slots,
        'today': date.today(),
    }
    return render(request, 'booking/booking.html', context)

@require_http_methods(["GET"])
def get_available_slots(request):
    """AJAX endpoint to get available time slots for a specific date and court"""
    try:
        booking_date = request.GET.get('date')
        court_id = request.GET.get('court_id', 1)  # Default to first court
        
        if not booking_date:
            return JsonResponse({'error': 'Date is required'}, status=400)
        
        # Parse date
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
        
        # Check if date is not in the past
        if booking_date < date.today():
            return JsonResponse({'error': 'Cannot book for past dates'}, status=400)
        
        court = get_object_or_404(Court, id=court_id, is_active=True)
        
        # Get all time slots
        all_slots = TimeSlot.objects.filter(is_active=True)
        
        # Get booked slots for this date and court
        booked_slots = Booking.get_booked_slots(booking_date, court)
        
        # Prepare response data
        slots_data = []
        for slot in all_slots:
            slots_data.append({
                'id': slot.id,
                'start_time': slot.start_time.strftime('%H:%M'),
                'is_booked': slot.start_time in booked_slots,
                'display_time': slot.start_time.strftime('%H:%M')  # Optional display label
            })
        
        return JsonResponse({
            'success': True,
            'slots': slots_data,
            'court_name': court.name,
            'hourly_rate': float(court.hourly_rate)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def create_booking(request):
    """Handle booking creation"""
    try:
        data = json.loads(request.body)
        
        # Extract data
        court_id = data.get('court_id', 1)
        booking_date = data.get('date')
        time_slot_id = data.get('time_slot_id')
        player_name = data.get('player_name')
        contact_number = data.get('contact_number')
        notes = data.get('notes', '')
        
        # Validate required fields
        if not all([booking_date, time_slot_id, player_name, contact_number]):
            return JsonResponse({'error': 'All required fields must be provided'}, status=400)
        
        # Parse date
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
        
        # Check if date is not in the past
        if booking_date < date.today():
            return JsonResponse({'error': 'Cannot book for past dates'}, status=400)
        
        # Get court and time slot
        court = get_object_or_404(Court, id=court_id, is_active=True)
        time_slot = get_object_or_404(TimeSlot, id=time_slot_id, is_active=True)
        
        # Check if slot is already booked
        existing_booking = Booking.objects.filter(
            court=court,
            booking_date=booking_date,
            time_slot=time_slot,
            status__in=['pending', 'confirmed']
        ).first()
        
        if existing_booking:
            return JsonResponse({'error': 'This time slot is already booked'}, status=400)
        
        # Create booking
        booking = Booking.objects.create(
            court=court,
            booking_date=booking_date,
            time_slot=time_slot,
            player_name=player_name,
            contact_number=contact_number,
            user=request.user if request.user.is_authenticated else None,
            notes=notes,
            status='confirmed'  # Auto-confirm for now
        )
        
        # Create history entry
        BookingHistory.objects.create(
            booking=booking,
            previous_status='',
            new_status='confirmed',
            changed_by=request.user if request.user.is_authenticated else None,
            change_reason='Initial booking creation'
        )
        
        return JsonResponse({
            'success': True,
            'booking_id': str(booking.booking_id),
            'message': 'Booking created successfully!',
            'booking_details': {
                'player_name': booking.player_name,
                'date': booking.booking_date.strftime('%Y-%m-%d'),
                'time': f"{booking.time_slot.start_time.strftime('%H:%M')} - {booking.time_slot.end_time.strftime('%H:%M')}",
                'court': booking.court.name,
                'total_amount': float(booking.total_amount)
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def booking_confirmation(request, booking_id):
    """Booking confirmation page"""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    context = {
        'booking': booking,
    }
    return render(request, 'booking/confirmation.html', context)

def my_bookings(request):
    """User's booking history"""
    if request.user.is_authenticated:
        bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    else:
        # For anonymous users, you might want to use session or phone number
        bookings = []
    
    context = {
        'bookings': bookings,
    }
    return render(request, 'booking/my_bookings.html', context)

@require_http_methods(["POST"])
def cancel_booking(request, booking_id):
    """Cancel a booking"""
    booking = get_object_or_404(Booking, booking_id=booking_id)
    
    # Check if user can cancel this booking
    if request.user.is_authenticated and booking.user != request.user:
        return JsonResponse({'error': 'You can only cancel your own bookings'}, status=403)
    
    # Check if booking can be cancelled (e.g., not in the past, not already cancelled)
    if booking.status == 'cancelled':
        return JsonResponse({'error': 'Booking is already cancelled'}, status=400)
    
    if booking.is_past:
        return JsonResponse({'error': 'Cannot cancel past bookings'}, status=400)
    
    # Update booking status
    old_status = booking.status
    booking.status = 'cancelled'
    booking.save()
    
    # Create history entry
    BookingHistory.objects.create(
        booking=booking,
        previous_status=old_status,
        new_status='cancelled',
        changed_by=request.user if request.user.is_authenticated else None,
        change_reason='Cancelled by user'
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Booking cancelled successfully!'
    })

def booking_calendar_data(request):
    """Get booking data for calendar view"""
    try:
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        court_id = request.GET.get('court_id')
        
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            bookings = Booking.objects.filter(
                booking_date__range=[start_date, end_date],
                status__in=['pending', 'confirmed']
            )
            
            if court_id:
                bookings = bookings.filter(court_id=court_id)
            
            events = []
            for booking in bookings:
                events.append({
                    'date': booking.booking_date.isoformat(),
                    'time_slots': [booking.time_slot.start_time.strftime('%H:%M')]
                })
            
            return JsonResponse({'events': events})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'events': []})