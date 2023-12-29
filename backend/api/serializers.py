import re

from django.core.exceptions import ValidationError
from django.db import transaction
from djoser.serializers import (UserCreateSerializer,
                                UserSerializer)
from drf_extra_fields.fields import Base64ImageField
from rest_framework import serializers

from recipes.constants import MIN_TIME_VALUE, MIN_INGREDIENT_VALUE
from users.models import Follow, User
from recipes.models import (Ingredient, Recipe, RecipeIngredient,
                            Tag)


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
        return bool(request and request.user.is_authenticated
                    and obj.following.filter(user=request.user).exists())


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
        request = self.context.get('request', None)
        return bool(request and request.user.is_authenticated
                    and obj.favorites.filter(user=request.user).exists())

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request', None)
        return bool(request and request.user.is_authenticated
                    and obj.shopping_list.filter(user=request.user).exists())


class AddIngredientRecipeSerializer(serializers.ModelSerializer):
    """ Сериализатор добавления ингредиентов """

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all()
    )
    amount = serializers.IntegerField()

    def validate_amount(self, value):
        if value <= MIN_INGREDIENT_VALUE:
            raise serializers.ValidationError(
                f'Кол-во ингредиента должно быть больше '
                f'{MIN_INGREDIENT_VALUE}'
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
        if value < MIN_TIME_VALUE:
            raise ValidationError(
                f'Время приготовления должно быть больше {MIN_TIME_VALUE}'
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


class SubscriptionSerializer(UserReadSerializer):
    '''Сериализатор информации о подписках'''
    recipes_count = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = UserReadSerializer.Meta.fields + (
            'recipes_count', 'recipes'
        )
        read_only_fields = ('email', 'username',
                            'first_name', 'last_name')

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        return (request and not request.user.is_anonymous
                and Follow.objects.filter(user=request.user,
                                          author=obj).exists())

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            try:
                limit = int(limit)
                recipes = recipes[:limit]
            except ValueError:
                raise ValueError('Количество рецептов должно быть численным')
        return ShortRecipeSerializer(recipes, many=True, read_only=True).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class SubscribeSerializer(serializers.ModelSerializer):
    ''' сериализатор оформления подписки'''

    class Meta:
        model = Follow
        fields = ('author', 'user')

    def validate(self, data):
        author = data.get('author')
        user = data.get('user')

        if user == author:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя')
        if user.follower.filter(author=author).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя')
        return data
