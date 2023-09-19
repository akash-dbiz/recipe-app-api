"""
Test for the ingredient API
"""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Ingredient,
    Recipe
)

from recipe.serializers import IngredientSerializer

INGREDIENTS_URLS = reverse('recipe:ingredient-list')


def detail_url(ingredient_id):
    """Create and return an ingredient url"""
    return reverse('recipe:ingredient-detail', args=[ingredient_id])


def create_user(email='user12@example.com', password='testpass'):
    """Create and return user """
    return get_user_model().objects.create_user(email=email, password=password)


class PublicIngredientApitests(TestCase):
    """Test unauthorized api requests"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is required for retrieving ingredients."""
        res = self.client.get(INGREDIENTS_URLS)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientAPItests(TestCase):
    """Test authenticated api requests."""

    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredients(self):
        """Test retreiving list of ingredients"""
        Ingredient.objects.create(user=self.user, name='kale')
        Ingredient.objects.create(user=self.user, name='onion')

        res = self.client.get(INGREDIENTS_URLS)

        ingredients = Ingredient.objects.all().order_by('-name')
        serializer = IngredientSerializer(ingredients, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_ingredients_limited_to_user(self):
        """Test list is limited to authenticated user"""
        user2 = create_user(email='test@example.com')
        Ingredient.objects.create(user=user2, name='salt')
        ingredient = Ingredient.objects.create(user=self.user, name='Pepper')

        res = self.client.get(INGREDIENTS_URLS)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], ingredient.name)
        self.assertEqual(res.data[0]['id'], ingredient.id)

    def test_update_ingredient(self):
        """Test updating an ingredient"""
        ingredient = Ingredient.objects.create(user=self.user, name='clia')

        payload = {'name': 'coriu'}
        url = detail_url(ingredient.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.name, payload['name'])

    def test_delete_ingredients(self):
        """Test deleting ingredients"""
        ingredient = Ingredient.objects.create(user=self.user, name='lion')

        url = detail_url(ingredient.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        ingredients = Ingredient.objects.filter(user=self.user)
        self.assertFalse(ingredients.exists())

    def test_filter_ingredients_assigned_to_recipes(self):
        """Test listing ingredients by those assigned to recipes"""
        in1 = Ingredient.objects.create(user=self.user, name='apple')
        in2 = Ingredient.objects.create(user=self.user, name='banana')
        recipe = Recipe.objects.create(
            title='apple pie',
            time_minutes=5,
            price=Decimal(2),
            user=self.user
        )
        recipe.ingredients.add(in1)

        res = self.client.get(INGREDIENTS_URLS, {'assigned_only': 1})

        s1 = IngredientSerializer(in1)
        s2 = IngredientSerializer(in2)

        self.assertIn(s1.data, res.data)
        self.assertNotIn(s2.data, res.data)

    def test_filtered_ingredients_unique(self):
        """Test filtered ingredients returns a unique list"""
        ing = Ingredient.objects.create(user=self.user, name='Eggs')
        Ingredient.objects.create(user=self.user, name='eggssgsg')
        recipe1 = Recipe.objects.create(
            title='Egss',
            time_minutes=3,
            price=Decimal(2),
            user=self.user
        )
        recipe2 = Recipe.objects.create(
            title='Egssadafs',
            time_minutes=223,
            price=Decimal(12),
            user=self.user
        )
        recipe1.ingredients.add(ing)
        recipe2.ingredients.add(ing)

        res = self.client.get(INGREDIENTS_URLS, {'assigned_only': 1})

        self.assertEqual(len(res.data), 1)
