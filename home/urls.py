
from django.urls import path
from . import views

urlpatterns = [
    path('',views.home,name='home'),
    path('terms/',views.terms,name='terms'),
    path('privacy/',views.privacy,name='privacy'),
    path('profile/',views.profile,name='profile'),
    path('facility/',views.facility,name='facility'),
    path('news/',views.news,name='news'),
    path('contact/',views.contact,name='contact'),
    path('gallery/',views.gallery,name='gallery'),
]
