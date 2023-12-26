import re

from django.core.exceptions import ValidationError
from django.db import transaction
from djoser.serializers import (UserCreateSerializer,
                                UserSerializer)
from drf_extra_fields.fields import Base64ImageField
from rest_framework.response import Response
from rest_framework import serializers, status

from . import constants as c
from users.models import Follow, User
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Tag)


class UserCreateSerializer(UserCreateSerializer):
    """Серилизатор создания пользователя"""

    class Meta:
        model = User
        fields = ('email', 'id', 'username',
                  'first_name', 'last_name', 'password',)

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
        if user and user.is_authenticated:
            return obj.following.filter(user=user).exists()
        return False


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
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
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
        if request and request.user.is_authenticated:
            return obj.favorites.filter(user=request.user).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.shopping_list.filter(user=request.user).exists()
        return False


class AddIngredientRecipeSerializer(serializers.ModelSerializer):
    """ Сериализатор добавления ингредиентов """

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all()
    )
    amount = serializers.IntegerField()

    def validate_amount(self, value):
        if value <= c.NIL_VALUE:
            raise serializers.ValidationError(
                f'Кол-во ингредиента должно быть больше {c.NIL_VALUE}'
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
        if not obj.get('image'):
            raise ValidationError(
                'Нужно добавить изображение'
            )
        if not obj.get('ingredients'):
            raise ValidationError(
                'Нужно добавить ингредиент.'
            )
        inrgedient_id_list = [item['id'] for item in obj.get('ingredients')]
        unique_ingredient_id_list = set(inrgedient_id_list)
        if len(inrgedient_id_list) != len(unique_ingredient_id_list):
            raise ValidationError(
                'Ингредиенты должны быть уникальны.'
            )
        return obj

    def validate_cooking_time(self, value):
        if value <= c.NIL_VALUE:
            raise ValidationError(
                f'Время приготовления должно быть больше {c.NIL_VALUE}'
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
    user = UserSerializer()
    recipe = ShortRecipeSerializer()

    class Meta:
        model = Favorite
        fields = ('user', 'recipe')

    recipe_id = serializers.IntegerField()

    def validate(self, validated_data):
        try:
            recipe = Recipe.objects.get(id=validated_data['recipe_id'])
        except Recipe.DoesNotExist:
            raise serializers.ValidationError('Рецепт не существует!')

        if Favorite.objects.filter(user=self.context['request'].user,
                                   recipe=recipe).exists():
            raise serializers.ValidationError('Рецепт уже добавлен!')

        favorite = Favorite.objects.create(
            user=self.context['request'].user, recipe=recipe)
        return favorite


class SubscribeSerializer(UserReadSerializer):
    recipes_count = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = UserReadSerializer.Meta.fields + (
            'recipes_count', 'recipes'
        )
        read_only_fields = ('email', 'username',
                            'first_name', 'last_name')

    def validate(self, data):
        user = self.context['request'].user
        author = self.instance

        if user == author:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя')
        if Follow.objects.filter(user=user, author=author).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя')
        return data

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            recipes = recipes[:int(limit)]
        serializer = ShortRecipeSerializer(recipes, many=True, read_only=True)
        return serializer.data


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
        if not Recipe.objects.filter(user=self.request.user,
                                     recipe=recipe_id).exists():
            return Response({'errors': 'Рецепт не существует!'},
                            status=status.HTTP_400_BAD_REQUEST)
        return data
