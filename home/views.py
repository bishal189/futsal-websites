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
    return render(request, 'legal/privacy.html')