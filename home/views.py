from django.shortcuts import render
from django.http import JsonResponse
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging

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



logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def contact_form_view(request):
    """
    Handle contact form submission and send emails to owners and user
    """
    try:
        # Parse form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        # Extract form fields
        first_name = data.get('firstName', '').strip()
        last_name = data.get('lastName', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        
        # Basic validation
        if not all([first_name, last_name, email, subject, message]):
            return JsonResponse({
                'success': False,
                'message': 'Please fill in all required fields.'
            }, status=400)
        
        # Prepare email context
        email_context = {
            'first_name': first_name,
            'last_name': last_name,
            'full_name': f"{first_name} {last_name}",
            'email': email,
            'phone': phone,
            'subject': subject,
            'message': message,
        }
        
        # Owner email addresses
        owner_emails = [
            'shreeshacademy@gmail.com',
            'mohannthapa@gmail.com',
        ]
        
        # Send email to owners
        owner_email_sent = send_email_to_owners(email_context, owner_emails)
        
        # Send confirmation email to user
        user_email_sent = send_confirmation_email_to_user(email_context)
        
        if owner_email_sent and user_email_sent:
            return JsonResponse({
                'success': True,
                'message': 'Thank you for your message! We have received your inquiry and will get back to you soon.'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'There was an issue sending your message. Please try again or contact us directly.'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error in contact form submission: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'An unexpected error occurred. Please try again later.'
        }, status=500)


def send_email_to_owners(context, owner_emails):
    """
    Send notification email to futsal owners
    """
    try:
        subject = f"New Contact Form Submission - {context['subject']}"
        
        # Plain text message
        message = f"""
        New contact form submission from kanakai Futsal website:
        
        Name: {context['full_name']}
        Email: {context['email']}
        Phone: {context['phone']}
        Subject: {context['subject']}
        Message:
        {context['message']}
        
        Please respond to the customer at: {context['email']}
        """
        
        # HTML message
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #2d5016, #ff6b35); padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
                    <h1 style="color: white; margin: 0;">New Contact Form Submission</h1>
                    <p style="color: #f0f0f0; margin: 5px 0 0 0;">kanakai Futsal</p>
                </div>
                
                <div style="background: #f9f9f9; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                    <h2 style="color: #2d5016; margin-top: 0;">Customer Details</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold; width: 30%;">Name:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{context['full_name']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">Email:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><a href="mailto:{context['email']}" style="color: #ff6b35;">{context['email']}</a></td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">Phone:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{context['phone'] or 'Not provided'}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">Subject:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{context['subject']}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #ff6b35;">
                    <h3 style="color: #2d5016; margin-top: 0;">Message:</h3>
                    <p style="margin: 0; white-space: pre-wrap;">{context['message']}</p>
                </div>
                
                <div style="text-align: center; margin-top: 20px; padding: 15px; background: #e8f5e8; border-radius: 10px;">
                    <p style="margin: 0; color: #2d5016;">
                        <strong>Please respond to the customer at:</strong>
                        <a href="mailto:{context['email']}" style="color: #ff6b35; text-decoration: none;">{context['email']}</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=owner_emails,
            reply_to=[context['email']]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send()
        logger.info(f"Owner notification email sent successfully to {owner_emails}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email to owners: {str(e)}")
        return False


def send_confirmation_email_to_user(context):
    """
    Send confirmation email to the user who submitted the form
    """
    try:
        subject = "Thank you for contacting kanakai Futsal"
        
        # Plain text message
        message = f"""
        Dear {context['first_name']},
        
        Thank you for contacting kanakai Futsal! We have received your message and will get back to you as soon as possible.
        
        Here's a summary of your submission:
        
        Subject: {context['subject']}
        Message: {context['message']}
        
        Our team typically responds within 24 hours. If you have any urgent questions, please call us at +977 9849484878.
        
        Best regards,
        kanakai Futsal Team
        
        Address: kanakai Municipality-3, kanakai Futsal (Shreesh Academy)
        Phone: +977 9849484878
        Email: shreeshacademy@gmail.com
        Operating Hours: Sunday-Saturday: 6:00 AM - 10:00 PM (24 Hours Services)
        """
        
        # HTML message
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #2d5016, #ff6b35); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">Thank You!</h1>
                    <p style="color: #f0f0f0; margin: 10px 0 0 0; font-size: 18px;">kanakai Futsal</p>
                </div>
                
                <div style="background: #f9f9f9; padding: 25px; border-radius: 10px; margin-bottom: 25px;">
                    <h2 style="color: #2d5016; margin-top: 0;">Dear {context['first_name']},</h2>
                    <p>Thank you for contacting kanakai Futsal! We have received your message and will get back to you as soon as possible.</p>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ff6b35;">
                        <h3 style="color: #2d5016; margin-top: 0;">Your Submission Summary:</h3>
                        <p><strong>Subject:</strong> {context['subject']}</p>
                        <p><strong>Message:</strong></p>
                        <p style="background: #f8f8f8; padding: 15px; border-radius: 5px; margin: 10px 0; white-space: pre-wrap;">{context['message']}</p>
                    </div>
                    
                    <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; text-align: center;">
                        <p style="margin: 0; color: #2d5016;">
                            <strong>📞 Our team typically responds within 24 hours</strong><br>
                            For urgent questions, call us at <a href="tel:+977 9849484878" style="color: #ff6b35; text-decoration: none;">+977 9849484878</a>
                        </p>
                    </div>
                </div>
                
                <div style="background: white; padding: 25px; border-radius: 10px; border: 2px solid #f0f0f0;">
                    <h3 style="color: #2d5016; margin-top: 0; text-align: center;">Contact Information</h3>
                    <div style="display: flex; flex-wrap: wrap; gap: 20px;">
                        <div style="flex: 1; min-width: 200px;">
                            <p style="margin: 8px 0;"><strong>📍 Address:</strong><br>
                            kanakai Municipality-3<br>
                            kanakai Futsal (Shresh Academy)</p>
                            
                            <p style="margin: 8px 0;"><strong>📞 Phone:</strong><br>
                            <a href="tel:+977 9849484878" style="color: #ff6b35; text-decoration: none;">+977 9849484878</a></p>
                        </div>
                        <div style="flex: 1; min-width: 200px;">
                            <p style="margin: 8px 0;"><strong>✉️ Email:</strong><br>
                            <a href="mailto:shreeshacademy@gmail.com" style="color: #ff6b35; text-decoration: none;">shreeshacademy@gmail.com</a></p>
                            
                            <p style="margin: 8px 0;"><strong>🕒 Operating Hours:</strong><br>
                            Sunday-Saturday: 6:00 AM - 10:00 PM<br>
                            <span style="color: #ff6b35; font-weight: bold;">24 Hours Services Available</span></p>
                        </div>
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding: 20px; color: #666;">
                    <p style="margin: 0;">Best regards,<br><strong style="color: #2d5016;">kanakai Futsal Team</strong></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[context['email']]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send()
        logger.info(f"Confirmation email sent successfully to {context['email']}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending confirmation email to user: {str(e)}")
        return False