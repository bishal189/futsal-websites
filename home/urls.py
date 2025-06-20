
from django.urls import path
from . import views

urlpatterns = [
    path('',views.home,name='home'),
    path('/terms',views.terms,name='terms'),
    path('/privacy',views.privacy,name='privacy'),
    path('/profile',views.profile,name='profile'),
    path('/mybooking',views.Booking,name='my_bookings'),
]
