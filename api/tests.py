from django.test import TestCase
from rest_framework.authtoken.models import Token

from accounts.models import User
from catalog.models import Product
from inventory.services import post_movement


class ApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('api', password='x', role='MANAGER')
        self.token = Token.objects.create(user=self.user)
        self.product = Product.objects.create(name='Item', selling_price=10)
        post_movement(self.product, 'RECEIPT', 7)

    def test_requires_authentication(self):
        self.assertEqual(self.client.get('/api/products/').status_code, 401)

    def test_lists_products_with_stock(self):
        response = self.client.get('/api/products/', HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['stock'], 7)

    def test_api_is_read_only(self):
        response = self.client.post('/api/products/', {'name': 'x'}, HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.assertEqual(response.status_code, 403)
