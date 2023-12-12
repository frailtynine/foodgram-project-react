from django_filters import rest_framework as rest_filters
from django_filters import ModelMultipleChoiceFilter

from recipes.models import Recipe, Tag, RecipeFavorite, RecipeInShoppingCart


class RecipeFilter(rest_filters.FilterSet):
    tags = ModelMultipleChoiceFilter(
        queryset=Tag.objects.all(),
        field_name='tags__slug',
        to_field_name='slug',
    )
    is_favorited = rest_filters.BooleanFilter(
        method='filter_is_favorited'
    )
    is_in_shopping_cart = rest_filters.BooleanFilter(
        method='filter_is_in_shopping_cart'
    )

    class Meta:
        model = Recipe
        fields = ('author', 'tags',
                  'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, value):
        if value and self.request.user.is_authenticated:
            if RecipeFavorite.objects.filter(
                user=self.request.user
            ).exists():
                return queryset.filter(
                    id__in=RecipeFavorite.objects.filter(
                        user=self.request.user,
                    ).values_list('recipe', flat=True)
                )
        return queryset.none()

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if value and self.request.user.is_authenticated:
            if RecipeInShoppingCart.objects.filter(
                user=self.request.user
            ).exists():
                return queryset.filter(
                    id__in=RecipeInShoppingCart.objects.filter(
                        user=self.request.user
                    ).values_list('recipe', flat=True)
                )
        return queryset.none()
