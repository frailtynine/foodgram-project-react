"""
Run python manage.py load_db after preparing and making migrations
to load data into ingredients table.
CSV file is expected to be in data folder of recipes app.
"""

from csv import DictReader
from django.core.management import BaseCommand

from recipes.models import Ingredient
from backend.settings import BASE_DIR


class Command(BaseCommand):

    def handle(self, *args, **options):
        file_path = 'recipes/data/ingredients.csv'
        reader = DictReader(
            open(BASE_DIR.joinpath(file_path), encoding='utf8'),
            fieldnames=['name', 'measurement_unit']
        )
        id = 1
        for row in reader:
            Ingredient.objects.update_or_create(
                id=id,
                name=row['name'],
                measurement_unit=row['measurement_unit']
            )
            id += 1
        print('Success')
