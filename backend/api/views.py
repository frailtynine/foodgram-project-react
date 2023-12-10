from rest_framework import (viewsets, generics, status,
                            filters, permissions, mixins)
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.http import HttpResponse

from .serializers import (
    UserSerializer, ChangePasswordSerializer, IngredientSerializer,
    TagSerializer, RecipeSerializer, UserFollowingSerializer,
    SimpleRecipeSerializer
)
from .filters import RecipeFilter
from .pagination import CustomPagination
from .permissions import IsOwnerOrReadOnly
from recipes.models import (Ingredient, Tag, Recipe, UserFollowing,
                            RecipeFavorite, RecipeInShoppingCart)


User = get_user_model()


class UserViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    pagination_class = CustomPagination
    permission_classes = (permissions.AllowAny,)

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
            # DELETE route
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
    filter_backends = (filters.SearchFilter,)
    search_fields = ['^name']
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    permission_classes = (permissions.AllowAny,)
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    MODELS = {
        'is_favorited': RecipeFavorite,
        'is_in_shopping_cart': RecipeInShoppingCart
    }

    serializer_class = RecipeSerializer
    queryset = Recipe.objects.all()
    filterset_class = RecipeFilter
    filterset_fields = ('author', 'tags')
    pagination_class = CustomPagination
    permission_classes = (IsOwnerOrReadOnly, )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        queryset = Recipe.objects.all()
        return queryset.distinct()

    def __get_user_recipe_connection(self, pk, field, request):
        """Handles connections between users and recipes.

        Expects 'is_favorited' or 'is_in_shopping_cart' in field argument.

        Returns relevant response.
        """
        try:
            recipe = Recipe.objects.get(id=pk)
        except Recipe.DoesNotExist:
            if request.method == 'POST':
                return Response({'Error': 'Recipe doesnt exist'},
                                status=status.HTTP_400_BAD_REQUEST)
            return Response(status=status.HTTP_404_NOT_FOUND)
        existing_user_recipe = self.__check_existing_user_recipe(
            request, recipe, field=field
        )
        model = self.MODELS.get(field)
        if request.method == 'POST':
            if existing_user_recipe:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            model.objects.create(
                user=request.user,
                recipe=recipe,
                **{field: True}
            )
            serializer = SimpleRecipeSerializer(recipe)
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED)
        # DELETE route
        if not existing_user_recipe:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        existing_user_recipe.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def __check_existing_user_recipe(self, request, recipe, field):
        model = self.MODELS.get(field)
        return model.objects.filter(
            user=request.user,
            recipe=recipe,
            **{field: True}
        ).first()

    @action(methods=['POST', 'DELETE'], detail=True)
    def shopping_cart(self, request, pk):
        response = self.__get_user_recipe_connection(
            pk,
            'is_in_shopping_cart',
            request
        )
        return response

    def prepare_shopping_cart(self, request):
        user_recipes = RecipeInShoppingCart.objects.filter(
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
        response = self.__get_user_recipe_connection(
            pk,
            'is_favorited',
            request
        )
        return response
