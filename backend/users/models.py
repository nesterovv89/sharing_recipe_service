from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import constraints


class User(AbstractUser):
    username = models.CharField(
        max_length=150,
        unique=True,
    )
    first_name = models.CharField(
        max_length=150,
        blank=False,
    )
    last_name = models.CharField(
        max_length=150,
        blank=False,
    )
    email = models.EmailField(
        max_length=254,
        blank=False,
        unique=True,)
    password = models.CharField(
        max_length=150,
        blank=False,
    )
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ('username', 'first_name', 'last_name', 'password')

    class Meta:
        ordering = ['id']
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self) -> str:
        return self.username


class Follow(models.Model):
    user = models.ForeignKey(
        User,
        related_name='follower',
        on_delete=models.CASCADE,
    )
    author = models.ForeignKey(
        User,
        related_name='following',
        on_delete=models.CASCADE,
    )

    class Meta:
        constraints = [
            constraints.UniqueConstraint(fields=['user', 'author'],
                                         name='follow_unique')
        ]
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'

    def clean(self):
        if self.user == self.author:
            raise ValidationError('Подписка на себя невозможна')

    def __str__(self):
        return f'{self.user.username} - {self.author.username}'
