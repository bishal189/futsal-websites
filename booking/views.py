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
from django.db.models import Sum, Count


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
    """Handle booking creation with clean, stateless user stats tracking"""
    try:
        data = json.loads(request.body)
        
        # Extract data
        court_id = data.get('court_id')
        booking_date = data.get('date')
        time_slot_id = data.get('time_slot_id')
        player_name = data.get('player_name')
        contact_number = data.get('contact_number')
        notes = data.get('notes', '')

        if not all([court_id, booking_date, time_slot_id, player_name, contact_number]):
            return JsonResponse({'error': 'All required fields must be provided'}, status=400)

        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        
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
        
        # Booking history
        BookingHistory.objects.create(
            booking=booking,
            previous_status='',
            new_status='confirmed',
            changed_by=request.user,
            change_reason='Initial booking creation'
        )
        
        try:
            send_booking_confirmation_email(booking, request.user)
        except Exception as email_error:
            logger.error(f"Booking confirmation email failed: {str(email_error)}")

        try:
            send_owner_notification_email(booking, request.user)
        except Exception as email_error:
            logger.error(f"Owner notification email failed: {str(email_error)}")
        
        # Dynamically fetch user stats
        confirmed_bookings = Booking.objects.filter(user=request.user, status='confirmed')
        stats = confirmed_bookings.aggregate(
            total_hours=Sum('duration_hours'),
            total_spent=Sum('total_amount')
        )
        
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
                'total_bookings': confirmed_bookings.count(),
                'total_hours': stats['total_hours'] or 0,
                'total_spent': float(stats['total_spent']) if stats['total_spent'] else 0,
                'reward_points': confirmed_bookings.count() 
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

    valid_bookings = bookings.filter(status='confirmed')

    # Aggregations
    totals = valid_bookings.aggregate(
        total_bookings=Count('id'),
        total_hours=Sum('duration_hours'),
        total_cost=Sum('total_amount')
    )

    completed_bookings = valid_bookings
    cancelled_bookings = bookings.filter(status='cancelled')

    # Fallback to 0 if None
    context = {
        'bookings': bookings,
        'total_bookings': totals['total_bookings'] or 0,
        'total_hours': totals['total_hours'] or 0,
        'total_cost': totals['total_cost'] or 0,
        'reward_points': totals['total_bookings'] or 0, 
        "completed_bookings": completed_bookings,
        'cancelled_bookings': cancelled_bookings,
    }

    return render(request, 'home/dashboard.html', context)

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
    """Cancel a booking and reflect updated stats"""
    
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Check if already cancelled
    if booking.status == 'cancelled':
        return JsonResponse({'success': False, 'message': 'Booking is already cancelled'}, status=400)
    
    # Check if booking is in the past
    booking_datetime = datetime.combine(booking.booking_date, booking.time_slot.start_time)
    if timezone.is_naive(booking_datetime):
        booking_datetime = timezone.make_aware(booking_datetime, timezone.get_current_timezone())
    
    if booking_datetime < timezone.now():
        return JsonResponse({'success': False, 'message': 'Cannot cancel past bookings'}, status=400)
    
    # Update booking status
    booking.status = 'cancelled'
    booking.updated_at = timezone.now()
    booking.save()
    
    # Track in Booking History
    BookingHistory.objects.create(
        booking=booking,
        previous_status='confirmed',
        new_status='cancelled',
        changed_by=request.user,
        change_reason='User cancelled booking'
    )
    
    # Updated aggregated stats (optional)
    valid_bookings = Booking.objects.filter(user=request.user, status='confirmed')
    
    totals = valid_bookings.aggregate(
        total_hours=Sum('duration_hours'),
        total_cost=Sum('total_amount')
    )
    
    response_data = {
        'success': True,
        'message': 'Booking cancelled successfully.',
        'total_bookings': valid_bookings.count(),
        'total_hours': totals['total_hours'] or 0,
        'total_cost': float(totals['total_cost']) if totals['total_cost'] else 0,
        'reward_points': valid_bookings.count() 
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(response_data)
    else:
        messages.success(request, response_data['message'])
        return redirect('booking_page')


def send_booking_confirmation_email(booking, user):
    """Send booking confirmation email with bill details"""
    try:
        # Calculate user stats
        confirmed_bookings = Booking.objects.filter(user=user, status='confirmed')
        stats = confirmed_bookings.aggregate(
            total_bookings=Count('id'),
            total_hours=Sum('duration_hours'),
            total_spent=Sum('total_amount')
        )
        
        # Email context data
        context = {
            'booking': booking,
            'user': user,
            'booking_date': booking.booking_date.strftime('%B %d, %Y'),
            'booking_time': f"{booking.time_slot.start_time.strftime('%I:%M %p')} - {booking.time_slot.end_time.strftime('%I:%M %p')}",
            'duration': booking.duration_hours,
            'company_name': 'Kanakai Futsal',
            'company_address': 'Kankai-3 Surunga-jhapa',
            'company_phone': '+977 9849484878',
            'company_email': 'shreeshacademy@gmail.com',
            
            # Dynamically calculated user stats
            'total_booking': stats['total_bookings'] or 0,
            'hours_played': stats['total_hours'] or 0,
            'reward_points': stats['total_bookings'] or 0,  # 1 reward point per confirmed booking
            'balance': stats['total_spent'] or 0,
        }
        
        html_message = render_to_string('emails/booking_confirmation.html', context)
        plain_message = strip_tags(html_message)
        
        subject = f'Booking Confirmation - {booking.booking_id} | Kanakai Futsal'
        
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
        owner_emails = ['shreeshacademy@gmail.com', 'mohannthapa@gmail.com']
        # owner_emails = ['umamurmu52@gmail.com']

        confirmed_bookings = Booking.objects.filter(user=user, status='confirmed')
        stats = confirmed_bookings.aggregate(
            total_bookings=Count('id'),
            total_hours=Sum('duration_hours'),
            total_spent=Sum('total_amount')
        )
        
        
        # Email context data for owner
        context = {
            'booking': booking,
            'user': user,
            'booking_date': booking.booking_date.strftime('%B %d, %Y'),
            'booking_time': f"{booking.time_slot.start_time.strftime('%I:%M %p')} - {booking.time_slot.end_time.strftime('%I:%M %p')}",
            'duration': booking.duration_hours,
            'company_name': 'Kanakai Futsal',

            # for stats
            'total_booking': stats['total_bookings'] or 0,
            'hours_played': stats['total_hours'] or 0,
            'reward_points': stats['total_bookings'] or 0, 
            'balance': stats['total_spent'] or 0,
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
            recipient_list=owner_emails,
            html_message=html_message,
            fail_silently=False,
        )
        
    except Exception as e:
        logger.error(f"Owner notification email sending failed: {str(e)}")
        raise e
   