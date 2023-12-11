import base64

from django.db import transaction
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from rest_framework import serializers, validators

from recipes.models import (
    UserFollowing, Ingredient, Tag, Recipe, RecipeIngredient,
    RecipeFavorite, RecipeInShoppingCart
)
from .validators import validate_non_empty


MAX_SMALL_INT_VALUE = 32767


User = get_user_model()


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)

        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, max_length=150)
    email = serializers.EmailField(
        required=True,
        validators=(validators.UniqueValidator(
            queryset=User.objects.all()
        ),)
    )
    first_name = serializers.CharField(validators=[validate_non_empty],
                                       max_length=150)
    last_name = serializers.CharField(validators=[validate_non_empty],
                                      max_length=150)

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'is_subscribed', 'password')
        extra_kwargs = {'email': {'required': True},
                        'first_name': {'required': True},
                        'last_name': {'required': True}
                        }

    def get_is_subscribed(self, obj):
        return (
            self.context.get('request').user.is_authenticated
            and UserFollowing.objects.filter(
                user_follows=self.context['request'].user,
                user_following=obj
            ).exists()
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        if request.method == 'POST':
            representation.pop('is_subscribed')
        return representation

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        instance = self.Meta.model(**validated_data)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance


class UserFollowingSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user_following.email')
    id = serializers.IntegerField(source='user_following.id')
    username = serializers.CharField(source='user_following.username')
    first_name = serializers.CharField(source='user_following.first_name')
    last_name = serializers.CharField(source='user_following.last_name')
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = UserFollowing
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes', 'recipes_count')

    def get_recipes(self, obj):
        recipes_limit = self.context['request'].query_params.get(
            'recipes_limit', None
        )
        recipes = obj.user_following.recipe_author.all()
        if recipes_limit is not None:
            recipes = recipes[:int(recipes_limit)]
        serializer = RecipeSerializer(recipes, many=True, context=self.context)
        return [{field: recipe[field] for field
                in ('id', 'name', 'image', 'cooking_time')}
                for recipe in serializer.data]

    def get_recipes_count(self, obj):
        return obj.user_following.recipe_author.count()

    def get_is_subscribed(self, obj):
        user_serializer = UserSerializer(obj.user_following,
                                         context=self.context)
        return user_serializer.get_is_subscribed(obj.user_following)


class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=True)
    current_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        request = self.context.get('request')
        if not request.user.check_password(value):
            raise serializers.ValidationError('Incorrect password')
        return value

    def update(self, instance, validated_data):
        new_password = validated_data['new_password']
        current_password = validated_data['current_password']
        if new_password != current_password:
            instance.set_password(new_password)
            instance.save()
            return instance
        raise serializers.ValidationError('Incorrect new password')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class TagSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()

    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(max_value=MAX_SMALL_INT_VALUE)
    name = serializers.CharField(source='ingredient.name', required=False)
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit',
        required=False
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount', 'name', 'measurement_unit')

    def validate_ingredient(self, ingredient):
        if not Ingredient.objects.filter(id=ingredient['id']).exists():
            raise serializers.ValidationError('Object not in database')
        return ingredient

    def validate_amount(self, amount):
        if amount < 1:
            raise serializers.ValidationError('Amount is below 1')
        return amount

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['id'] = instance.ingredient_id
        return representation


class RecipeSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source='recipeingredient_set',
        many=True
    )
    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
    )
    image = Base64ImageField()
    cooking_time = serializers.IntegerField(max_value=MAX_SMALL_INT_VALUE)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'author', 'ingredients', 'tags', 'image',
                  'name', 'text', 'cooking_time', 'is_favorited',
                  'is_in_shopping_cart')
        read_only_fields = ('is_favorited',
                            'is_in_shopping_cart')

    def get_is_favorited(self, obj):
        return (
            self.context.get('request').user.is_authenticated
            and RecipeFavorite.objects.filter(
                user=self.context['request'].user,
                recipe=obj,
            ).exists()
        )

    def get_is_in_shopping_cart(self, obj):
        return (
            self.context.get('request').user.is_authenticated
            and RecipeInShoppingCart.objects.filter(
                user=self.context['request'].user,
                recipe=obj,
            ).exists()
        )

    def validate_tags(self, tags_data):
        if not tags_data:
            raise serializers.ValidationError('Tag field is empty')
        if len(tags_data) != len(set(tags_data)):
            raise serializers.ValidationError('Tags must be unique')
        return tags_data

    def validate_cooking_time(self, cooking_time):
        if cooking_time < 1:
            raise serializers.ValidationError(
                'Cooking time must be at least 1'
            )
        return cooking_time

    def validate_ingredients(self, ingredients_data):
        if not ingredients_data:
            raise serializers.ValidationError('Ingredients field is empty')
        ingredient_ids = [ingredient['id'] for ingredient in ingredients_data]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError('Ingredients must be unique')
        return ingredients_data

    def __create_ingredients(self, ingredients_data, recipe):
        for ingredient in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient['id'],
                amount=ingredient['amount']
            )

    def __update_ingredients(self, ingredients_data, recipe):
        recipe.ingredients.clear()
        for ingredient in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient['id'],
                amount=ingredient['amount']
            )

    def validate(self, attrs):
        tags = attrs.get('tags')
        ingredients = attrs.get('recipeingredient_set')
        if not tags or not ingredients:
            raise serializers.ValidationError('All fields have to be present')
        return super().validate(attrs)

    @transaction.atomic
    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        ingredients_data = validated_data.pop('recipeingredient_set')
        tags_data = validated_data.pop('tags')
        # Я не знаю, как решить это иначе. В ТЗ нет ничего про
        # требования к рецептам, поэтому мы запретим создавать
        # рецепты с одинаковыми названиями, автором, текстом и временем
        # готовки. Если ожидается иное решение, мне нужна подсказка.
        duplicate_recipe = Recipe.objects.filter(
            author=validated_data['author'],
            name=validated_data['name'],
            text=validated_data['text'],
            cooking_time=validated_data['cooking_time']
        ).first()
        if duplicate_recipe:
            raise serializers.ValidationError(
                'Recipe with the same details already exists'
            )
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)
        self.__create_ingredients(ingredients_data, recipe)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('recipeingredient_set')
        tags_data = validated_data.pop('tags')
        instance.author = validated_data.get('author', instance.author)
        instance.image = validated_data.get('image', instance.image)
        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get('cooking_time',
                                                   instance.cooking_time)
        instance.save()
        instance.tags.set(tags_data)
        self.__update_ingredients(ingredients_data, instance)
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        tags = instance.tags.all()
        tags_list = TagSerializer(tags, many=True).data
        representation['tags'] = tags_list
        return representation


class SimpleRecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
