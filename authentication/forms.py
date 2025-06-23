from django import forms
from django.contrib.auth.hashers import make_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import CustomUser
from django.utils.text import slugify
import re

class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(),
        min_length=8,
        help_text="Password must be at least 8 characters long"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(),
        help_text="Enter the same password as before, for verification"
    )

    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'password', 'confirm_password']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name')
        if not full_name:
            raise ValidationError("Full name is required.")
        
        if len(full_name.strip()) < 2:
            raise ValidationError("Full name must be at least 2 characters long.")
        
        # Check for valid characters (letters, spaces, hyphens, apostrophes)
        if not re.match(r"^[a-zA-Z\s\-']+$", full_name):
            raise ValidationError("Full name can only contain letters, spaces, hyphens, and apostrophes.")
        
        return full_name.strip()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email address is required.")
        
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError("Please enter a valid email address.")
        
        # Check if email already exists
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError("An account with this email address already exists.")
        
        return email.lower()

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password:
            raise ValidationError("Password is required.")
        
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        
        # Check for at least one digit
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one number.")
        
        # Check for at least one letter
        if not re.search(r'[A-Za-z]', password):
            raise ValidationError("Password must contain at least one letter.")
        
        return password

    def clean_confirm_password(self):
        password = self.cleaned_data.get("password")
        confirm_password = self.cleaned_data.get("confirm_password")
        
        if not confirm_password:
            raise ValidationError("Please confirm your password.")
        
        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")
        
        return confirm_password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        
        # Additional password confirmation check
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Generate unique username from full name
        base_username = slugify(self.cleaned_data.get('full_name'))
        if not base_username:  # fallback if slugify returns empty
            base_username = 'user'
            
        username = base_username
        counter = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{base_username}-{counter}"
            counter += 1
        
        user.username = username
        user.email = self.cleaned_data.get('email')
        user.full_name = self.cleaned_data.get('full_name')
        user.password = make_password(self.cleaned_data.get('password'))
        
        if commit:
            user.save()
        
        return user