from django.core.exceptions import ValidationError


def validate_positive(value):
    if value == 0:
        raise ValidationError(
            'Value should be more than zero.'
        )
