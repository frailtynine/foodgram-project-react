from rest_framework import (viewsets, generics, status,
                            filters, permissions)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django_filters import rest_framework as rest_filters

from .serializers import (
    UserSerializer, ChangePasswordSerializer, IngredientSerializer,
    TagSerializer, RecipeSerializer, UserFollowingSerializer,
    SimpleRecipeSerializer
)
from recipes.models import (Ingredient, Tag, Recipe, UserFollowing,
                            UserRecipe)


User = get_user_model()


class RecipeFilter(rest_filters.FilterSet):
    tags = rest_filters.CharFilter(method='filter_tags')

    def filter_tags(self, queryset, name, value):
        tags = self.request.query_params.getlist('tags')
        return queryset.filter(tags__slug__in=tags)

    class Meta:
        model = Recipe
        fields = ['author', 'tags']


class CustomPagination(PageNumberPagination):
    page_size_query_param = 'limit'


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    pagination_class = CustomPagination
    permission_classes = [permissions.AllowAny]

    @action(methods=['GET'], detail=False)
    def me(self, request):
        if request.user.is_authenticated:
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    @action(methods=['GET'], detail=False)
    def subscriptions(self, request):
        if request.user.is_authenticated:
            subscriptions = UserFollowing.objects.filter(
                user_follows=request.user
            )
            page = self.paginate_queryset(subscriptions)
            serializer = UserFollowingSerializer(page, many=True,
                                                 context={'request': request})
            return self.get_paginated_response(serializer.data)
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    @action(methods=['POST', 'DELETE'], detail=True)
    def subscribe(self, request, pk):
        if request.user.is_authenticated:
            if request.method == 'POST':
                user_to_follow = get_object_or_404(User, id=pk)
                if user_to_follow == request.user:
                    return Response({'error': 'Cant follow yourself'},
                                    status=status.HTTP_400_BAD_REQUEST)
                elif UserFollowing.objects.filter(
                    user_follows=request.user,
                    user_following=user_to_follow
                ).exists():
                    return Response({'error': 'Already following'},
                                    status=status.HTTP_400_BAD_REQUEST)
                user_following = UserFollowing.objects.create(
                    user_follows=request.user,
                    user_following=user_to_follow
                )
                serializer = UserFollowingSerializer(
                    user_following,
                    context={'request': request},
                )
                return Response(serializer.data,
                                status=status.HTTP_201_CREATED)
            if request.method == 'DELETE':
                user_to_unfollow = get_object_or_404(User, id=pk)
                try:
                    user_following = UserFollowing.objects.get(
                        user_follows=request.user,
                        user_following=user_to_unfollow
                    )
                    user_following.delete()
                    return Response(status=status.HTTP_204_NO_CONTENT)
                except UserFollowing.DoesNotExist:
                    return Response(status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_401_UNAUTHORIZED)


class PasswordChangeView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        user = User.objects.get(id=request.user.id)
        serializer = self.get_serializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngredientSerializer
    queryset = Ingredient.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['^name']
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    serializer_class = RecipeSerializer
    queryset = Recipe.objects.all()
    filterset_class = RecipeFilter
    filterset_fields = ('author', 'tags')
    pagination_class = CustomPagination

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.author != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        queryset = Recipe.objects.all()
        if not self.request.user.is_authenticated:
            return queryset.distinct()
        is_favorited = self.request.query_params.get('is_favorited', None)
        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart',
            None
        )

        if is_favorited is not None:
            queryset = queryset.filter(
                id__in=UserRecipe.objects.filter(
                    user=self.request.user,
                    is_favorited=is_favorited
                ).values_list('recipe', flat=True)
            )

        if is_in_shopping_cart is not None:
            queryset = queryset.filter(
                id__in=UserRecipe.objects.filter(
                    user=self.request.user,
                    is_in_shopping_cart=is_in_shopping_cart
                ).values_list('recipe', flat=True)
            )

        return queryset.distinct()

    def get_auth(self, request):
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

    def get_recipe_or_400(self, pk):
        try:
            return Recipe.objects.get(id=pk)
        except Recipe.DoesNotExist:
            return None

    def check_existing_user_recipe(self, request, recipe, field):
        kwargs = {field: True}
        return UserRecipe.objects.filter(
            user=request.user,
            recipe=recipe,
            **kwargs
        ).first()

    @action(methods=['POST', 'DELETE'], detail=True)
    def shopping_cart(self, request, pk):
        self.get_auth(request)
        if request.method == 'POST':
            recipe = self.get_recipe_or_400(pk)
            if not recipe:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            existing_user_recipe = self.check_existing_user_recipe(
                request, recipe, field='is_in_shopping_cart'
            )
            if existing_user_recipe:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            UserRecipe.objects.create(
                user=request.user,
                recipe=recipe,
                is_in_shopping_cart=True
            )
            serializer = SimpleRecipeSerializer(recipe)
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED)
        if request.method == 'DELETE':
            recipe = get_object_or_404(Recipe, id=pk)
            existing_user_recipe = self.check_existing_user_recipe(
                request, recipe, field='is_in_shopping_cart'
            )
            if not existing_user_recipe:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            existing_user_recipe.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    def prepare_shopping_cart(self, request):
        user_recipes = UserRecipe.objects.filter(
                    user=request.user,
                    is_in_shopping_cart=True
        )
        ingredients = {}
        for user_recipe in user_recipes:
            for item in user_recipe.recipe.recipeingredient_set.all():
                if item.ingredient.name not in ingredients:
                    ingredients[item.ingredient.name] = {
                        'amount': item.amount,
                        'measurement_unit': item.ingredient.measurement_unit
                    }
                else:
                    ingredients[item.ingredient.name]['amount'] += item.amount
        return ingredients

    @action(methods=['GET'], detail=False)
    def download_shopping_cart(self, request):
        self.get_auth(request)
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_cart.txt"'
        )
        ingredients = self.prepare_shopping_cart(request)
        for name, data in ingredients.items():
            response.write(
                f"{name} ({data['measurement_unit']}) — {data['amount']} \n"
            )
        return response

    @action(methods=['POST', 'DELETE'], detail=True)
    def favorite(self, request, pk):
        self.get_auth(request)
        if request.method == 'POST':
            recipe = self.get_recipe_or_400(pk)
            if not recipe:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            existing_user_recipe = self.check_existing_user_recipe(
                request, recipe, field='is_favorited'
            )
            if existing_user_recipe:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            UserRecipe.objects.create(
                user=request.user,
                recipe=recipe,
                is_favorited=True
            )
            serializer = SimpleRecipeSerializer(recipe)
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED)
        if request.method == 'DELETE':
            recipe = get_object_or_404(Recipe, id=pk)
            existing_user_recipe = self.check_existing_user_recipe(
                request, recipe, field='is_favorited'
            )
            if not existing_user_recipe:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            existing_user_recipe.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return super().get_permissions()
