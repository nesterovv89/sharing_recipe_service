from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.admin import display

from .models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                     ShoppingCart, Tag)


class RecipeIngredientInlineFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        ingredient_count = 0
        for form in self.forms:
            if form.cleaned_data.get('DELETE', False):
                continue
            if form.cleaned_data.get('ingredient'):
                ingredient_count += 1
        if ingredient_count < 1:
            raise ValidationError('Должен быть минимум 1 ингредиент')


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    min_num = 1
    extra = 1
    formset = RecipeIngredientInlineFormSet


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'author', 'count_favorites')
    readonly_fields = ('count_favorites',)
    list_filter = ('author', 'name', 'tags')
    inlines = [RecipeIngredientInline, ]
    exclude = ('ingredients', )

    @display(description='Количество в избранных')
    def count_favorites(self, obj):
        return obj.favorites.count()


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_unit', 'id')
    list_filter = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'slug',)


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe',)


@admin.register(Favorite)
class FavouriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'recipe',)


@admin.register(RecipeIngredient)
class IngredientInRecipe(admin.ModelAdmin):
    list_display = ('recipe', 'ingredient', 'amount', 'id')
