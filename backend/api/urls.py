from django.urls import path, include
from rest_framework.routers import DefaultRouter
from djoser.views import TokenCreateView, TokenDestroyView

from .views import (
    UserViewSet, PasswordChangeView, IngredientViewSet,
    TagViewSet, RecipeViewSet
)

router = DefaultRouter()
router.register('users', UserViewSet)
router.register('ingredients', IngredientViewSet)
router.register('tags', TagViewSet)
router.register('recipes', RecipeViewSet)

urlpatterns = [
    path('auth/token/login/', TokenCreateView.as_view(),
         name='create_token'),
    path('auth/token/logout/', TokenDestroyView.as_view(),
         name='destroy_token'),
    path('users/set_password/', PasswordChangeView.as_view(),
         name='set_password'),
    path('', include(router.urls)),
]
