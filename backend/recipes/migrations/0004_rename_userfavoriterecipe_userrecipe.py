# Generated by Django 3.2.3 on 2023-11-22 20:26

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('recipes', '0003_userfavoriterecipe_is_in_shopping_cart'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='UserFavoriteRecipe',
            new_name='UserRecipe',
        ),
    ]