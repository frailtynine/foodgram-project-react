import base64

from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from rest_framework import serializers, validators

from recipes.models import (
    UserFollowing, Ingredient, Tag, Recipe, RecipeIngredient,
    UserRecipe
)


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
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(
        required=True,
        validators=[validators.UniqueValidator(
            queryset=User.objects.all()
        )]
    )

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name',
                  'last_name', 'is_subscribed', 'password')
        extra_kwargs = {'email': {'required': True},
                        'first_name': {'required': True},
                        'last_name': {'required': True}
                        }

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request.user.is_authenticated:
            following = UserFollowing.objects.filter(
                user_follows=request.user,
                user_following=obj).exists()
            return following
        return False

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        if request.method == 'POST':
            ret.pop('is_subscribed')
        return ret

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


class UserRecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRecipe
        fields = ('user', 'is_favorite', 'is_in_shopping_cart')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(write_only=True)
    ingredient = IngredientSerializer(read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount', 'ingredient')

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ingredient = IngredientSerializer(instance.ingredient).data
        return {
            'id': ingredient['id'],
            'name': ingredient['name'],
            'measurement_unit': ingredient['measurement_unit'],
            'amount': ret['amount']
        }


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
    cooking_time = serializers.IntegerField()
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
        return self.get_recipe_status(
            obj=obj,
            field_name='is_favorited'
        )

    def get_is_in_shopping_cart(self, obj):
        return self.get_recipe_status(
            obj=obj,
            field_name='is_in_shopping_cart'
        )

    def get_recipe_status(self, obj, field_name):
        user = self.context['request'].user
        if user.is_authenticated:
            return UserRecipe.objects.filter(
                user=user,
                recipe=obj,
                **{field_name: True}
            ).exists()
        return False

    def validate(self, data):
        # user validation
        if (
            self.instance
            and self.instance.author != self.context['request'].user
        ):
            raise PermissionDenied(
                'You do not have permission to update this recipe'
            )
        # ingredients validation.
        ingredients_data = data.get('recipeingredient_set')
        if not ingredients_data or len(ingredients_data) == 0:
            raise serializers.ValidationError('Ingredients field is empty')
        for ingredient in ingredients_data:
            if not Ingredient.objects.filter(id=ingredient['id']).exists():
                raise serializers.ValidationError('Object not in database')
            if ingredient['amount'] < 1:
                raise serializers.ValidationError('Amount is below 1')
        ingredient_ids = [ingredient['id'] for ingredient in ingredients_data]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError('Ingredients must be unique')
        # tags validation.
        tags_data = data.get('tags')
        if not tags_data or len(tags_data) == 0:
            raise serializers.ValidationError('Tag field is empty')
        tag_ids = [tag.id for tag in tags_data]
        if len(tag_ids) != len(set(tag_ids)):
            raise serializers.ValidationError('Tags must be unique')
        # cooking time validation
        cooking_time = data.get('cooking_time')
        if cooking_time is not None and cooking_time < 1:
            print(cooking_time)
            raise serializers.ValidationError(
                'Cooking time must be at least 1'
            )
        return data

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        ingredients_data = validated_data.pop('recipeingredient_set')
        tags_data = validated_data.pop('tags')
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)
        for ingredient in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=Ingredient.objects.get(id=ingredient['id']),
                amount=ingredient['amount']
            )
        return recipe

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
        for ingredient in ingredients_data:
            RecipeIngredient.objects.update_or_create(
                recipe=instance,
                ingredient=Ingredient.objects.get(id=ingredient['id']),
                defaults={'amount': ingredient['amount']}
            )
        return instance

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        tags = instance.tags.all()
        tags_list = [{'id': tag.id,
                      'name': tag.name,
                      'color': tag.color,
                      'slug': tag.slug} for tag in tags]
        ret['tags'] = tags_list
        return ret


class SimpleRecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
