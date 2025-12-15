import secrets
from django.db import models
from django.utils import timezone
from datetime import timedelta


class TelegramUser(models.Model):
    """Пользователь Telegram"""
    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name="Username")
    first_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Имя")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Пользователь Telegram"
        verbose_name_plural = "Пользователи Telegram"
    
    def __str__(self):
        return f"{self.first_name or self.username or self.telegram_id} ({self.telegram_id})"


class Group(models.Model):
    """Группа для розыгрыша Тайного Санты"""
    
    STATUS_CHOICES = [
        ('active', 'Активна'),
        ('drawn', 'Жеребьевка проведена'),
        ('distribution', 'Расдача подарков'),
        ('closed', 'Закрыта'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Название группы")
    code = models.CharField(max_length=20, unique=True, verbose_name="Код группы")
    owner = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="owned_groups",
        verbose_name="Владелец"
    )
    description = models.TextField(verbose_name="Описание подарка", help_text="Ориентировочная сумма, характер подарка")
    gift_via_bot = models.BooleanField(default=False, verbose_name="Подарки через бота")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Статус")
    draw_date = models.DateField(null=True, blank=True, verbose_name="Дата проведения жеребьевки")
    gift_distribution_date = models.DateField(null=True, blank=True, verbose_name="Дата расдачи подарков")
    close_date = models.DateField(null=True, blank=True, verbose_name="Дата закрытия группы")
    is_closed = models.BooleanField(default=False, verbose_name="Группа закрыта")  # Оставляем для обратной совместимости
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    drawn_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата розыгрыша")
    
    class Meta:
        verbose_name = "Группа"
        verbose_name_plural = "Группы"
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @staticmethod
    def generate_code():
        """Генерирует уникальный код группы"""
        while True:
            code = secrets.token_urlsafe(8).upper()[:8]
            if not Group.objects.filter(code=code).exists():
                return code
    
    def can_add_participants(self):
        """Проверяет, можно ли добавлять участников"""
        return self.status == 'active'
    
    def can_draw(self):
        """Проверяет, можно ли провести розыгрыш"""
        return self.status == 'active' and self.participants.count() >= 2
    
    def save(self, *args, **kwargs):
        """Автоматически устанавливаем дату закрытия, если не указана"""
        if not self.close_date and self.gift_distribution_date:
            self.close_date = self.gift_distribution_date + timedelta(days=1)
        # Синхронизируем is_closed со статусом
        self.is_closed = (self.status == 'closed')
        super().save(*args, **kwargs)


class Participant(models.Model):
    """Участник группы"""
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Группа"
    )
    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="participations",
        verbose_name="Пользователь"
    )
    name = models.CharField(max_length=200, verbose_name="Имя участника")
    gift_message = models.TextField(blank=True, null=True, verbose_name="Подарок (сообщение)")
    gift_photo_file_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Подарок (фото file_id)")
    gift_sent = models.BooleanField(default=False, verbose_name="Подарок отправлен боту")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата вступления")
    
    class Meta:
        verbose_name = "Участник"
        verbose_name_plural = "Участники"
        unique_together = [['group', 'user']]
    
    def __str__(self):
        return f"{self.name} в группе {self.group.name}"


class Draw(models.Model):
    """Результат розыгрыша - кто кому дарит подарок"""
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="draws",
        verbose_name="Группа"
    )
    giver = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="gifts_given",
        verbose_name="Даритель"
    )
    receiver = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="gifts_received",
        verbose_name="Получатель"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Результат розыгрыша"
        verbose_name_plural = "Результаты розыгрышей"
        unique_together = [['group', 'giver']]
    
    def __str__(self):
        return f"{self.giver.name} -> {self.receiver.name} ({self.group.name})"
