# sharing_recipe_service

### Социальная сеть, которая позволяет размещать свои кулинарные рецепты, подписываться на интересных авторов, создавать списки покупок на основе выбранных рецептов.

## Технологии:
* Python
* Django
* Nginx
* Docker
* Gunicorn


## Проект можно запускать в двух версиях: локальная, которая подойдет для тестирования и дополнительной разработки проекта, и продакшн версия, которая используется для развертывания проекта на боевом сервере, её используют для тестирования и доработки проекта в реальных условиях.

## Запуск проекта:

# Для локального запуска проекта:
- Скопировать репозиторий `git clone https://github.com/nesterovv89/foodgram-project-react.git` себе на ПК
- Создать и активировать виртуальное окружение `python3 -m venv venv`, `source venv/bin/activate`
- Применить зависимости `pip install -r requirements.txt`
- Выполнить команду для запуска `docker compose up`
- Провести сбор статики и выполнить миграции, в директории, где находится файл docker-compose:
```
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py collectstatic
docker compose exec backend cp -r /app/collected_static/. /backend_static/static/
```
- Загрузить в БД ингредиенты и базовый набор тегов:
```

docker compose exec backend python manage.py csv_data
docker compose exec backend python manage.py load_tags
```
- Проект будет доступен по адресу http://localhost:8010/

# Для запуска проекта на сервере:
- В корень проекта необходимо перенести файл docker-compose.production.yml
- В корне проекта создать файл .env для хранения секретных данных, заполнить согласно образца .env.example
- Для скачивания образов и создания необходимых контейнеров необходимо выполнить команду `sudo docker compose -f docker-compose.production.yml up`
- После запуска контейнеров необходимо выполнить миграции и провести сбор статики:
```
sudo docker compose -f docker-compose.production.yml exec backend python manage.py migrate
sudo docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic
sudo docker compose -f docker-compose.production.yml exec backend cp -r /app/collected_static/. /static/
```
- Загрузить в БД ингредиенты и базовый набор тегов:
```
sudo docker compose -f docker-compose.production.yml exec backend python manage.py csv_data
sudo docker compose -f docker-compose.production.yml exec backend python manage.py load_tags
```
- Проект станет доступен по адресу, который вы указали в .env файле

[![Main foodgram workflow](https://github.com/nesterovv89/foodgram-project-react/actions/workflows/main.yml/badge.svg)](https://github.com/nesterovv89/foodgram-project-react/actions/workflows/main.yml)

В данный момент проект доступен по этой [ссылке](https://food-gram0.ddns.net) 
Логин администратора admin@admin.com Пароль Praktikum+123



Автор [Павел Нестеров](https://github.com/nesterovv89)  

