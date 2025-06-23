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
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count



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
                'end_time': slot.end_time.strftime('%H:%M'),
                'is_booked': slot.start_time in booked_slots,
               'display_time': slot.start_time.strftime('%I:%M %p').lstrip('0') 

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
        booking_page_url = f"/booking/?court_id={court_id}&date={booking_date}&time_slot_id={time_slot_id}"

        
        if not all([booking_date, time_slot_id, player_name, contact_number]):
            return JsonResponse({'error': 'All required fields must be provided'}, status=400)


        if not request.user.is_authenticated:
            return JsonResponse({
                'error': 'Authentication required',
                'redirect_to': f"/login/?next={booking_page_url}"
            }, status=401)
        # Parse and validate date
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)
        
        if booking_date < date.today():
            return JsonResponse({'error': 'Cannot book for past dates'}, status=400)

        court = get_object_or_404(Court, id=court_id, is_active=True)
        time_slot = get_object_or_404(TimeSlot, id=time_slot_id, is_active=True)

        existing_booking = Booking.objects.filter(
            court=court,
            booking_date=booking_date,
            time_slot=time_slot,
            status__in=['pending', 'confirmed']
        ).first()
        if existing_booking:
            return JsonResponse({'error': 'This time slot is already booked'}, status=400)

        # Determine if user should get this hour for free
        user = request.user if request.user.is_authenticated else None
        is_free = False

        if user:
            current_points = user.reward_points
            if current_points > 0 and current_points % 11 == 0:
                is_free = True

        # Create booking
        booking = Booking.objects.create(
            court=court,
            booking_date=booking_date,
            time_slot=time_slot,
            player_name=player_name,
            contact_number=contact_number,
            user=user,
            notes=notes,
            status='confirmed',
            total_amount=0 if is_free else None  # Will auto-calculate in model if not free
        )

        # Create booking history
        BookingHistory.objects.create(
            booking=booking,
            previous_status='',
            new_status='confirmed',
            changed_by=user,
            change_reason='Initial booking creation'
        )

        # Update reward points
        if user:
            user.reward_points += 1
            user.save()

        return JsonResponse({
            'success': True,
            'booking_id': str(booking.booking_id),
            'free_hour_used': is_free,
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
    print(booking,'booking')
    
    context = {
        'booking': booking,
    }
    return render(request, 'booking/confirm.html', context)

@login_required(login_url='login')
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')

    # Aggregations
    totals = bookings.aggregate(
        total_bookings=Count('id'),
        total_hours=Sum('duration_hours'),
        total_cost=Sum('total_amount')
    )

    completed_bookings = bookings.filter(status='confirmed')
    cancelled_bookings = bookings.filter(status='cancelled')
    reward_points = request.user.reward_points or 0

    context = {

        'bookings': bookings,
        'total_bookings': totals['total_bookings'] or 0,
        'total_hours': totals['total_hours'] or 0,
        'total_cost': totals['total_cost'] or 0.00,
        'reward_points': reward_points,
        'free_games_earned': reward_points// 11,
        "completed_bookings":completed_bookings,
        'cancelled_bookings': cancelled_bookings,
}

    return render(request, 'home/dashboard.html', context)


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