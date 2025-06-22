
from django.urls import path
from . import views

urlpatterns = [
    path('booking/', views.booking_page, name='booking_page'),
    path('book/', views.booking_page, name='book_court'),
    
    # AJAX endpoints
    path('api/available-slots/', views.get_available_slots, name='get_available_slots'),
    path('api/create-booking/', views.create_booking, name='create_booking'),
    path('api/calendar-data/', views.booking_calendar_data, name='calendar_data'),
    
    # Booking management
    path('confirmation/<uuid:booking_id>/', views.booking_confirmation, name='booking_confirmation'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('cancel/<uuid:booking_id>/', views.cancel_booking, name='cancel_booking'),
]
