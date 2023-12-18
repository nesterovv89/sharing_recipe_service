from django.core.management import BaseCommand

from recipes.models import Tag


class Command(BaseCommand):
    help = 'Создание базовых тегов'

    def handle(self, *args, **kwargs):
        data = [
            {'name': 'Завтрак', 'color': '#e8eb34', 'slug': 'zavtrak'},
            {'name': 'Обед', 'color': '#34eba8', 'slug': 'obed'},
            {'name': 'Ужин', 'color': '#eb3480', 'slug': 'uzhin'}]
        Tag.objects.bulk_create(Tag(**tag) for tag in data)
        self.stdout.write(self.style.SUCCESS('Загрузка тегов успешна.'))