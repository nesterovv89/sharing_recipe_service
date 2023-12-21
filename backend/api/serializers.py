import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from djoser.serializers import (SetPasswordSerializer, UserCreateSerializer,
                                UserSerializer)
from drf_extra_fields.fields import Base64ImageField
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Tag)
from rest_framework import serializers, status
from rest_framework.validators import UniqueTogetherValidator
from users.models import Follow, User


class UserCreateSerializer(UserCreateSerializer):
    """Серилизатор создания пользователя"""

    class Meta:
        model = User
        fields = ('email', 'id', 'username',
                  'first_name', 'last_name', 'password')

    def validate_username(self, value):
        if not re.match(r'^[\w.@+-]+$', value):
            raise ValidationError(
                'Username содержит недопустимые символы'
            )
        return value


class UserReadSerializer(UserSerializer):
    """Серилизатор списка пользователей"""

    is_subscribed = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('email', 'id', 'username',
                  'first_name', 'last_name', 'is_subscribed')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        return user and user.is_authenticated and (
            obj.following.filter(user=user).exists()
        )


class SetPasswordSerializer(SetPasswordSerializer):
    """[POST] Изменение пароля пользователя."""
    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)


class IngredientSerializer(serializers.ModelSerializer):
    """Серилизатор ингредиентов"""

    class Meta:
        model = Ingredient
        fields = '__all__'


class TagSerializer(serializers.ModelSerializer):
    """Серилизатор тэгов"""

    class Meta:
        model = Tag
        fields = '__all__'


class ShortRecipeSerializer(serializers.ModelSerializer):
    """Серилизатор предпросмотра рецептов"""
    image = Base64ImageField(read_only=True)
    name = serializers.ReadOnlyField()
    cooking_time = serializers.ReadOnlyField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'image',
            'cooking_time',
        )


class RecipeIngredientGetSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиентов рецепта"""

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeGetSerializer(serializers.ModelSerializer):
    """Сериализатор списка рецептов"""

    author = UserReadSerializer(
        read_only=True,
    )
    tags = TagSerializer(
        many=True,
        read_only=True
    )
    ingredients = RecipeIngredientGetSerializer(
        many=True, source='recipe_ingredients'
    )
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request is None or request.user.is_anonymous:
            return False
        return Favorite.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request is None or request.user.is_anonymous:
            return False
        return ShoppingCart.objects.filter(user=request.user,
                                           recipe=obj).exists()


class AddIngredientRecipeSerializer(serializers.ModelSerializer):
    """ Сериализатор добавления ингредиентов """

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all()
    )
    amount = serializers.IntegerField()

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Кол-во ингредиента должно быть больше 0'
            )
        return value

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount',)


class RecipeCreateSerializer(serializers.ModelSerializer):
    """ Сериализатор создания рецептов """

    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    author = UserReadSerializer(read_only=True)
    ingredients = AddIngredientRecipeSerializer(many=True)
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'author',
            'ingredients',
            'tags',
            'image',
            'name',
            'text',
            'cooking_time',
        )

    def validate(self, obj):

        if not obj.get('tags'):
            raise ValidationError(
                'Нужно указать минимум 1 тег.'
            )
        tags_list = []
        for tag in obj.get('tags'):
            if tag in tags_list:
                raise ValidationError(
                    {'tags': 'Теги должны быть уникальными!'}
                )
            tags_list.append(tag)

        ingredients_list = []
        for ingredient in obj.get('recipeingredients'):
            if ingredient.get('amount') <= 0:
                raise ValidationError(
                    {'ingredients': 'Количество не может быть меньше 1'}
                )
            ingredients_list.append(ingredient.get('id'))
        if len(set(ingredients_list)) != len(ingredients_list):
            raise ValidationError(
                {'ingredients':
                 'Вы пытаетесь добавить в рецепт два одинаковых ингредиента'}
            )
        return obj

    def validate_cooking_time(self, value):
        if value <= 0:
            raise ValidationError(
                'Время приготовления должно быть больше 0'
            )
        return value

    def create_ingredients(self, recipe, ingredients):
        ingredient_list = []
        for ingredient_data in ingredients:
            ingredient_list.append(
                RecipeIngredient(
                    ingredient=ingredient_data['id'],
                    amount=ingredient_data['amount'],
                    recipe=recipe,
                )
            )
        RecipeIngredient.objects.bulk_create(ingredient_list)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')
        recipe = Recipe.objects.create(author=request.user, **validated_data)
        recipe.tags.set(tags)
        self.create_ingredients(recipe, ingredients)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('ingredients')
        instance.ingredients.clear()
        self.create_ingredients(instance, ingredients)
        instance.tags.set(tags)
        instance.save()
        return instance

    def to_representation(self, instance):
        request = self.context.get('request')
        context = {'request': request}
        return RecipeGetSerializer(instance, context=context).data


class FavoritesListSerializer(serializers.Serializer):
    """ Сериализатор добавления рецепта в избранное """
    user = UserSerializer
    recipe = ShortRecipeSerializer

    class Meta:
        model = Favorite
        fields = ('user', 'recipe')

    def validate(self, data):
        user = data.get('user')
        recipe = data.get('recipe')
        if Favorite.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError(
                {'errors': 'Данный рецепт уже есть в избраном'}
            )
        return data

    def create(self, validated_data):
        user = validated_data.get('user')
        recipe = validated_data.get('recipe')
        return Favorite.objects.create(user=user, recipe=recipe)


class SubscribeSerializer(UserReadSerializer):
    """Сериализатор подписок """
    recipes = ShortRecipeSerializer(many=True, read_only=True)
    recipes_count = serializers.SerializerMethodField(source='recipes.count')

    class Meta:
        model = User
        fields = ('email', 'id',
                  'username', 'first_name',
                  'last_name', 'is_subscribed',
                  'recipes', 'recipes_count')

    def validate(self, data):
        user = self.request.user
        author = get_object_or_404(User, pk=id)
        if user == author:
            return Response(
                {'errors': 'Нельзя подписаться на самого себя'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if Follow.objects.filter(user=user, author=author).exists():
            return Response(
                {'errors': 'Вы уже подписаны на этого пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return data

    def get_is_subscribed(self, obj):
        return (
            self.context.get('request').user.is_authenticated
            and Follow.objects.filter(user=self.context['request'].user,
                                      author=obj).exists()
        )

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class SubscriptionSerializer(serializers.ModelSerializer):
    """ Сериализатор для подписки на пользователя """

    class Meta:
        model = Follow
        fields = '__all__'
        validators = [
            UniqueTogetherValidator(
                queryset=Follow.objects.all(),
                fields=('user', 'author'),
                message='Вы уже подписаны на этого пользователя'
            )
        ]

    def create(self, validated_data):
        author = validated_data.get('author')
        user = validated_data.get('user')
        return Follow.objects.create(user=user, author=author)


class ShoppingCartSerializer(serializers.Serializer):
    """ Сериализатор корзины покупок """
    class Meta:
        fields = (
            'recipe', 'user'
        )
        model = ShoppingCart

    def validate(self, data):
        recipe_id = data.get('recipe_id')
        user = data.get('user')
        if ShoppingCart.objects.filter(user=user,
                                       recipe_id=recipe_id).exists():
            raise serializers.ValidationError(
                'Этот рецепт уже есть в списке покупок'
            )
        return data
