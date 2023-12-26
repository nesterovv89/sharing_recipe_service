from django.core.validators import RegexValidator

hex_validator = RegexValidator(
    regex=r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$',
    message='Цвет должен быть в формате HEX, например #ffffff.',
)
