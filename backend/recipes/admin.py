from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import (Ingredient, Recipe, RecipeIngredient, UserFollowing,
                     Tag, RecipeFavorite, RecipeInShoppingCart)


User = get_user_model()
admin.site.unregister(User)


class CustomUserAdmin(UserAdmin):
    search_fields = ('first_name', 'last_name', 'email')


class RecipeAdmin(admin.ModelAdmin):
    search_fields = ('author', 'name', 'tags__name')
    list_filter = ('tags__name',)
    readonly_fields = ('favorited_count',)
    list_display = ('name', 'author')

    def favorited_count(self, obj):
        count = RecipeFavorite.objects.filter(
            recipe=obj,
            is_favorited=True
        ).count()
        first_digit = int(str(count[0]))
        if 1 < first_digit < 5:
            return f'{count} раза'
        return f'{count} раз'

    favorited_count.short_description = 'Добавлено в избранное'


class IngredientAdmin(admin.ModelAdmin):
    search_fields = ['name']


admin.site.register(Ingredient, IngredientAdmin)
admin.site.register(Recipe, RecipeAdmin)
admin.site.register(RecipeIngredient)
admin.site.register(UserFollowing)
admin.site.register(Tag)
admin.site.register(User, CustomUserAdmin)
admin.site.register(RecipeFavorite)
admin.site.register(RecipeInShoppingCart)
