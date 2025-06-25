from django.shortcuts import render, redirect
from .forms import RegisterForm
from django.contrib import messages
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.http import HttpResponse
from django.utils.html import strip_tags
from django.conf import settings

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
    """Handle forgot password requests"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Email address is required.')
            return render(request, 'forgot_password.html')
        
        try:
            # Check if user exists with this email
            user = CustomUser.objects.get(email=email)
            
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Create password reset URL
            reset_url = request.build_absolute_uri(
                reverse('password_reset_confirm', kwargs={
                    'uidb64': uid,
                    'token': token
                })
            )
            
            # Email context
            context = {
                'user': user,
                'reset_url': reset_url,
                'site_name': 'Kanakai Futsal',
                'protocol': 'https' if request.is_secure() else 'http',
                'domain': request.get_host(),
            }
            
            # Render email templates
            subject = f'Password Reset for {context["site_name"]}'
            html_message = render_to_string('emails/password_reset_email.html', context)
            plain_message = strip_tags(html_message)
            
            # Send email
            try:
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False,
                )
                print(send_mail,'send')
                
                messages.success(
                    request, 
                    f'Password reset instructions have been sent to {email}. Please check your inbox and spam folder.'
                )
                
                # Store email in session for success page
                request.session['reset_email'] = email
                print('hello world')
                return render(request, 'auth/forgot_password.html', {'email_sent': True})
                
            except Exception as e:
                messages.error(
                    request, 
                    'Failed to send password reset email. Please try again later or contact support.'
                )
                return render(request, 'auth/forgot_password.html')
                
        except CustomUser.DoesNotExist:
            # Don't reveal that the user doesn't exist for security reasons
            messages.success(
                request, 
                f'If an account with {email} exists, password reset instructions have been sent to that email address.'
            )
            request.session['reset_email'] = email
            return render(request, 'auth/forgot_password.html', {'email_sent': True})
    
    return render(request, 'auth/forgot_password.html')


def password_reset_confirm(request, uidb64, token):
    """Handle password reset confirmation"""
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            if not password1 or not password2:
                messages.error(request, 'Both password fields are required.')
                return render(request, 'auth/password_reset_confirm.html', {
                    'validlink': True,
                    'uidb64': uidb64,
                    'token': token
                })
            
            if password1 != password2:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'auth/password_reset_confirm.html', {
                    'validlink': True,
                    'uidb64': uidb64,
                    'token': token
                })
            
            if len(password1) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
                return render(request, 'auth/password_reset_confirm.html', {
                    'validlink': True,
                    'uidb64': uidb64,
                    'token': token
                })
            
            # Set new password
            user.set_password(password1)
            user.save()
            
            messages.success(request, 'Your password has been successfully reset. You can now log in with your new password.')
            return redirect('login')
        
        return render(request, 'auth/password_reset_confirm.html', {
            'validlink': True,
            'uidb64': uidb64,
            'token': token
        })
    else:
        messages.error(request, 'The password reset link is invalid or has expired. Please request a new one.')
        return redirect('forget_password')


def resend_reset_email(request):
    """Handle resend password reset email via AJAX"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            
            if not email:
                return JsonResponse({'success': False, 'message': 'Email is required.'})
            
            try:
                user = CustomUser.objects.get(email=email)
                
                # Generate new token
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Create password reset URL
                reset_url = request.build_absolute_uri(
                    reverse('password_reset_confirm', kwargs={
                        'uidb64': uid,
                        'token': token
                    })
                )
                
                # Email context
                context = {
                    'user': user,
                    'reset_url': reset_url,
                    'site_name': 'Kanakai Futsal',
                    'protocol': 'https' if request.is_secure() else 'http',
                    'domain': request.get_host(),
                }
                
                # Send email
                subject = f'Password Reset for {context["site_name"]}'
                html_message = render_to_string('emails/password_reset_email.html', context)
                plain_message = strip_tags(html_message)
                
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False,
                )
                
                return JsonResponse({'success': True, 'message': 'Reset email sent successfully!'})
                
            except CustomUser.DoesNotExist:
                # Don't reveal user existence
                return JsonResponse({'success': True, 'message': 'Reset email sent successfully!'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'message': 'Failed to resend email. Please try again.'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})