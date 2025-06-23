from django.shortcuts import render, redirect
from .forms import RegisterForm
from django.contrib import messages
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.http import HttpResponse
from .models import  CustomUser



# Create your views here.


def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.full_name}!")

            if next_url:
                return redirect(next_url)
            return redirect('home')
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, 'auth/login.html', {'next': next_url})

def register_view(request):
    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data['full_name'] = post_data.get('firstName')
        post_data['password'] = post_data.get('password')
        post_data['confirm_password'] = post_data.get('confirmPassword')
        post_data['email'] = post_data.get('email')
        post_data['agree_terms'] = 'on' if post_data.get('terms') else ''

        form = RegisterForm(post_data)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Registration successful! Welcome to Kankai Futsal.")
                return redirect('login')

            except Exception as e:
                messages.error(request, "Registration failed. Please try again.")
                print(f"Registration error: {e}")
           
        else:
            messages.error(request, "Please correct the errors below.")
            print("Form errors:", form.errors.as_data())
    else:
        form = RegisterForm()      

    return render(request, 'auth/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')  

    
def forget_password(request):
    if request.method == "POST":
        email = request.POST.get('email')
        users = User.objects.filter(email=email)
        if users.exists():
            for user in users:
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                domain = request.get_host()
                protocol = 'https' if request.is_secure() else 'http'
                
                email_subject = "Password Reset Requested"
                email_body = render_to_string("auth/password_reset_email.html", {
                    'user': user,
                    'domain': domain,
                    'uid': uid,
                    'token': token,
                    'protocol': protocol,
                })

                send_mail(
                    email_subject,
                    email_body,
                    None,  # Default from email
                    [user.email],
                    fail_silently=False,
                )
            messages.success(request, "Password reset link sent to your email.")
            return redirect('login')
        else:
            messages.error(request, "No account found with this email.")
    return render(request, 'auth/forget_password.html')




def password_reset_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == "POST":
            password1 = request.POST.get("password1")
            password2 = request.POST.get("password2")
            if password1 and password1 == password2:
                user.set_password(password1)
                user.save()
                messages.success(request, "Password has been reset. You can now log in.")
                return redirect('login')
            else:
                messages.error(request, "Passwords do not match.")
        return render(request, "auth/password_reset_confirm.html")
    else:
        messages.error(request, "The reset link is invalid or has expired.")
        return redirect('password_reset')
