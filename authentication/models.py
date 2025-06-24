# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from decimal import Decimal


class CustomUser(AbstractUser):
    username = models.CharField(max_length=150, blank=True, null=True, unique=False)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    reward_points = models.PositiveIntegerField(default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hours_played = models.PositiveIntegerField(default=0)
    total_booking = models.PositiveIntegerField(default=0)



    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username'] 

    def __str__(self):
        return self.email
