from django.test import TestCase
from django.urls import reverse

from .models import User


class LoginAndRoleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('boss', password='Str0ng-pass!', role='ADMIN')
        self.viewer = User.objects.create_user('view', password='Str0ng-pass!', role='VIEWER')

    def test_account_locks_after_five_wrong_passwords(self):
        for _ in range(5):
            self.client.post(reverse('accounts:login'), {'username': 'view', 'password': 'wrong'})
        response = self.client.post(reverse('accounts:login'), {'username': 'view', 'password': 'Str0ng-pass!'})
        self.assertEqual(response.status_code, 200)             # form shown again: login refused
        self.assertContains(response, 'Too many failed attempts')

    def test_successful_login_resets_the_counter(self):
        self.client.post(reverse('accounts:login'), {'username': 'view', 'password': 'wrong'})
        self.client.post(reverse('accounts:login'), {'username': 'view', 'password': 'Str0ng-pass!'})
        self.viewer.refresh_from_db()
        self.assertEqual(self.viewer.failed_attempts, 0)

    def test_only_admin_can_manage_users(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('accounts:user_list')).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('accounts:user_list')).status_code, 200)

    def test_anonymous_users_are_sent_to_login(self):
        response = self.client.get(reverse('reports:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_passwords_are_hashed(self):
        self.assertNotEqual(self.admin.password, 'Str0ng-pass!')
        self.assertTrue(self.admin.password.startswith(('pbkdf2_', 'argon2', 'bcrypt')))
