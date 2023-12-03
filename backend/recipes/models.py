from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class Tag(models.Model):
    name = models.CharField('Название', max_length=200,
                            unique=True)
    color = models.CharField('Цвет', max_length=7,
                             unique=True)
    slug = models.SlugField('Слаг', unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = 'тег'
        verbose_name_plural = 'теги'


class Ingredient(models.Model):
    name = models.CharField('Название', max_length=200)
    measurement_unit = models.CharField('Единица измерения',
                                        max_length=200)

    def __str__(self) -> str:
        return f'{self.name}, {self.measurement_unit}'

    class Meta:
        verbose_name = 'ингредиент'
        verbose_name_plural = 'ингредиенты'


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
    cooking_time = models.PositiveIntegerField('Время приготовления')

    class Meta:
        ordering = ['-id']
        verbose_name = 'рецепт'
        verbose_name_plural = 'рецепты'

    def __str__(self) -> str:
        return self.name


class RecipeIngredient(models.Model):
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    amount = models.IntegerField()

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
    user_follows = models.ForeignKey(User,
                                     on_delete=models.CASCADE,
                                     related_name='user_follows')
    user_following = models.ForeignKey(User,
                                       on_delete=models.CASCADE,
                                       related_name='user_following'
                                       )

    class Meta:
        unique_together = ('user_follows', 'user_following')
        verbose_name = 'фолловеры'
        verbose_name_plural = 'фолловеры'

    def __str__(self) -> str:
        return (
            f'{self.user_follows.get_username()} '
            f'следит за {self.user_following.get_username()}'
        )


class UserRecipe(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    is_favorited = models.BooleanField(default=False)
    is_in_shopping_cart = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f'{self.user.get_username()} {self.recipe.name}'

    class Meta:
        verbose_name = 'рецепты пользователя'
        verbose_name_plural = 'рецепты пользователей'
