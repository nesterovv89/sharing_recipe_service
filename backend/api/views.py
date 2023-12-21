from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Subquery, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Tag)
from users.models import Follow
from .filters import IngredientFilter, RecipeFilter
from .pagination import CustomPaginator
from .permissions import IsAuthorOrReadOnly
from .serializers import (IngredientSerializer, RecipeCreateSerializer,
                          RecipeGetSerializer, SetPasswordSerializer,
                          ShortRecipeSerializer, SubscribeSerializer,
                          SubscriptionSerializer, TagSerializer,
                          UserCreateSerializer, UserReadSerializer)

User = get_user_model()


class UserViewSet(UserViewSet):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    pagination_class = CustomPaginator

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return UserReadSerializer
        return UserCreateSerializer

    @action(
        methods=('get',),
        detail=False,
        permission_classes=[IsAuthenticated],
    )
    def me(self, request):
        """Профиль"""

        serializer = UserReadSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'],
            permission_classes=(IsAuthenticated,))
    def set_password(self, request):
        serializer = SetPasswordSerializer(request.user, data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
        return Response({'detail': 'Пароль успешно изменен!'},
                        status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=[IsAuthenticated],
        pagination_class=CustomPaginator
    )
    def subscriptions(self, request):
        """Страница подписок пользователя"""
        user = request.user
        queryset = User.objects.filter(following__user=user)
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = SubscriptionSerializer(
            paginated_queryset, many=True, context={'request': request}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=('post', 'delete'),
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, id):
        user = self.request.user
        author = get_object_or_404(User, pk=id)
        if request.method == 'POST':
            Follow.objects.create(user=user, author=author)
            serializer = SubscribeSerializer(
                author, context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        else:
            subscription = Follow.objects.filter(user=user, author=author)
            if subscription.exists():
                subscription.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {'errors': 'Вы не подписаны на этого пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )


class RecipeViewSet(viewsets.ModelViewSet):
    """Страницы рецептов"""

    queryset = Recipe.objects.all()
    permission_classes = (IsAuthorOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    pagination_class = CustomPaginator

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        is_favorited_subquery = (
            Favorite.objects.filter(user=user, recipe=OuterRef('pk')).exists()
        )
        is_in_shopping_cart_subquery = (
            ShoppingCart.objects.filter(user=user,
                                        recipe=OuterRef('pk')).exists()
        )
        queryset = queryset.annotate(
            is_favorited=Subquery(is_favorited_subquery),
            is_in_shopping_cart=Subquery(is_in_shopping_cart_subquery)
        )
        return queryset

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return RecipeGetSerializer
        return RecipeCreateSerializer

    @action(
        methods=['post', 'delete'],
        detail=True,
        permission_classes=[IsAuthenticated],
        pagination_class=CustomPaginator,
    )
    def favorite(self, request, pk=None):
        """Страница продуктовой корзины"""

        if self.request.method == 'POST':
            return self.add_recipe_to_cart_or_favorite(
                Favorite, request.user, pk
            )
        else:
            return self.del_recipe_from_cart_or_favorite(
                Favorite, request.user, pk
            )

    @action(
        methods=('post', 'delete',),
        detail=True,
        permission_classes=(IsAuthenticated,),
        pagination_class=CustomPaginator
    )
    def shopping_cart(self, request, pk=None):
        """Страница продуктовой корзины"""

        if self.request.method == 'POST':
            return self.add_recipe_to_cart_or_favorite(
                ShoppingCart, request.user, pk
            )
        else:
            return self.del_recipe_from_cart_or_favorite(
                ShoppingCart, request.user, pk
            )

    def del_recipe_from_cart_or_favorite(self, model, user, pk):
        obj = model.objects.filter(user=user, recipe__id=pk)
        if obj.exists():
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'errors': 'Рецепт уже удален!'},
                        status=status.HTTP_400_BAD_REQUEST)

    def add_recipe_to_cart_or_favorite(self, model, user, pk):
        if model.objects.filter(user=user, recipe__id=pk).exists():
            return Response({'errors': 'Рецепт уже добавлен!'},
                            status=status.HTTP_400_BAD_REQUEST)
        recipe = get_object_or_404(Recipe, id=pk)
        model.objects.create(user=user, recipe=recipe)
        serializer = ShortRecipeSerializer(recipe)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(IsAuthenticated,)
    )
    def download_shopping_cart(self, request):
        """Выгрузка списка покупок"""

        buy_list = RecipeIngredient.objects.filter(
            recipe__in__user=request.user
        ).values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).annotate(
            amount=Sum('amount')
        )
        shopping_list = ['Список покупок:\n']
        for item in buy_list:
            ingredient = Ingredient.objects.get(pk=item['ingredient'])
            amount = item['amount']
            shopping_list += (
                f'{ingredient.name}, {amount} '
                f'{ingredient.measurement_unit}\n'
            )
        response = HttpResponse(shopping_list, content_type='text/plain')
        response['Content-Disposition'] = \
            'attachment; filename="shopping_cart.txt"'
        return response


class IngredientViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    """Получение списка ингридиентов"""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny, )
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


class TagViewSet(mixins.ListModelMixin,
                 mixins.RetrieveModelMixin,
                 viewsets.GenericViewSet):
    """Получение списка тэгов"""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None
