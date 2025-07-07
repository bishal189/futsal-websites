from django.test import TestCase, Client
from django.urls import reverse
from .models import CustomUser

class LoginViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')

        # Provide username if create_user requires it
        self.user = CustomUser.objects.create_user(
            username='testuser',  # Add this if your model requires it
            email='testuser@example.com',
            password='testpassword123',
            full_name='Test User'
        )

    def test_login_successful(self):
        response = self.client.post(self.login_url, {
            'email': 'testuser@example.com',
            'password': 'testpassword123'
        })

        self.assertRedirects(response, reverse('home'))
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_login_invalid_credentials(self):
        response = self.client.post(self.login_url, {
            'email': 'testuser@example.com',
            'password': 'wrongpassword'
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
