"""
Django management команда для включения/отключения DEBUG режима
"""
from django.core.management.base import BaseCommand
import re
import os
from pathlib import Path


class Command(BaseCommand):
    help = 'Включить или отключить DEBUG режим в settings.py'

    def add_arguments(self, parser):
        parser.add_argument(
            '--on',
            action='store_true',
            help='Включить DEBUG режим',
        )
        parser.add_argument(
            '--off',
            action='store_true',
            help='Отключить DEBUG режим',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Показать текущий статус DEBUG режима',
        )

    def handle(self, *args, **options):
        # Определяем путь к settings.py
        BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
        settings_file = BASE_DIR / 'santagame' / 'settings.py'
        
        if not settings_file.exists():
            self.stdout.write(
                self.style.ERROR(f'Файл settings.py не найден: {settings_file}')
            )
            return
        
        # Читаем файл
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Определяем текущий статус DEBUG
        debug_match = re.search(r'^DEBUG\s*=\s*(True|False)', content, re.MULTILINE)
        current_debug = None
        if debug_match:
            current_debug = debug_match.group(1) == 'True'
        
        # Если запрошен только статус
        if options['status']:
            if current_debug is None:
                self.stdout.write(
                    self.style.WARNING('DEBUG режим не найден в settings.py')
                )
            else:
                status = 'включен' if current_debug else 'отключен'
                self.stdout.write(
                    self.style.SUCCESS(f'DEBUG режим: {status}')
                )
            return
        
        # Определяем действие
        if options['on'] and options['off']:
            self.stdout.write(
                self.style.ERROR('Нельзя одновременно использовать --on и --off')
            )
            return
        
        if not options['on'] and not options['off']:
            # Если не указано действие, переключаем на противоположное
            new_debug = not current_debug if current_debug is not None else False
        elif options['on']:
            new_debug = True
        else:  # options['off']
            new_debug = False
        
        # Обновляем DEBUG
        if debug_match:
            # Заменяем существующую строку
            new_content = re.sub(
                r'^DEBUG\s*=\s*(True|False)',
                f'DEBUG = {new_debug}',
                content,
                flags=re.MULTILINE
            )
        else:
            # Добавляем DEBUG после SECRET_KEY, если его нет
            secret_key_match = re.search(r'^SECRET_KEY\s*=', content, re.MULTILINE)
            if secret_key_match:
                insert_pos = content.find('\n', secret_key_match.end())
                new_content = (
                    content[:insert_pos] +
                    f'\n\n# SECURITY WARNING: don\'t run with debug turned on in production!\n'
                    f'DEBUG = {new_debug}\n' +
                    content[insert_pos:]
                )
            else:
                self.stdout.write(
                    self.style.ERROR('Не удалось найти место для вставки DEBUG')
                )
                return
        
        # Если отключаем DEBUG, нужно также настроить CSRF_TRUSTED_ORIGINS
        if not new_debug:
            # Проверяем наличие CSRF_TRUSTED_ORIGINS
            csrf_match = re.search(r'^CSRF_TRUSTED_ORIGINS\s*=', new_content, re.MULTILINE)
            if not csrf_match:
                # Ищем ALLOWED_HOSTS для определения доменов
                allowed_hosts_match = re.search(r"^ALLOWED_HOSTS\s*=\s*\[(.*?)\]", new_content, re.MULTILINE | re.DOTALL)
                if allowed_hosts_match:
                    hosts_str = allowed_hosts_match.group(1)
                    # Извлекаем домены из ALLOWED_HOSTS
                    hosts = re.findall(r"['\"]([^'\"]+)['\"]", hosts_str)
                    # Формируем CSRF_TRUSTED_ORIGINS на основе ALLOWED_HOSTS
                    csrf_origins = []
                    for host in hosts:
                        if host not in ['localhost', '127.0.0.1']:
                            # Добавляем HTTPS версии для продакшена
                            csrf_origins.append(f"https://{host}")
                            if not host.startswith('www.'):
                                csrf_origins.append(f"https://www.{host}")
                    # Добавляем также HTTP для localhost
                    csrf_origins.extend(['http://localhost:8000', 'http://127.0.0.1:8000'])
                    
                    if csrf_origins:
                        csrf_line = f"CSRF_TRUSTED_ORIGINS = {csrf_origins}\n"
                        # Вставляем после ALLOWED_HOSTS
                        insert_pos = allowed_hosts_match.end()
                        new_content = (
                            new_content[:insert_pos] +
                            '\n' + csrf_line +
                            new_content[insert_pos:]
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f'CSRF_TRUSTED_ORIGINS настроен: {csrf_origins}')
                        )
        
        # Записываем обратно
        with open(settings_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        status = 'включен' if new_debug else 'отключен'
        self.stdout.write(
            self.style.SUCCESS(f'DEBUG режим {status}')
        )
        
        if new_debug:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  ВНИМАНИЕ: DEBUG режим включен. '
                    'Не используйте в продакшене!'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  ВАЖНО: После отключения DEBUG убедитесь, что:\n'
                    '  1. ALLOWED_HOSTS содержит ваш домен\n'
                    '  2. CSRF_TRUSTED_ORIGINS настроен для вашего домена\n'
                    '  3. SECURE_PROXY_SSL_HEADER настроен, если используете HTTPS через Nginx\n'
                    '  4. Перезапустите сервис Django Admin'
                )
            )

