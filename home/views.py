from django.shortcuts import render
from django.shortcuts import render

def home(request):
    return render(request, 'home/index.html')

def terms(request):
    return render(request, 'legal/terms.html')

def privacy(request):
    return render(request, 'legal/privacy.html')

def profile(request):
    return render(request, 'legal/privacy.html')

def Booking(request):
    return render(request, 'home/dashboard.html')

def facility(request):
    return render(request, 'home/facility.html')

def news(request):
    return render(request, 'home/news.html')

def contact(request):
    return render(request, 'home/contact.html')

def gallery(request):
    return render(request, 'home/gallery.html')