"""
Tests for recipe app APIs
"""
import tempfile
import os
from PIL import Image
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Recipe,
    Tag,
    Ingredient
)

from recipe.serializers import (
    RecipeSerializer,
    RecipeDetailSerializer,
    )

RECIPES_URLS = reverse('recipe:recipe-list')


def detail_url(recipe_id):
    """Create and return a recipe detail URL."""
    return reverse('recipe:recipe-detail', args=[recipe_id])


def image_upload_url(recipe_id):
    """Create and return a recipe detain URL"""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


def create_recipe(user, **params):
    """Create and return a sample recipe"""
    defaults = {
        'title': 'Sample recipe title',
        'time_minutes': 5,
        'price': Decimal('5.50'),
        'description': 'Sample Desc',
        'link': 'http://example.com/recipe'
    }
    defaults.update(params)

    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe


def create_user(**params):
    """Create and return a new User"""
    return get_user_model().objects.create_user(**params)


class PublicRecipeAPITests(TestCase):
    """Test unauthenticated API test"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth is requid to call API"""
        res = self.client.get(RECIPES_URLS)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeAPITests(TestCase):
    """Test authenticated API Requests"""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="user@example.com", password='test123')
        self.client.force_authenticate(self.user)

    def test_retrive_recipes(self):
        """Test retriving a list of recipes"""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URLS)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_recipe_list_limited_to_user(self):
        """Test list of recipes is limited to authenticated user."""
        other_user = create_user(email='other@example.com',
                                 password='password')
        create_recipe(user=other_user)
        create_recipe(user=self.user)

        res = self.client.get(RECIPES_URLS)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_get_recipe_detail(self):
        """test get recipe detail"""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)

    def test_create_recipe(self):
        """Test creating a recipe"""
        payload = {
            'title': 'Sample Recipe',
            'time_minutes': 10,
            'price': Decimal('5.23'),
        }
        res = self.client.post(RECIPES_URLS, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        """Test partial update of a recipe"""
        original_link = 'https://example.com/recipe.pdf'
        recipe = create_recipe(
            user=self.user,
            title='sample recipe',
            link=original_link,
        )

        payload = {'title': 'New Recipe Title'}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_update(self):
        """Test full update of recipe"""
        recipe = create_recipe(
            user=self.user,
            title='sample recipe title',
            link='example.com',
            description='sample desc'
        )

        payload = {
            'title': 'new',
            'link': 'newexample.com',
            'description': 'new desc',
            'time_minutes': 10,
            'price': Decimal('3.42')
        }
        url = detail_url(recipe.id)
        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_update_user_returns_error(self):
        """Test changeing the recipe user results in an error"""
        new_user = create_user(email='user2@example.com', password='testpass')
        recipe = create_recipe(user=self.user)

        payload = {'user': new_user.id}
        url = detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe(self):
        """Test deleting a recipe successful"""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_other_users_recipe_error(self):
        """Test trying to delete another users recipe gives error"""
        new_user = create_user(email='user2@example.com', password='testpass')
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        """Test creating a recipe with the new tags"""
        payload = {
            'title': 'sdfadf',
            'time_minutes': 20,
            'price': Decimal('23.34'),
            'tags': [{'name': 'thao'}, {'name': 'dinenr'}],
        }
        res = self.client.post(RECIPES_URLS, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)
        for tag in payload['tags']:
            exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user,
            ).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_tags(self):
        """Test creating a recipe with existing tag."""
        tag_indian = Tag.objects.create(user=self.user, name='Indian')
        payload = {
            'title': 'Pongal',
            'time_minutes': 50,
            'price': Decimal('23.23'),
            'tags': [{'name': 'Indian'}, {'name': 'Breakfast'}],
        }
        res = self.client.post(RECIPES_URLS, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipies = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipies.count(), 1)
        recipe = recipies[0]
        self.assertEqual(recipe.tags.count(), 2)
        self.assertIn(tag_indian, recipe.tags.all())
        for tag in payload['tags']:
            exists = recipe.tags.filter(
                name=tag['name'],
                user=self.user,
            ).exists()
            self.assertTrue(exists)

    def test_create_tag_on_update(self):
        """Test creating a tag when updating a recipe"""
        recipe = create_recipe(user=self.user)

        payload = {'tags': [{'name': 'lunch'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user=self.user, name='lunch')
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        """Test assigning an existing tag when updating a recipe."""
        tag_breakfast = Tag.objects.create(user=self.user, name='breakfast')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user, name='lunch')
        payload = {'tags': [{'name': 'lunch'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):
        """Test clearing recipe tags."""
        tag = Tag.objects.create(user=self.user, name='desert')
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {'tags': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    def test_create_recipe_with_new_ingredients(self):
        """test creating a recipe with new ingredients"""
        payload = {
            'title': 'Cauliflower tacos',
            'time_minutes': 60,
            'price': Decimal('20'),
            'ingredients': [{'name': 'Cauliflower'}, {'name': 'Taco'}]
        }
        res = self.client.post(RECIPES_URLS, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)
        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(
                name=ingredient['name'],
                user=self.user,
            ).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_ingredient(self):
        """test creating recipe with existing ingredient"""
        ingredient = Ingredient.objects.create(user=self.user, name='Lemon')
        payload = {
            'title': 'Vite',
            'time_minutes': 20,
            'price': Decimal(29),
            'ingredients': [{'name': 'Lemon'}, {'name': 'Fish'}],
        }
        res = self.client.post(RECIPES_URLS, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)
        self.assertIn(ingredient, recipe.ingredients.all())
        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(
                name=ingredient['name'],
                user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_ingredient_on_update(self):
        """Test creating an ingredietn when updating a recipe"""
        recipe = create_recipe(user=self.user)

        payload = {'ingredients': [{'name': 'Line'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_ingredient = Ingredient.objects.get(user=self.user, name='Line')
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        """Test assinging an existing ingredient when updting a recipe"""
        ingredient1 = Ingredient.objects.create(user=self.user, name='pepper')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient1)

        ingredient2 = Ingredient.objects.create(user=self.user, name='chilli')
        payload = {'ingredients': [{'name': 'chilli'}]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(ingredient2, recipe.ingredients.all())
        self.assertNotIn(ingredient1, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        """Test clearing a recipe ingredients"""
        ingredient = Ingredient.objects.create(user=self.user, name='garlic')
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = {'ingredients': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)

    def test_filter_by_tags(self):
        """Test filtering recipes by tags"""
        r1 = create_recipe(user=self.user, title='Thai curry')
        r2 = create_recipe(user=self.user, title='Brinjall curry')
        tag1 = Tag.objects.create(user=self.user, name='vegan')
        tag2 = Tag.objects.create(user=self.user, name='veg')
        r1.tags.add(tag1)
        r2.tags.add(tag2)

        r3 = create_recipe(user=self.user, title='fish and chips')

        params = {'tags': f'{tag1.id},{tag2.id}'}
        res = self.client.get(RECIPES_URLS, params)

        s1 = RecipeSerializer(r1)
        s2 = RecipeSerializer(r2)
        s3 = RecipeSerializer(r3)
        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)

    def test_filter_by_ingredients(self):
        """test filtering recipes by ingredients"""
        r1 = create_recipe(user=self.user, title='title1')
        r2 = create_recipe(user=self.user, title='title2')
        in1 = Ingredient.objects.create(user=self.user, name='chicken')
        in2 = Ingredient.objects.create(user=self.user, name='chilli')
        r1.ingredients.add(in1)
        r2.ingredients.add(in2)

        r3 = create_recipe(user=self.user, title='title3')

        params = {'ingredients': f'{in1.id},{in2.id}'}
        res = self.client.get(RECIPES_URLS, params)

        s1 = RecipeSerializer(r1)
        s2 = RecipeSerializer(r2)
        s3 = RecipeSerializer(r3)

        self.assertIn(s1.data, res.data)
        self.assertIn(s2.data, res.data)
        self.assertNotIn(s3.data, res.data)


class ImageUploadTests(TestCase):
    """tests for the image upload API"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'user@example.com',
            'testpass'
        )
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image(self):
        """Test uploading an image to a recipe"""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix='.jpg') as image_file:
            img = Image.new('RGB', (10, 10))
            img.save(image_file, format='JPEG')
            image_file.seek(0)
            payload = {'image': image_file}
            res = self.client.post(url, payload, format='multipart')

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_test(self):
        """Test uploading invalid image"""
        url = image_upload_url(self.recipe.id)
        payload = {'image': 'notimage'}
        res = self.client.post(url, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
