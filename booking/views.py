# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime, date, timedelta
import json
from .models import Court, TimeSlot, Booking, BookingHistory,BookingCancellation
from .forms import BookingForm
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

# Set up logging for email debugging
logger = logging.getLogger(__name__)


# for downloads 
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.contrib.auth.decorators import login_required
from xhtml2pdf import pisa
from io import BytesIO
import os
from django.conf import settings
from django.utils import timezone


@login_required(login_url='/login/')
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
    """Handle booking creation with balance tracking and email confirmation"""
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
        
        # Validate required fields
        if not all([booking_date, time_slot_id, player_name, contact_number]):
            return JsonResponse({'error': 'All required fields must be provided'}, status=400)
        
        # Check authentication
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
        
        # Get court and time slot
        court = get_object_or_404(Court, id=court_id, is_active=True)
        time_slot = get_object_or_404(TimeSlot, id=time_slot_id, is_active=True)
        
        # Check if time slot is already booked
        existing_booking = Booking.objects.filter(
            court=court,
            booking_date=booking_date,
            time_slot=time_slot,
            status__in=['pending', 'confirmed']
        ).first()
        
        if existing_booking:
            return JsonResponse({'error': 'This time slot is already booked'}, status=400)
        
        # Calculate total amount (court price for the time slot)
        total_amount = court.hourly_rate 
        
        # Create booking
        booking = Booking.objects.create(
            court=court,
            booking_date=booking_date,
            time_slot=time_slot,
            player_name=player_name,
            contact_number=contact_number,
            user=request.user,
            notes=notes,
            status='confirmed',
            total_amount=total_amount
        )
        
        # Update user's balance (total amount spent)
        request.user.balance += total_amount
        request.user.total_booking += 1

        # Increment hours played (using booking duration)
        request.user.hours_played += booking.duration_hours 

        # Update reward points
        request.user.reward_points += 1
        
        # Save user changes
        request.user.save()
        
        # Create booking history
        BookingHistory.objects.create(
            booking=booking,
            previous_status='',
            new_status='confirmed',
            changed_by=request.user,
            change_reason='Initial booking creation'
        )
        
        # Send confirmation email to user
        try:
            send_booking_confirmation_email(booking, request.user)
            logger.info(f"Booking confirmation email sent successfully for booking {booking.booking_id}")
        except Exception as email_error:
            logger.error(f"Failed to send booking confirmation email: {str(email_error)}")
            # Don't fail the booking creation if email fails
        
        # Send notification email to owner
        try:
            send_owner_notification_email(booking, request.user)
            logger.info(f"Owner notification email sent successfully for booking {booking.booking_id}")
        except Exception as email_error:
            logger.error(f"Failed to send owner notification email: {str(email_error)}")
            # Don't fail the booking creation if email fails
        
        return JsonResponse({
            'success': True,
            'booking_id': str(booking.booking_id),
            'message': 'Booking created successfully! Confirmation email sent.',
            'booking_details': {
                'player_name': booking.player_name,
                'date': booking.booking_date.strftime('%Y-%m-%d'),
                'time': f"{booking.time_slot.start_time.strftime('%H:%M')} - {booking.time_slot.end_time.strftime('%H:%M')}",
                'court': booking.court.name,
                'total_amount': float(booking.total_amount)
            },
            'user_stats': {
                'total_spent': float(request.user.balance),
                'reward_points': request.user.reward_points
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Booking creation failed: {str(e)}")
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
    # totals = bookings.aggregate(
    #     total_bookings=Count('id'),
    #     total_hours=Sum('duration_hours'),
    #     total_cost=Sum('total_amount')
    # )

    completed_bookings = bookings.filter(status='confirmed')
    cancelled_bookings = bookings.filter(status='cancelled')
    reward_points = request.user.reward_points or 0
    booking = request.user.total_booking or 0
    hours_played = request.user.hours_played or 0
    balance = request.user.balance or 0

    context = {

        'bookings': bookings,
        'total_bookings': booking,
        'total_hours':hours_played,
        'total_cost': balance,
        'reward_points': reward_points,
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



@login_required
def download_receipt(request, booking_id):
    """
    Generate and download PDF receipt for a booking
    """
    # Get the booking object
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Create the PDF template
    template_path = 'booking/receipt.html'
    template = get_template(template_path)
    
    # Context data for the template
    context = {
        'booking': booking,
        'current_date': timezone.now(),
        'company_name': 'KankaiFutsal(shreshacademy)',
        'company_address': 'Kankai-3, Jhapa, Nepal',
        'company_phone': '+977-9849484847',
        'company_email': 'shreshacademy@gmail.com',
    }
    
    # Render the template with context
    html = template.render(context)
    
    # Create PDF
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        # Create HTTP response with PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="receipt_{booking.booking_id}.pdf"'
        response.write(result.getvalue())
        return response
    
    return HttpResponse('Error generating PDF', status=500)

@login_required
@require_POST
@csrf_protect
def cancel_booking(request, booking_id):
    """Cancel a booking and deduct user stats"""
    
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Check if booking is already cancelled
    if booking.status == 'cancelled':
        return JsonResponse({
            'success': False, 
            'message': 'Booking is already cancelled'
        }, status=400)
    
    # Check if booking is in the past
    booking_datetime = datetime.combine(booking.booking_date, booking.time_slot.start_time)
    current_time = timezone.now()
    
    if timezone.is_naive(booking_datetime):
        booking_datetime = timezone.make_aware(booking_datetime)
    
    if booking_datetime < current_time:
        return JsonResponse({
            'success': False, 
            'message': 'Cannot cancel past bookings'
        }, status=400)
    
    # Deduct user stats (reverse what was added during booking creation)
    
    # Deduct balance (total amount spent)
    if request.user.balance >= booking.total_amount:
        request.user.balance -= booking.total_amount
    else:
        request.user.balance = 0
    
    # Deduct total booking count
    if request.user.total_booking > 0:
        request.user.total_booking -= 1
    
    # Deduct hours played
    if request.user.hours_played >= booking.duration_hours:
        request.user.hours_played -= booking.duration_hours
    else:
        request.user.hours_played = 0
    
    # Deduct reward points (remove the 1 point gained from booking)
    if request.user.reward_points > 0:
        request.user.reward_points -= 1
    
    # Save user changes
    request.user.save()
    
    # Update booking status
    booking.status = 'cancelled'
    booking.cancelled_at = timezone.now()
    booking.cancellation_reason = 'User cancelled'
    booking.save()
    
    # Create booking history
    BookingHistory.objects.create(
        booking=booking,
        previous_status='confirmed',
        new_status='cancelled',
        changed_by=request.user,
        change_reason='User cancelled booking'
    )
    
    success_message = f"Booking cancelled successfully. NPR {booking.total_amount} deducted from total spent."
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': success_message,
            'amount_deducted': float(booking.total_amount),
            'remaining_points': request.user.reward_points,
            'remaining_balance': float(request.user.balance),
            'hours_deducted': booking.duration_hours
        })
    else:
        messages.success(request, success_message)
        return redirect('booking_page')

@login_required
def rebook_cancelled_booking(request, booking_id):
    """Rebook a previously cancelled booking"""
    
    cancelled_booking = get_object_or_404(
        Booking, 
        id=booking_id, 
        user=request.user, 
        status='cancelled'
    )
    
    # Check if the time slot is still available
    existing_booking = Booking.objects.filter(
        court=cancelled_booking.court,
        booking_date=cancelled_booking.booking_date,
        time_slot=cancelled_booking.time_slot,
        status__in=['confirmed', 'pending']
    ).first()
    
    if existing_booking:
        messages.error(request, 'This time slot is no longer available.')
        return redirect('booking_page')

    cancelled_booking.status = 'confirmed'
    cancelled_booking.save()
    
    messages.success(request, 'Booking recreated successfully!')
    return redirect('booking_page')

def send_booking_confirmation_email(booking, user):
    """Send booking confirmation email with bill details"""
    try:
        # Email context data
        context = {
            'booking': booking,
            'user': user,
            'booking_date': booking.booking_date.strftime('%B %d, %Y'),
            'booking_time': f"{booking.time_slot.start_time.strftime('%I:%M %p')} - {booking.time_slot.end_time.strftime('%I:%M %p')}",
            'duration': booking.duration_hours,
            'company_name': 'Kanakai Futsal',
            'company_address': 'Kankai-3 Surunga-jhapa',  # Update with actual address
            'company_phone': '+977 9849484878',    # Update with actual phone
            'company_email': 'shreeshacademy@gmail.com',  # Update with actual email
        }
        
        # Render HTML email template
        html_message = render_to_string('emails/booking_confirmation.html', context)
        
        # Create plain text version
        plain_message = strip_tags(html_message)
        
        # Email subject
        subject = f'Booking Confirmation - {booking.booking_id} | Kanakai Futsal'
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        raise e


def send_owner_notification_email(booking, user):
    """Send booking notification email to futsal owner with complete user details"""
    try:
        owner_email = getattr(settings, 'OWNER_EMAIL', 'umamurmu52@gmail.com') 
        
        # Email context data for owner
        context = {
            'booking': booking,
            'user': user,
            'booking_date': booking.booking_date.strftime('%B %d, %Y'),
            'booking_time': f"{booking.time_slot.start_time.strftime('%I:%M %p')} - {booking.time_slot.end_time.strftime('%I:%M %p')}",
            'duration': booking.duration_hours,
            'company_name': 'Kanakai Futsal',
        }
        
        # Render HTML email template for owner
        html_message = render_to_string('emails/owner_notification.html', context)
        
        # Create plain text version
        plain_message = strip_tags(html_message)
        
        # Email subject for owner
        subject = f'🔔 New Booking Alert - {booking.booking_id} | {booking.player_name}'
        
        # Send email to owner
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner_email],
            html_message=html_message,
            fail_silently=False,
        )
        
    except Exception as e:
        logger.error(f"Owner notification email sending failed: {str(e)}")
        raise e
    """Send booking confirmation email with bill details"""
    try:
        # Email context data
        context = {
            'booking': booking,
            'user': user,
            'booking_date': booking.booking_date.strftime('%B %d, %Y'),
            'booking_time': f"{booking.time_slot.start_time.strftime('%I:%M %p')} - {booking.time_slot.end_time.strftime('%I:%M %p')}",
            'duration': booking.duration_hours,
            'company_name': 'Kanakai Futsal',
            'company_address': 'Your Address Here',  # Update with actual address
            'company_phone': 'Your Phone Number',    # Update with actual phone
            'company_email': 'info@kanakifutsal.com',  # Update with actual email
        }
        
        # Render HTML email template
        html_message = render_to_string('emails/booking_confirmation.html', context)
        
        # Create plain text version
        plain_message = strip_tags(html_message)
        
        # Email subject
        subject = f'Booking Confirmation - {booking.booking_id} | Kanakai Futsal'
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        raise e