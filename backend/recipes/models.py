from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()


class Tag(models.Model):
    '''Модель тэгов.'''

    name = models.CharField(
        'Название тэга',
        max_length=200,
        unique=True,
    )
    color = models.CharField(
        'Цвет',
        max_length=7,
        unique=True,
        default='#ffffff',
    )
    slug = models.SlugField(
        'Слаг тэга',
        unique=True,
    )

    class Meta:
        verbose_name = 'Тэг'
        verbose_name_plural = 'Тэги'

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    '''Модель ингредиентов.'''

    name = models.CharField(
        'Название ингредиента',
        max_length=200,
    )
    measurement_unit = models.CharField(
        max_length=200,
        verbose_name='Единицы измерения',
    )

    class Meta:
        ordering = ('-id',)
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'

    def __str__(self):
        return self.name


class Recipe(models.Model):
    """Модель рецептов."""

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=False,
        related_name='recipes',
        verbose_name='Автор рецепта',
    )
    name = models.CharField(
        'Название рецепта',
        max_length=200,
        help_text='Введите название рецепта',
    )
    text = models.TextField(
        'Описание рецепта',
        help_text='Введите описание рецепта',
    )
    image = models.ImageField(
        'Изображение',
        upload_to='recipes/',
        help_text='Прикрепите изображение',
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        related_name='recipes',
        verbose_name='Ингредиенты',
        help_text='Выберите ингредиенты',
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='recipes',
        verbose_name='Тэги',
        help_text='Выберите тэги',
    )
    cooking_time = models.PositiveSmallIntegerField(
        'Время приготовления',
        validators=[
            MinValueValidator(
                1,
                'Время приготовления должно быть больше 1'
            )
        ],
        help_text='Время приготовления в минутах',
    )

    class Meta:
        ordering = ['-id']
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    """Модель для добавления ингредиентов в рецепте."""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='recipe_ingredients',
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент',
    )
    amount = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1, message='Минимальное количество 1!')],
        verbose_name='Количество',
    )

    class Meta:
        verbose_name = 'Ингредиент в рецепте',
        verbose_name_plural = 'Ингредиенты в рецепте'

    def __str__(self):
        return (f'{self.recipe.name}: '
                f'{self.ingredient.name} - '
                f'{self.amount} '
                f'{self.ingredient.measurement_unit}')


class Favorite(models.Model):
    """Модель подписок."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_favorites',
        verbose_name='Владелец списка избранных рецептов',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        null=True,
        related_name='favorites',
        verbose_name='Избранные рецепты',
    )

    class Meta:
        verbose_name = 'Список избранных рецептов'
        verbose_name_plural = 'Списки избранных рецептов'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_favorites'
            ),
        ]

    def __str__(self):
        return f'Избранный рецепт {self.user}'


class ShoppingCart(models.Model):
    """Модель для добавления рецептов в корзину."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shopping_list',
        verbose_name='Владелец списка покупок',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        null=True,
        related_name='shopping_list',
        verbose_name='Рецепт из списка покупок',
    )

    class Meta:
        verbose_name = 'Список покупок'
        verbose_name_plural = 'Списки покупок'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_recipe'
            ),
        ]

    def __str__(self):
        return f'Рецепт из корзины покупок {self.user}'