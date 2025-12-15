import os
import asyncio
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Update
from telegram.ext import Application
from bot.bot_handler import setup_handlers


class Command(BaseCommand):
    help = 'Запускает Telegram бота'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            help='Telegram Bot Token',
            default=None,
        )

    def handle(self, *args, **options):
        # Получаем токен из аргументов, переменной окружения или settings
        token = options.get('token') or os.getenv('TELEGRAM_BOT_TOKEN') or getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        
        if not token:
            self.stdout.write(
                self.style.ERROR(
                    '❌ Токен бота не найден!\n'
                    'Установите токен одним из способов:\n'
                    '1. Переменная окружения: export TELEGRAM_BOT_TOKEN="your_token"\n'
                    '2. Аргумент команды: python manage.py runbot --token your_token\n'
                    '3. В settings.py: TELEGRAM_BOT_TOKEN = "your_token"'
                )
            )
            return
        
        self.stdout.write(self.style.SUCCESS('🤖 Запуск Telegram бота...'))
        
        # Создаем приложение бота
        application = Application.builder().token(token).build()
        
        # Настраиваем обработчики
        setup_handlers(application)
        
        # Запускаем бота
        self.stdout.write(self.style.SUCCESS('✅ Бот запущен и готов к работе!'))
        application.run_polling(allowed_updates=Update.ALL_TYPES)

