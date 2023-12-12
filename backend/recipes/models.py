from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from colorfield.fields import ColorField

from .validators import validate_positive


User = get_user_model()


class Tag(models.Model):
    name = models.CharField('Название', max_length=200,
                            unique=True)
    color = ColorField('Цвет', unique=True)
    slug = models.SlugField('Слаг', unique=True)

    class Meta:
        verbose_name = 'тег'
        verbose_name_plural = 'теги'

    def save(self, *args, **kwargs):
        self.color = self.color.upper()
        super().save(*args, **kwargs)

    def clean(self):
        if (
            Tag.objects
            .filter(color__iexact=self.color)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError('Цвет должен быть уникальным')

    def __str__(self) -> str:
        return self.name


class Ingredient(models.Model):
    name = models.CharField('Название', max_length=200)
    measurement_unit = models.CharField('Единица измерения',
                                        max_length=200)

    class Meta:
        verbose_name = 'ингредиент'
        verbose_name_plural = 'ингредиенты'

    def __str__(self) -> str:
        return f'{self.name}, {self.measurement_unit}'


class Recipe(models.Model):
    author = models.ForeignKey(User,
                               on_delete=models.CASCADE,
                               related_name='recipe_author',
                               verbose_name='Автор')
    ingredients = models.ManyToManyField(Ingredient,
                                         through='RecipeIngredient',
                                         verbose_name='Ингредиенты')
    tags = models.ManyToManyField(Tag,
                                  verbose_name='Теги')
    image = models.ImageField('Изображение', upload_to='recipes/')
    name = models.CharField('Название', max_length=200)
    text = models.TextField('Текст')
    cooking_time = models.PositiveSmallIntegerField(
        'Время приготовления',
        validators=(validate_positive,)
    )

    class Meta:
        ordering = ('-id',)
        verbose_name = 'рецепт'
        verbose_name_plural = 'рецепты'

    def __str__(self) -> str:
        return self.name


class RecipeIngredient(models.Model):
    ingredient = models.ForeignKey(Ingredient,
                                   on_delete=models.CASCADE,
                                   verbose_name='ингредиент')
    recipe = models.ForeignKey(Recipe,
                               on_delete=models.CASCADE,
                               verbose_name='рецепт')
    amount = models.PositiveSmallIntegerField(
        'Количество',
        validators=(validate_positive,)
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['ingredient', 'recipe'],
                name='unique_recipe_ingredient'
            )
        ]
        verbose_name = 'ингредиенты рецепта'
        verbose_name_plural = 'ингредиенты рецептов'

    def __str__(self) -> str:
        return f'{self.recipe.name}: {self.ingredient.name}'


class UserFollowing(models.Model):
    user_follows = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_follows',
        verbose_name='Пользователь')
    user_following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_following',
        verbose_name='Подписка на пользователя'
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user_follows', 'user_following'],
                name='unique_user_following'
            )
        ]
        verbose_name = 'фолловеры'
        verbose_name_plural = 'фолловеры'

    def __str__(self) -> str:
        return (
            f'{self.user_follows.get_username()} '
            f'следит за {self.user_following.get_username()}'
        )

    def clean(self):
        if self.user_follows == self.user_following:
            raise ValidationError('Нельзя подписаться на себя')


class AbstractUserRecipe(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь')
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт')

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f'{self.user.get_username()} {self.recipe.name}'


class RecipeFavorite(AbstractUserRecipe):
    class Meta:
        verbose_name = 'рецепт в избранном'
        verbose_name_plural = 'рецепты в избранном'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_recipefavorite'
            )
        ]


class RecipeInShoppingCart(AbstractUserRecipe):
    class Meta:
        verbose_name = 'рецепт в корзине'
        verbose_name_plural = 'рецепты в корзине'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_recipeinshoppingcart'
            )
        ]
