import asyncio
from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async
from bot.models import Group, Participant, Draw
from django.conf import settings
from telegram import Bot


class Command(BaseCommand):
    help = 'Закрывает все группы и уведомляет участников'

    def handle(self, *args, **options):
        self.stdout.write('🔒 Начинаю закрытие всех групп...')
        
        # Получаем все незакрытые группы
        groups = Group.objects.filter(status__in=['active', 'drawn', 'distribution'])
        
        if not groups.exists():
            self.stdout.write(self.style.SUCCESS('✅ Все группы уже закрыты.'))
            return
        
        self.stdout.write(f'Найдено групп для закрытия: {groups.count()}')
        
        # Запускаем асинхронную функцию
        asyncio.run(self.close_groups_async(groups))
        
        self.stdout.write(self.style.SUCCESS('✅ Все группы закрыты и участники уведомлены.'))

    async def close_groups_async(self, groups):
        """Асинхронное закрытие групп и уведомление участников"""
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            self.stdout.write(self.style.ERROR('❌ Токен бота не настроен!'))
            return
        
        bot = Bot(token=token)
        
        groups_list = await sync_to_async(list)(groups)
        
        for group in groups_list:
            # Получаем всех участников группы
            participants = await sync_to_async(list)(
                Participant.objects.filter(group=group).select_related('user')
            )
            
            # Закрываем группу
            group.status = 'closed'
            group.is_closed = True
            await sync_to_async(group.save)()
            
            self.stdout.write(f'Закрыта группа: {group.name} ({group.code})')
            
            # Уведомляем всех участников
            for participant in participants:
                try:
                    message_text = (
                        f"🔒 Группа '{group.name}' закрыта.\n\n"
                        f"Спасибо за участие в Тайном Санте! 🎄\n"
                        f"До встречи в следующем году! 🎅"
                    )
                    await bot.send_message(
                        chat_id=participant.user.telegram_id,
                        text=message_text
                    )
                    self.stdout.write(f'  ✓ Уведомлен: {participant.user.telegram_id}')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ✗ Ошибка уведомления {participant.user.telegram_id}: {e}')
                    )

