from rest_framework.serializers import ValidationError


def validate_non_empty(value):
    if value == '':
        raise ValidationError('This field cannot be empty.')
