import random
from asgiref.sync import sync_to_async
from django.utils import timezone
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from .models import TelegramUser, Group, Participant, Draw


# Состояния для ConversationHandler
WAITING_FOR_GROUP_NAME, WAITING_FOR_DESCRIPTION, WAITING_FOR_GIFT_VIA_BOT, WAITING_FOR_DRAW_DATE, WAITING_FOR_DISTRIBUTION_DATE, WAITING_FOR_CLOSE_DATE, WAITING_FOR_NAME, WAITING_FOR_CODE, WAITING_FOR_GIFT, WAITING_FOR_GROUP_SELECTION, WAITING_FOR_GROUP_SELECTION_FOR_NAME, WAITING_FOR_GIFT_PHOTO, WAITING_FOR_CLOSE_MESSAGE, WAITING_FOR_DELETE_GROUP_SELECTION = range(14)


def get_command_hints(*commands):
    """Генерирует подсказки с командами"""
    if not commands:
        return ""
    hints = "\n\n💡 Полезные команды:\n"
    for cmd in commands:
        hints += f"• {cmd}\n"
    return hints


def get_all_commands_list():
    """Возвращает полный список всех команд"""
    return (
        "📋 Все доступные команды:\n\n"
        "🔹 Основные:\n"
        "/start - Начать работу с ботом\n"
        "/help - Подробная инструкция\n"
        "/my_groups - Показать мои группы\n\n"
        "🔹 Группы:\n"
        "/create_group - Создать новую группу\n"
        "/join_group - Вступить в группу по коду\n"
        "/invite - Получить пригласительное сообщение\n"
        "/leave_group - Выйти из группы\n"
        "/delete_group - Удалить закрытую группу\n\n"
        "🔹 Участие:\n"
        "/set_name - Установить имя в группе\n"
        "/send_gift - Отправить подарок боту\n"
        "/view_gifts - Просмотреть полученные подарки\n\n"
        "🔹 Для владельцев:\n"
        "/draw - Провести розыгрыш\n"
        "/distribute_gifts - Распределить подарки\n"
        "/close_group - Принудительно закрыть группу"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    telegram_user, created = await sync_to_async(TelegramUser.objects.get_or_create)(
        telegram_id=user.id,
        defaults={
            'username': user.username,
            'first_name': user.first_name
        }
    )
    
    if not created:
        # Обновляем данные пользователя
        telegram_user.username = user.username
        telegram_user.first_name = user.first_name
        await sync_to_async(telegram_user.save)()
    
    welcome_text = (
        "🎄 Добро пожаловать в бота Тайный Санта! 🎄\n\n"
        "Этот бот поможет вам организовать игру Тайный Санта с друзьями!\n\n"
    )
    welcome_text += get_all_commands_list()
    welcome_text += "\n\n💡 Для начала работы используйте /create_group или /join_group"
    
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📖 Помощь по использованию бота:\n\n"
        "/create_group - Создать новую группу для розыгрыша\n"
        "/join_group - Вступить в группу по коду\n"
        "/invite - Получить пригласительное сообщение для пересылки\n"
        "/leave_group - Выйти из группы\n"
        "/my_groups - Показать все ваши группы\n"
        "/set_name - Установить ваше имя в группе\n"
        "/draw - Провести розыгрыш (только для владельца группы)\n"
        "/send_gift - Отправить подарок боту (если включены подарки через бота)\n"
        "/distribute_gifts - Распределить подарки (только для владельца группы)\n"
        "/view_gifts - Просмотреть полученные подарки из групп, где уже прошла расдача\n"
        "/close_group - Принудительно закрыть группу (только для владельца группы)\n"
        "/delete_group - Удалить закрытую группу из списка\n"
        "/help - Показать эту справку\n\n"
        "Как это работает:\n"
        "1. Создайте группу командой /create_group\n"
        "   - Укажите название, описание подарка\n"
        "   - Выберите, будут ли подарки через бота\n"
        "   - Укажите даты жеребьевки, расдачи и закрытия\n"
        "2. Получите пригласительное сообщение командой /invite\n"
        "   - Перешлите его друзьям из вашего списка контактов\n"
        "   - Они могут переслать его боту для автоматического вступления\n"
        "   - Или используйте /join_group с кодом группы\n"
        "3. Каждый участник указывает своё имя командой /set_name\n"
        "4. Владелец группы проводит розыгрыш командой /draw\n"
        "5. Если подарки через бота - участники отправляют подарки командой /send_gift\n"
        "6. Владелец распределяет подарки командой /distribute_gifts\n"
        "7. Группа автоматически закрывается на следующий день после расдачи"
    )
    await update.message.reply_text(help_text)


async def create_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания группы"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        telegram_user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user.id,
            defaults={
                'username': user.username,
                'first_name': user.first_name
            }
        )
    
    # Проверяем, есть ли у пользователя активная группа (не закрытая)
    active_group = await sync_to_async(Group.objects.filter(owner=telegram_user, status__in=['active', 'drawn', 'distribution']).first)()
    if active_group:
        status_display = dict(Group.STATUS_CHOICES).get(active_group.status, active_group.status)
        hints = get_command_hints("/my_groups", "/close_group", "/help")
        await update.message.reply_text(
            f"❌ У вас уже есть группа со статусом '{status_display}': {active_group.name} ({active_group.code})\n"
            "Вы можете создать новую группу только после закрытия текущей." + hints
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "📝 Создание новой группы\n\n"
        "Введите название группы:"
    )
    return WAITING_FOR_GROUP_NAME


async def create_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка названия группы"""
    group_name = update.message.text.strip()
    if len(group_name) > 200:
        await update.message.reply_text("❌ Название слишком длинное (максимум 200 символов). Попробуйте снова:")
        return WAITING_FOR_GROUP_NAME
    
    context.user_data['group_name'] = group_name
    await update.message.reply_text(
        "📝 Теперь введите описание подарка:\n"
        "(ориентировочная сумма, характер подарка и т.д.)"
    )
    return WAITING_FOR_DESCRIPTION


async def create_group_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка описания подарка"""
    description = update.message.text.strip()
    context.user_data['description'] = description
    
    await update.message.reply_text(
        "🤖 Подарки будут отправляться через бота?\n\n"
        "Ответьте: да или нет"
    )
    return WAITING_FOR_GIFT_VIA_BOT


async def create_group_gift_via_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка вопроса о подарках через бота"""
    answer = update.message.text.strip().lower()
    
    if answer in ['да', 'yes', 'y', 'д']:
        gift_via_bot = True
    elif answer in ['нет', 'no', 'n', 'н']:
        gift_via_bot = False
    else:
        await update.message.reply_text("❌ Пожалуйста, ответьте 'да' или 'нет':")
        return WAITING_FOR_GIFT_VIA_BOT
    
    context.user_data['gift_via_bot'] = gift_via_bot
    
    await update.message.reply_text(
        "📅 Введите дату проведения жеребьевки (формат: ДД.ММ.ГГГГ, например: 25.12.2024):"
    )
    return WAITING_FOR_DRAW_DATE


async def create_group_draw_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка даты жеребьевки"""
    from datetime import datetime
    
    date_str = update.message.text.strip()
    try:
        draw_date = datetime.strptime(date_str, '%d.%m.%Y').date()
        context.user_data['draw_date'] = draw_date
        
        await update.message.reply_text(
            "📅 Введите дату расдачи подарков (формат: ДД.ММ.ГГГГ, например: 31.12.2024):"
        )
        return WAITING_FOR_DISTRIBUTION_DATE
    except ValueError:
        await update.message.reply_text("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ (например: 25.12.2024):")
        return WAITING_FOR_DRAW_DATE


async def create_group_distribution_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка даты расдачи подарков"""
    from datetime import datetime
    
    date_str = update.message.text.strip()
    try:
        distribution_date = datetime.strptime(date_str, '%d.%m.%Y').date()
        draw_date = context.user_data.get('draw_date')
        
        if distribution_date <= draw_date:
            await update.message.reply_text("❌ Дата расдачи должна быть позже даты жеребьевки. Попробуйте снова:")
            return WAITING_FOR_DISTRIBUTION_DATE
        
        context.user_data['gift_distribution_date'] = distribution_date
        
        await update.message.reply_text(
            "📅 Введите дату закрытия группы (формат: ДД.ММ.ГГГГ) или отправьте 'пропустить' для автоматической установки (на следующий день после расдачи):"
        )
        return WAITING_FOR_CLOSE_DATE
    except ValueError:
        await update.message.reply_text("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ (например: 31.12.2024):")
        return WAITING_FOR_DISTRIBUTION_DATE


async def create_group_close_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка даты закрытия группы и создание группы"""
    from datetime import datetime, timedelta
    
    date_str = update.message.text.strip().lower()
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        telegram_user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user.id,
            defaults={
                'username': user.username,
                'first_name': user.first_name
            }
        )
    
    close_date = None
    if date_str not in ['пропустить', 'skip', 'пропустить', '']:
        try:
            close_date = datetime.strptime(date_str, '%d.%m.%Y').date()
            distribution_date = context.user_data.get('gift_distribution_date')
            if close_date <= distribution_date:
                await update.message.reply_text("❌ Дата закрытия должна быть позже даты расдачи. Попробуйте снова:")
                return WAITING_FOR_CLOSE_DATE
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ или отправьте 'пропустить':")
            return WAITING_FOR_CLOSE_DATE
    
    # Создаем группу
    group = await sync_to_async(Group.objects.create)(
        name=context.user_data['group_name'],
        code=await sync_to_async(Group.generate_code)(),
        owner=telegram_user,
        description=context.user_data['description'],
        gift_via_bot=context.user_data['gift_via_bot'],
        draw_date=context.user_data['draw_date'],
        gift_distribution_date=context.user_data['gift_distribution_date'],
        close_date=close_date,
        status='active'
    )
    
    # Владелец автоматически становится участником
    default_name = telegram_user.first_name or telegram_user.username or f"Участник {telegram_user.telegram_id}"
    await sync_to_async(Participant.objects.create)(
        group=group,
        user=telegram_user,
        name=default_name
    )
    
    gift_text = "✅ Да, подарки будут отправляться через бота" if context.user_data['gift_via_bot'] else "❌ Нет, подарки не через бота"
    
    hints = get_command_hints("/invite", "/set_name", "/my_groups", "/help")
    await update.message.reply_text(
        f"✅ Группа '{group.name}' успешно создана!\n\n"
        f"🔑 Код группы: <code>{group.code}</code>\n\n"
        f"📝 Описание подарка:\n{context.user_data['description']}\n\n"
        f"🤖 {gift_text}\n"
        f"📅 Дата жеребьевки: {group.draw_date.strftime('%d.%m.%Y') if group.draw_date else 'Не указана'}\n"
        f"📅 Дата расдачи: {group.gift_distribution_date.strftime('%d.%m.%Y') if group.gift_distribution_date else 'Не указана'}\n"
        f"📅 Дата закрытия: {group.close_date.strftime('%d.%m.%Y') if group.close_date else 'Автоматически'}\n\n"
        f"Поделитесь этим кодом с друзьями, чтобы они могли вступить в группу.\n"
        f"Вы автоматически добавлены в группу как участник.\n\n"
        f"Используйте /set_name чтобы изменить ваше имя в группе.\n\n"
        f"Используйте /invite для получения пригласительного сообщения." + hints,
        parse_mode='HTML'
    )
    
    # Отправляем пригласительное сообщение
    invite_message = generate_invite_message(group)
    await update.message.reply_text(
        invite_message,
        parse_mode='HTML'
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def create_group_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания группы"""
    context.user_data.clear()
    await update.message.reply_text("❌ Создание группы отменено.")
    return ConversationHandler.END


async def join_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало вступления в группу"""
    await update.message.reply_text(
        "🔑 Введите код группы для вступления:"
    )
    return WAITING_FOR_CODE


async def join_group_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кода группы"""
    code = update.message.text.strip().upper()
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        # Создаем пользователя, если его нет
        telegram_user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user.id,
            defaults={
                'username': user.username,
                'first_name': user.first_name
            }
        )
    
    try:
        group = await sync_to_async(Group.objects.get)(code=code)
    except Group.DoesNotExist:
        hints = get_command_hints("/my_groups", "/create_group", "/help")
        await update.message.reply_text("❌ Группа с таким кодом не найдена. Проверьте код и попробуйте снова." + hints)
        return ConversationHandler.END
    
    if not await sync_to_async(group.can_add_participants)():
        status_display = await sync_to_async(lambda: group.get_status_display())()
        hints = get_command_hints("/my_groups", "/create_group", "/help")
        await update.message.reply_text(f"❌ Эта группа уже не принимает участников. Статус: {status_display}" + hints)
        return ConversationHandler.END
    
    # Проверяем, не является ли пользователь уже участником
    is_participant = await sync_to_async(Participant.objects.filter(group=group, user=telegram_user).exists)()
    if is_participant:
        hints = get_command_hints("/my_groups", "/set_name", "/help")
        await update.message.reply_text("❌ Вы уже являетесь участником этой группы." + hints)
        return ConversationHandler.END
    
    # Добавляем участника
    default_name = telegram_user.first_name or telegram_user.username or f"Участник {telegram_user.telegram_id}"
    await sync_to_async(Participant.objects.create)(
        group=group,
        user=telegram_user,
        name=default_name
    )
    
    hints = get_command_hints("/set_name", "/my_groups", "/help")
    await update.message.reply_text(
        f"✅ Вы успешно вступили в группу '{group.name}'!\n\n"
        f"📝 Описание подарка:\n{group.description}\n\n"
        f"Ваше имя в группе: {default_name}\n"
        f"Используйте /set_name чтобы изменить ваше имя." + hints
    )
    
    return ConversationHandler.END


async def join_group_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена вступления в группу"""
    await update.message.reply_text("❌ Вступление в группу отменено.")
    return ConversationHandler.END


async def leave_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из группы"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return
    
    # Получаем все группы пользователя с предзагрузкой связанных объектов
    participations = await sync_to_async(list)(Participant.objects.filter(user=telegram_user, group__is_closed=False).select_related('group', 'group__owner'))
    
    if not participations:
        await update.message.reply_text("❌ Вы не состоите ни в одной активной группе.")
        return
    
    if len(participations) == 1:
        # Если только одна группа, выходим сразу
        participation = participations[0]
        group = participation.group
        
        # Нельзя выйти, если ты владелец
        if group.owner_id == telegram_user.id:
            hints = get_command_hints("/draw", "/close_group", "/my_groups", "/help")
            await update.message.reply_text("❌ Вы не можете выйти из группы, которой владеете. Сначала проведите розыгрыш." + hints)
            return
        
        await sync_to_async(participation.delete)()
        hints = get_command_hints("/my_groups", "/join_group", "/help")
        await update.message.reply_text(f"✅ Вы вышли из группы '{group.name}'." + hints)
        return
    
    # Если несколько групп, показываем список
    groups_list = "\n".join([f"{i+1}. {p.group.name} ({p.group.code})" for i, p in enumerate(participations)])
    await update.message.reply_text(
        f"📋 Вы состоите в нескольких группах:\n\n{groups_list}\n\n"
        "Введите номер группы, из которой хотите выйти:"
    )
    # Здесь можно добавить более сложную логику выбора группы
    await update.message.reply_text("⚠️ Для выхода из конкретной группы используйте код группы в формате: /leave_group КОД")


async def my_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать группы пользователя"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return
    
    # Группы, где пользователь владелец
    owned_groups = await sync_to_async(list)(Group.objects.filter(owner=telegram_user))
    
    # Группы, где пользователь участник
    participations = await sync_to_async(list)(Participant.objects.filter(user=telegram_user).select_related('group', 'group__owner'))
    participant_groups = []
    for p in participations:
        if p.group.owner_id != telegram_user.id:
            participant_groups.append(p.group)
    
    if not owned_groups and not participant_groups:
        hints = get_command_hints("/create_group", "/join_group", "/invite", "/help")
        await update.message.reply_text("❌ Вы не состоите ни в одной группе." + hints)
        return
    
    message = "📋 Ваши группы:\n\n"
    
    status_map = {
        'active': '✅ Активна',
        'drawn': '🎲 Жеребьевка проведена',
        'distribution': '🎁 Расдача подарков',
        'closed': '🔒 Закрыта'
    }
    
    if owned_groups:
        message += "👑 Группы, которыми вы владеете:\n"
        for group in owned_groups:
            status = status_map.get(group.status, group.status)
            participants_count = await sync_to_async(group.participants.count)()
            message += f"• {group.name} ({group.code}) - {status}\n"
            message += f"  Участников: {participants_count}\n"
            if group.status == 'active':
                message += f"  Используйте /draw для розыгрыша\n"
            elif group.status == 'drawn':
                message += f"  Используйте /distribute_gifts для расдачи подарков\n"
        message += "\n"
    
    if participant_groups:
        message += "👥 Группы, в которых вы участвуете:\n"
        for group in participant_groups:
            status = status_map.get(group.status, group.status)
            participation = await sync_to_async(Participant.objects.get)(group=group, user=telegram_user)
            message += f"• {group.name} ({group.code}) - {status}\n"
            message += f"  Ваше имя: {participation.name}\n"
            
            # Для групп со статусом "жеребьевка проведена" показываем получателя
            if group.status == 'drawn':
                try:
                    draw = await sync_to_async(Draw.objects.select_related('receiver').get)(
                        group=group,
                        giver=participation
                    )
                    message += f"  🎁 Вы дарите подарок: {draw.receiver.name}\n"
                except Draw.DoesNotExist:
                    pass
            
            # Информация о подарке через бота
            if group.status == 'drawn' and group.gift_via_bot:
                if participation.gift_sent:
                    gift_info = "  ✅ Подарок отправлен боту\n"
                    if participation.gift_photo_file_id:
                        gift_info += "  📷 Подарок содержит фото\n"
                    if participation.gift_message:
                        gift_preview = participation.gift_message[:50] + "..." if len(participation.gift_message) > 50 else participation.gift_message
                        gift_info += f"  📝 Текст: {gift_preview}\n"
                    gift_info += "  ✏️ Используйте /send_gift для изменения подарка\n"
                    message += gift_info
                else:
                    message += f"  📝 Используйте /send_gift для отправки подарка\n"
        message += "\n"
    
    await update.message.reply_text(message)


async def set_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало установки имени"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return ConversationHandler.END
    
    # Получаем только активные группы (до жеребьевки) пользователя
    participations = await sync_to_async(list)(
        Participant.objects.filter(
            user=telegram_user,
            group__status='active'
        ).select_related('group')
    )
    
    if not participations:
        hints = get_command_hints("/join_group", "/my_groups", "/help")
        await update.message.reply_text(
            "❌ Вы не состоите ни в одной активной группе (где еще не проведена жеребьевка).\n\n"
            "Имя можно установить только до проведения жеребьевки." + hints
        )
        return ConversationHandler.END
    
    if len(participations) == 1:
        # Если одна группа, сразу запрашиваем имя
        participation = participations[0]
        context.user_data['participation_id'] = participation.id
        current_name = participation.name
        await update.message.reply_text(
            f"📝 Введите ваше имя для группы '{participation.group.name}':\n\n"
            f"Текущее имя: {current_name}"
        )
        return WAITING_FOR_NAME
    
    # Если несколько групп - сохраняем список и запрашиваем выбор
    context.user_data['participations'] = [(p.id, p.group.name, p.name) for p in participations]
    groups_list = "\n".join([f"{i+1}. {p.group.name} (текущее имя: {p.name})" for i, p in enumerate(participations)])
    await update.message.reply_text(
        f"📋 Вы состоите в нескольких активных группах:\n\n{groups_list}\n\n"
        "Введите номер группы (1, 2, 3...), для которой хотите установить имя:"
    )
    return WAITING_FOR_GROUP_SELECTION_FOR_NAME


async def set_name_select_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора группы для установки имени"""
    try:
        group_number = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите номер группы (число):")
        return WAITING_FOR_GROUP_SELECTION_FOR_NAME
    
    participations_data = context.user_data.get('participations', [])
    
    if not participations_data:
        await update.message.reply_text("❌ Ошибка. Попробуйте снова использовать /set_name")
        context.user_data.clear()
        return ConversationHandler.END
    
    if group_number < 1 or group_number > len(participations_data):
        await update.message.reply_text(
            f"❌ Неверный номер. Введите число от 1 до {len(participations_data)}:"
        )
        return WAITING_FOR_GROUP_SELECTION_FOR_NAME
    
    # Получаем выбранную participation
    participation_id, group_name, current_name = participations_data[group_number - 1]
    context.user_data['participation_id'] = participation_id
    context.user_data.pop('participations', None)  # Удаляем список, больше не нужен
    
    await update.message.reply_text(
        f"📝 Введите ваше имя для группы '{group_name}':\n\n"
        f"Текущее имя: {current_name}"
    )
    return WAITING_FOR_NAME


async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка имени участника"""
    name = update.message.text.strip()
    
    if len(name) > 200:
        await update.message.reply_text("❌ Имя слишком длинное (максимум 200 символов). Попробуйте снова:")
        return WAITING_FOR_NAME
    
    participation_id = context.user_data.get('participation_id')
    if participation_id:
        participation = await sync_to_async(Participant.objects.select_related('group').get)(id=participation_id)
        participation.name = name
        await sync_to_async(participation.save)()
        
        hints = get_command_hints("/my_groups", "/draw", "/help")
        await update.message.reply_text(
            f"✅ Ваше имя в группе '{participation.group.name}' установлено: {name}" + hints
        )
    else:
        await update.message.reply_text("❌ Ошибка. Попробуйте снова.")
    
    context.user_data.clear()
    return ConversationHandler.END


async def set_name_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена установки имени"""
    context.user_data.clear()
    await update.message.reply_text("❌ Установка имени отменена.")
    return ConversationHandler.END


async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проведение розыгрыша"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return
    
    # Находим активную группу пользователя
    group = await sync_to_async(Group.objects.filter(owner=telegram_user, status='active').first)()
    
    if not group:
        hints = get_command_hints("/create_group", "/my_groups", "/help")
        await update.message.reply_text(
            "❌ У вас нет активной группы. Создайте группу командой /create_group" + hints
        )
        return
    
    can_draw = await sync_to_async(group.can_draw)()
    if not can_draw:
        participants_count = await sync_to_async(group.participants.count)()
        hints = get_command_hints("/invite", "/my_groups", "/help")
        await update.message.reply_text(
            "❌ Для розыгрыша необходимо минимум 2 участника. "
            f"Сейчас участников: {participants_count}" + hints
        )
        return
    
    # Получаем всех участников
    participants = await sync_to_async(list)(group.participants.select_related('user').all())
    
    # Проводим розыгрыш
    # Перемешиваем список получателей
    receivers = participants.copy()
    random.shuffle(receivers)
    
    # Проверяем, чтобы никто не дарил сам себе
    max_attempts = 100
    attempt = 0
    while attempt < max_attempts:
        valid = True
        for i, giver in enumerate(participants):
            if giver == receivers[i]:
                valid = False
                break
        
        if valid:
            break
        
        random.shuffle(receivers)
        attempt += 1
    
    # Создаем записи о розыгрыше
    draws_created = []
    for giver, receiver in zip(participants, receivers):
        draw_obj = await sync_to_async(Draw.objects.create)(
            group=group,
            giver=giver,
            receiver=receiver
        )
        draws_created.append(draw_obj)
    
    # Загружаем связанные объекты для рассылки
    draws_created = await sync_to_async(list)(Draw.objects.filter(group=group).select_related('giver__user', 'receiver'))
    
    # Устанавливаем статус "жеребьевка проведена"
    group.status = 'drawn'
    group.drawn_at = timezone.now()
    await sync_to_async(group.save)()
    
    # Рассылаем результаты участникам
    gift_via_bot_text = ""
    if group.gift_via_bot:
        gift_via_bot_text = "\n\n🎁 Вы можете отправить подарок боту командой /send_gift, и он сохранит его на виртуальной ёлочке до дня расдачи!"
    
    for draw_obj in draws_created:
        try:
            receiver_name = draw_obj.receiver.name
            giver_telegram_id = draw_obj.giver.user.telegram_id
            
            message_text = (
                f"🎄 Розыгрыш в группе '{group.name}' проведен!\n\n"
                f"🎁 Вы дарите подарок: <b>{receiver_name}</b>\n\n"
                f"📝 Описание подарка:\n{group.description}\n"
            )
            if group.gift_distribution_date:
                message_text += f"📅 Дата расдачи: {group.gift_distribution_date.strftime('%d.%m.%Y')}\n"
            message_text += f"{gift_via_bot_text}\n\nУдачи в выборе подарка! 🎅"
            await context.bot.send_message(
                chat_id=giver_telegram_id,
                text=message_text,
                parse_mode='HTML'
            )
        except Exception as e:
            # Логируем ошибку, но продолжаем рассылку
            giver_telegram_id = draw_obj.giver.user.telegram_id if hasattr(draw_obj, 'giver') else 'unknown'
            print(f"Ошибка отправки сообщения пользователю {giver_telegram_id}: {e}")
    
    distribution_date_text = ""
    if group.gift_distribution_date:
        distribution_date_text = f"\n📅 Дата расдачи подарков: {group.gift_distribution_date.strftime('%d.%m.%Y')}"
    
    hints = get_command_hints("/distribute_gifts", "/my_groups", "/send_gift", "/help")
    await update.message.reply_text(
        f"✅ Розыгрыш в группе '{group.name}' успешно проведен!\n\n"
        f"📨 Все участники получили уведомления о своих получателях.{distribution_date_text}\n\n"
        f"Статус группы изменен на 'Жеребьевка проведена'." + hints
    )


async def send_gift_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало отправки подарка боту"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return ConversationHandler.END
    
    # Получаем группы, где пользователь участник и статус "жеребьевка проведена" или "расдача подарков" и gift_via_bot=True
    # Позволяем изменять подарок до момента расдачи
    participations = await sync_to_async(list)(
        Participant.objects.filter(
            user=telegram_user,
            group__status__in=['drawn', 'distribution'],
            group__gift_via_bot=True
        ).select_related('group')
    )
    
    if not participations:
        hints = get_command_hints("/my_groups", "/draw", "/help")
        await update.message.reply_text(
            "❌ У вас нет групп со статусом 'Жеребьевка проведена' или 'Расдача подарков', где подарки отправляются через бота." + hints
        )
        return ConversationHandler.END
    
    # Фильтруем только группы, где еще можно изменить подарок (до расдачи)
    participations = [p for p in participations if p.group.status == 'drawn']
    
    if not participations:
        await update.message.reply_text(
            "❌ В ваших группах уже началась расдача подарков. Изменить подарок нельзя."
        )
        return ConversationHandler.END
    
    if len(participations) == 1:
        participation = participations[0]
        context.user_data['participation_id'] = participation.id
        
        # Проверяем, есть ли уже подарок
        if participation.gift_sent:
            gift_info = ""
            if participation.gift_photo_file_id:
                gift_info += "📷 Подарок содержит фото\n"
            if participation.gift_message:
                gift_info += f"📝 Текст: {participation.gift_message[:50]}...\n"
            await update.message.reply_text(
                f"✅ Вы уже отправили подарок для группы '{participation.group.name}'.\n\n"
                f"{gift_info}\n"
                f"Хотите изменить подарок?\n\n"
                f"Отправьте:\n"
                f"• Текст подарка\n"
                f"• Фото (с подписью или без)\n"
                f"• Или фото с подписью одновременно"
            )
        else:
            await update.message.reply_text(
                f"🎁 Отправка подарка для группы '{participation.group.name}'\n\n"
                f"Отправьте ваш подарок:\n"
                f"• Текст подарка\n"
                f"• Фото (с подписью или без)\n"
                f"• Или фото с подписью одновременно"
            )
        return WAITING_FOR_GIFT
    
    # Если несколько групп - сохраняем список и запрашиваем выбор
    context.user_data['participations'] = [(p.id, p.group.name) for p in participations]
    groups_list = "\n".join([f"{i+1}. {p.group.name}" for i, p in enumerate(participations)])
    await update.message.reply_text(
        f"📋 Вы участвуете в нескольких группах:\n\n{groups_list}\n\n"
        "Введите номер группы (1, 2, 3...), для которой хотите отправить подарок:"
    )
    return WAITING_FOR_GROUP_SELECTION


async def send_gift_select_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора группы для отправки подарка"""
    try:
        group_number = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите номер группы (число):")
        return WAITING_FOR_GROUP_SELECTION
    
    participations_data = context.user_data.get('participations', [])
    
    if not participations_data:
        await update.message.reply_text("❌ Ошибка. Попробуйте снова использовать /send_gift")
        context.user_data.clear()
        return ConversationHandler.END
    
    if group_number < 1 or group_number > len(participations_data):
        await update.message.reply_text(
            f"❌ Неверный номер. Введите число от 1 до {len(participations_data)}:"
        )
        return WAITING_FOR_GROUP_SELECTION
    
    # Получаем выбранную participation
    participation_id, group_name = participations_data[group_number - 1]
    context.user_data['participation_id'] = participation_id
    context.user_data.pop('participations', None)  # Удаляем список, больше не нужен
    
    # Получаем participation для проверки подарка
    participation = await sync_to_async(Participant.objects.select_related('group').get)(id=participation_id)
    
    # Проверяем, есть ли уже подарок
    if participation.gift_sent:
        gift_info = ""
        if participation.gift_photo_file_id:
            gift_info += "📷 Подарок содержит фото\n"
        if participation.gift_message:
            gift_info += f"📝 Текст: {participation.gift_message[:50]}...\n"
        await update.message.reply_text(
            f"✅ Вы уже отправили подарок для группы '{group_name}'.\n\n"
            f"{gift_info}\n"
            f"Хотите изменить подарок?\n\n"
            f"Отправьте:\n"
            f"• Текст подарка\n"
            f"• Фото (с подписью или без)\n"
            f"• Или фото с подписью одновременно"
        )
    else:
        await update.message.reply_text(
            f"🎁 Отправка подарка для группы '{group_name}'\n\n"
            f"Отправьте ваш подарок:\n"
            f"• Текст подарка\n"
            f"• Фото (с подписью или без)\n"
            f"• Или фото с подписью одновременно"
        )
    return WAITING_FOR_GIFT


async def send_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка отправки подарка"""
    participation_id = context.user_data.get('participation_id')
    if not participation_id:
        await update.message.reply_text("❌ Ошибка. Попробуйте снова.")
        context.user_data.clear()
        return ConversationHandler.END
    
    participation = await sync_to_async(Participant.objects.select_related('group').get)(id=participation_id)
    
    # Проверяем, что пришло: фото, текст или фото с подписью
    photo = update.message.photo
    text = update.message.text
    caption = update.message.caption
    
    # Если есть фото
    if photo:
        # Берем фото наибольшего размера (последнее в списке)
        photo_file_id = photo[-1].file_id
        participation.gift_photo_file_id = photo_file_id
        
        # Если есть подпись к фото, используем её как текст подарка
        if caption:
            if len(caption) > 2000:
                await update.message.reply_text("❌ Подпись к фото слишком длинная (максимум 2000 символов). Попробуйте снова:")
                return WAITING_FOR_GIFT
            participation.gift_message = caption.strip()
        # Если фото без подписи, но есть сохраненный текст - оставляем его
        elif not participation.gift_message:
            participation.gift_message = None
    
    # Если только текст (без фото)
    elif text:
        gift_message = text.strip()
        if len(gift_message) > 2000:
            await update.message.reply_text("❌ Подарок слишком длинный (максимум 2000 символов). Попробуйте снова:")
            return WAITING_FOR_GIFT
        participation.gift_message = gift_message
        # Если был фото, но теперь только текст - удаляем фото
        if participation.gift_photo_file_id:
            participation.gift_photo_file_id = None
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте текст или фото подарка.")
        return WAITING_FOR_GIFT
    
    # Проверяем, что есть хотя бы текст или фото
    if not participation.gift_message and not participation.gift_photo_file_id:
        await update.message.reply_text("❌ Подарок должен содержать текст или фото.")
        return WAITING_FOR_GIFT
    
    participation.gift_sent = True
    await sync_to_async(participation.save)()
    
    distribution_date_text = participation.group.gift_distribution_date.strftime('%d.%m.%Y') if participation.group.gift_distribution_date else "в день расдачи"
    
    gift_summary = ""
    if participation.gift_photo_file_id:
        gift_summary += "📷 Фото"
    if participation.gift_message:
        if gift_summary:
            gift_summary += " и "
        gift_summary += "📝 текст"
    
    hints = get_command_hints("/my_groups", "/view_gifts", "/help")
    await update.message.reply_text(
        f"✅ Ваш подарок для группы '{participation.group.name}' сохранен на виртуальной ёлочке! 🎄\n\n"
        f"Подарок содержит: {gift_summary}\n"
        f"Подарок будет доставлен получателю {distribution_date_text}." + hints
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def send_gift_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена отправки подарка"""
    context.user_data.clear()
    await update.message.reply_text("❌ Отправка подарка отменена.")
    return ConversationHandler.END


def generate_invite_message(group: Group) -> str:
    """Генерирует пригласительное сообщение для группы"""
    return (
        f"🎄 Приглашение в группу Тайного Санты!\n\n"
        f"📋 Группа: <b>{group.name}</b>\n"
        f"🔑 Код: <code>{group.code}</code>\n\n"
        f"📝 Описание подарка:\n{group.description}\n\n"
        f"📅 Дата жеребьевки: {group.draw_date.strftime('%d.%m.%Y') if group.draw_date else 'Не указана'}\n"
        f"📅 Дата расдачи: {group.gift_distribution_date.strftime('%d.%m.%Y') if group.gift_distribution_date else 'Не указана'}\n\n"
        f"➡️ Перешлите это сообщение боту, чтобы автоматически присоединиться к группе!\n\n"
        f"🔑 <code>SANTA_INVITE:{group.code}</code>"
    )


async def get_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить пригласительное сообщение для группы"""
    if not update.message:
        return
    
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return
    except Exception as e:
        print(f"Ошибка при получении пользователя в get_invite: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
        return
    
    try:
        # Получаем активные группы пользователя (где он владелец или участник)
        owned_groups = await sync_to_async(list)(
            Group.objects.filter(owner=telegram_user, status='active')
        )
        participations = await sync_to_async(list)(
            Participant.objects.filter(
                user=telegram_user,
                group__status='active'
            ).select_related('group', 'group__owner')
        )
        # Используем owner_id вместо owner для избежания дополнительных запросов к БД
        participant_groups = [p.group for p in participations if p.group.owner_id != telegram_user.id]
        
        all_groups = owned_groups + participant_groups
        
        if not all_groups:
            hints = get_command_hints("/create_group", "/join_group", "/help")
            await update.message.reply_text(
                "❌ У вас нет активных групп. Создайте группу командой /create_group" + hints
            )
            return
        
        if len(all_groups) == 1:
            # Если одна группа, отправляем приглашение сразу
            group = all_groups[0]
            invite_message = generate_invite_message(group)
            await update.message.reply_text(invite_message, parse_mode='HTML')
            return
        
        # Если несколько групп, отправляем приглашения для всех
        for group in all_groups:
            invite_message = generate_invite_message(group)
            await update.message.reply_text(invite_message, parse_mode='HTML')
    except Exception as e:
        print(f"Ошибка в get_invite: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text("❌ Произошла ошибка при получении приглашения. Попробуйте позже.")


async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка непонятных сообщений"""
    if not update.message or not update.message.text:
        return
    
    # Игнорируем команды (они обрабатываются CommandHandler)
    if update.message.text.startswith('/'):
        return
    
    # Список основных команд
    commands_list = (
        "📋 Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/create_group - Создать новую группу\n"
        "/join_group - Вступить в группу по коду\n"
        "/invite - Получить пригласительное сообщение\n"
        "/my_groups - Показать мои группы\n"
        "/set_name - Установить имя в группе\n"
        "/leave_group - Выйти из группы\n"
        "/draw - Провести розыгрыш (для владельца)\n"
        "/send_gift - Отправить подарок боту\n"
        "/distribute_gifts - Распределить подарки (для владельца)\n"
        "/view_gifts - Просмотреть полученные подарки\n"
        "/close_group - Принудительно закрыть группу (для владельца)\n"
        "/delete_group - Удалить закрытую группу\n"
        "/help - Подробная инструкция\n\n"
        "💡 Для получения подробной информации используйте команду /help"
    )
    
    await update.message.reply_text(commands_list)


async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка пересланного пригласительного сообщения"""
    if not update.message:
        return
    
    user = update.effective_user
    message_text = update.message.text or update.message.caption or ""
    
    # Ищем маркер приглашения в тексте сообщения
    if "SANTA_INVITE:" not in message_text:
        return
    
    # Извлекаем код группы
    try:
        code_start = message_text.find("SANTA_INVITE:") + len("SANTA_INVITE:")
        code_end = message_text.find("\n", code_start)
        if code_end == -1:
            code_end = len(message_text)
        code = message_text[code_start:code_end].strip().upper()
    except Exception as e:
        print(f"Ошибка извлечения кода из приглашения: {e}")
        return
    
    # Получаем или создаем пользователя
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        telegram_user, _ = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=user.id,
            defaults={
                'username': user.username,
                'first_name': user.first_name
            }
        )
    
    # Находим группу по коду
    try:
        group = await sync_to_async(Group.objects.get)(code=code)
    except Group.DoesNotExist:
        await update.message.reply_text("❌ Группа с таким кодом не найдена.")
        return
    
    # Проверяем, можно ли добавить участников
    if not await sync_to_async(group.can_add_participants)():
        status_display = await sync_to_async(lambda: group.get_status_display())()
        await update.message.reply_text(
            f"❌ Группа '{group.name}' уже не принимает участников. Статус: {status_display}"
        )
        return
    
    # Проверяем, не является ли пользователь уже участником
    is_participant = await sync_to_async(
        Participant.objects.filter(group=group, user=telegram_user).exists
    )()
    if is_participant:
        await update.message.reply_text(f"✅ Вы уже являетесь участником группы '{group.name}'.")
        return
    
    # Добавляем участника
    default_name = telegram_user.first_name or telegram_user.username or f"Участник {telegram_user.telegram_id}"
    await sync_to_async(Participant.objects.create)(
        group=group,
        user=telegram_user,
        name=default_name
    )
    
    await update.message.reply_text(
        f"✅ Вы успешно присоединились к группе '{group.name}'!\n\n"
        f"📝 Описание подарка:\n{group.description}\n\n"
        f"Ваше имя в группе: {default_name}\n"
        f"Используйте /set_name чтобы изменить ваше имя."
    )


async def view_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр полученных подарков из групп, где уже расдали подарки"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return
    
    # Находим все розыгрыши, где пользователь является получателем, и группа имеет статус 'distribution' или 'closed'
    draws = await sync_to_async(list)(
        Draw.objects.filter(
            receiver__user=telegram_user,
            group__status__in=['distribution', 'closed']
        ).select_related(
            'group',
            'giver',
            'giver__user'
        ).order_by('-group__gift_distribution_date', '-group__created_at')
    )
    
    if not draws:
        hints = get_command_hints("/my_groups", "/distribute_gifts", "/help")
        await update.message.reply_text(
            "❌ У вас нет полученных подарков из групп, где уже прошла расдача подарков." + hints
        )
        return
    
    # Группируем подарки по группам
    gifts_by_group = {}
    for draw_obj in draws:
        group_id = draw_obj.group.id
        if group_id not in gifts_by_group:
            gifts_by_group[group_id] = {
                'group': draw_obj.group,
                'gifts': []
            }
        gifts_by_group[group_id]['gifts'].append(draw_obj)
    
    # Отправляем подарки по группам
    for group_id, group_data in gifts_by_group.items():
        group = group_data['group']
        draw_obj = group_data['gifts'][0]  # Берем первый подарок (в группе должен быть только один)
        
        # Формируем информацию о группе
        status_map = {
            'distribution': '🎁 Расдача подарков',
            'closed': '🔒 Закрыта'
        }
        status = status_map.get(group.status, group.status)
        
        group_info = (
            f"📦 Группа: <b>{group.name}</b>\n"
            f"Статус: {status}\n"
            f"Дата расдачи: {group.gift_distribution_date.strftime('%d.%m.%Y') if group.gift_distribution_date else 'Не указана'}\n\n"
        )
        
        # Отправляем информацию о группе
        await update.message.reply_text(group_info, parse_mode='HTML')
        
        # Отправляем подарок
        if group.gift_via_bot and (draw_obj.giver.gift_message or draw_obj.giver.gift_photo_file_id):
            # Если подарок через бота и есть подарок
            if draw_obj.giver.gift_photo_file_id:
                # Если есть фото, отправляем фото с подписью
                message_text = "🎁 Подарок от Тайного Санты! 🎄"
                if draw_obj.giver.gift_message:
                    message_text += f"\n\n🎁 Ваш подарок:\n{draw_obj.giver.gift_message}"
                message_text += "\n\nСчастливого праздника! 🎅"
                
                await context.bot.send_photo(
                    chat_id=user.id,
                    photo=draw_obj.giver.gift_photo_file_id,
                    caption=message_text,
                    parse_mode='HTML'
                )
            else:
                # Если только текст без фото
                message_text = (
                    f"🎁 Подарок от Тайного Санты! 🎄\n\n"
                    f"🎁 Ваш подарок:\n{draw_obj.giver.gift_message}\n\n"
                    f"Счастливого праздника! 🎅"
                )
                await context.bot.send_message(
                    chat_id=user.id,
                    text=message_text,
                    parse_mode='HTML'
                )
        else:
            # Если подарок не через бота или не отправлен
            message_text = (
                f"🎁 Подарок от Тайного Санты! 🎄\n\n"
                f"Подарок был в условленном месте! 🎅"
            )
            await context.bot.send_message(
                chat_id=user.id,
                text=message_text,
                parse_mode='HTML'
            )
    
    # Итоговое сообщение
    total_groups = len(gifts_by_group)
    hints = get_command_hints("/my_groups", "/help")
    await update.message.reply_text(
        f"✅ Показано подарков из {total_groups} групп." + hints
    )


async def close_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало принудительного закрытия группы"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return ConversationHandler.END
    
    # Находим группу, которой владеет пользователь (не закрытую)
    group = await sync_to_async(
        Group.objects.filter(
            owner=telegram_user,
            status__in=['active', 'drawn', 'distribution']
        ).first
    )()
    
    if not group:
        hints = get_command_hints("/my_groups", "/create_group", "/help")
        await update.message.reply_text(
            "❌ У вас нет активной группы для закрытия.\n\n"
            "Группа может быть закрыта только если она имеет статус:\n"
            "• Активна\n"
            "• Жеребьевка проведена\n"
            "• Расдача подарков" + hints
        )
        return ConversationHandler.END
    
    # Сохраняем ID группы в контексте
    context.user_data['close_group_id'] = group.id
    
    status_map = {
        'active': '✅ Активна',
        'drawn': '🎲 Жеребьевка проведена',
        'distribution': '🎁 Расдача подарков'
    }
    status = status_map.get(group.status, group.status)
    
    await update.message.reply_text(
        f"🔒 Принудительное закрытие группы\n\n"
        f"Группа: <b>{group.name}</b>\n"
        f"Статус: {status}\n\n"
        f"Введите сообщение, которое будет отправлено всем участникам группы при закрытии:\n\n"
        f"(Или отправьте 'пропустить' для стандартного сообщения)",
        parse_mode='HTML'
    )
    return WAITING_FOR_CLOSE_MESSAGE


async def close_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщения для закрытия группы"""
    message_text = update.message.text.strip()
    
    group_id = context.user_data.get('close_group_id')
    if not group_id:
        await update.message.reply_text("❌ Ошибка. Попробуйте снова использовать /close_group")
        context.user_data.clear()
        return ConversationHandler.END
    
    # Получаем группу
    try:
        group = await sync_to_async(Group.objects.select_related('owner').get)(id=group_id)
    except Group.DoesNotExist:
        await update.message.reply_text("❌ Группа не найдена.")
        context.user_data.clear()
        return ConversationHandler.END
    
    # Проверяем, что пользователь все еще владелец
    if group.owner_id != update.effective_user.id:
        await update.message.reply_text("❌ Вы не являетесь владельцем этой группы.")
        context.user_data.clear()
        return ConversationHandler.END
    
    # Если пользователь хочет пропустить, используем стандартное сообщение
    if message_text.lower() in ['пропустить', 'skip', 'пропустить', '']:
        message_text = (
            f"🔒 Группа '{group.name}' закрыта владельцем.\n\n"
            f"Спасибо за участие в Тайном Санте! 🎄\n"
            f"До встречи в следующем году! 🎅"
        )
    else:
        # Используем введенное сообщение
        if len(message_text) > 1000:
            await update.message.reply_text("❌ Сообщение слишком длинное (максимум 1000 символов). Попробуйте снова:")
            return WAITING_FOR_CLOSE_MESSAGE
        message_text = (
            f"🔒 Группа '{group.name}' закрыта владельцем.\n\n"
            f"{message_text}"
        )
    
    # Получаем всех участников группы
    participants = await sync_to_async(list)(
        Participant.objects.filter(group=group).select_related('user')
    )
    
    # Отправляем сообщение всем участникам
    notified_count = 0
    for participant in participants:
        try:
            await context.bot.send_message(
                chat_id=participant.user.telegram_id,
                text=message_text
            )
            notified_count += 1
        except Exception as e:
            print(f"Ошибка отправки сообщения участнику {participant.user.telegram_id}: {e}")
    
    # Закрываем группу
    group.status = 'closed'
    group.is_closed = True
    await sync_to_async(group.save)()
    
    hints = get_command_hints("/delete_group", "/create_group", "/my_groups", "/help")
    await update.message.reply_text(
        f"✅ Группа '{group.name}' успешно закрыта!\n\n"
        f"📨 Уведомлено участников: {notified_count} из {len(participants)}" + hints
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def close_group_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена закрытия группы"""
    context.user_data.clear()
    await update.message.reply_text("❌ Закрытие группы отменено.")
    return ConversationHandler.END


async def delete_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления закрытой группы"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return ConversationHandler.END
    
    # Находим все закрытые группы пользователя (где он владелец)
    owned_closed_groups = await sync_to_async(list)(
        Group.objects.filter(owner=telegram_user, status='closed').select_related('owner').order_by('-created_at')
    )
    
    # Находим закрытые группы, где пользователь участник
    participations = await sync_to_async(list)(
        Participant.objects.filter(
            user=telegram_user,
            group__status='closed'
        ).select_related('group', 'group__owner')
    )
    participant_closed_groups = [p.group for p in participations if p.group.owner_id != telegram_user.id]
    
    all_closed_groups = owned_closed_groups + participant_closed_groups
    
    if not all_closed_groups:
        hints = get_command_hints("/my_groups", "/create_group", "/help")
        await update.message.reply_text(
            "❌ У вас нет закрытых групп для удаления." + hints
        )
        return ConversationHandler.END
    
    # Сохраняем список групп в контексте
    context.user_data['closed_groups'] = [
        {
            'id': g.id,
            'name': g.name,
            'code': g.code,
            'is_owner': g.owner.telegram_id == telegram_user.telegram_id
        }
        for g in all_closed_groups
    ]
    
    # Формируем список групп
    groups_list = []
    for i, group_data in enumerate(context.user_data['closed_groups'], 1):
        owner_text = "👑 (владелец)" if group_data['is_owner'] else "👥 (участник)"
        groups_list.append(f"{i}. {group_data['name']} ({group_data['code']}) {owner_text}")
    
    groups_text = "\n".join(groups_list)
    
    await update.message.reply_text(
        f"🗑️ Удаление закрытых групп\n\n"
        f"Найдено закрытых групп: {len(all_closed_groups)}\n\n"
        f"{groups_text}\n\n"
        f"Введите:\n"
        f"• Номер группы для удаления (1, 2, 3...)\n"
        f"• 'все' или 'all' для удаления всех групп\n"
        f"• 'отмена' или 'cancel' для отмены"
    )
    return WAITING_FOR_DELETE_GROUP_SELECTION


async def delete_group_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора группы для удаления"""
    user_input = update.message.text.strip().lower()
    
    closed_groups = context.user_data.get('closed_groups', [])
    if not closed_groups:
        await update.message.reply_text("❌ Ошибка. Попробуйте снова использовать /delete_group")
        context.user_data.clear()
        return ConversationHandler.END
    
    # Проверяем, хочет ли пользователь удалить все группы
    if user_input in ['все', 'all', 'удалить все', 'delete all']:
        deleted_count = 0
        for group_data in closed_groups:
            try:
                group = await sync_to_async(Group.objects.select_related('owner').get)(id=group_data['id'])
                # Проверяем, что пользователь является владельцем или участником
                if group.owner_id == update.effective_user.id:
                    # Если владелец - удаляем группу полностью
                    await sync_to_async(group.delete)()
                    deleted_count += 1
                else:
                    # Если участник - удаляем только его участие
                    telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=update.effective_user.id)
                    participation = await sync_to_async(
                        Participant.objects.get
                    )(group=group, user=telegram_user)
                    await sync_to_async(participation.delete)()
                    deleted_count += 1
            except Exception as e:
                print(f"Ошибка удаления группы {group_data['id']}: {e}")
        
        await update.message.reply_text(
            f"✅ Удалено групп: {deleted_count} из {len(closed_groups)}"
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Проверяем, хочет ли пользователь отменить
    if user_input in ['отмена', 'cancel', 'отменить']:
        context.user_data.clear()
        await update.message.reply_text("❌ Удаление отменено.")
        return ConversationHandler.END
    
    # Пытаемся распознать номер группы
    try:
        group_number = int(user_input)
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный ввод. Введите номер группы (1, 2, 3...), 'все' для удаления всех или 'отмена' для отмены:"
        )
        return WAITING_FOR_DELETE_GROUP_SELECTION
    
    if group_number < 1 or group_number > len(closed_groups):
        await update.message.reply_text(
            f"❌ Неверный номер. Введите число от 1 до {len(closed_groups)}:"
        )
        return WAITING_FOR_DELETE_GROUP_SELECTION
    
    # Получаем выбранную группу
    selected_group_data = closed_groups[group_number - 1]
    
    try:
        group = await sync_to_async(Group.objects.select_related('owner').get)(id=selected_group_data['id'])
        
        # Проверяем, что пользователь является владельцем или участником
        if group.owner_id == update.effective_user.id:
            # Если владелец - удаляем группу полностью
            group_name = group.name
            await sync_to_async(group.delete)()
            hints = get_command_hints("/my_groups", "/create_group", "/help")
            await update.message.reply_text(
                f"✅ Группа '{group_name}' успешно удалена!\n\n"
                f"Удалены все связанные данные (участники, розыгрыши и т.д.)." + hints
            )
        else:
            # Если участник - удаляем только его участие
            telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=update.effective_user.id)
            participation = await sync_to_async(
                Participant.objects.get
            )(group=group, user=telegram_user)
            await sync_to_async(participation.delete)()
            hints = get_command_hints("/my_groups", "/join_group", "/help")
            await update.message.reply_text(
                f"✅ Вы удалены из группы '{group.name}'." + hints
            )
    except Group.DoesNotExist:
        await update.message.reply_text("❌ Группа не найдена.")
    except Participant.DoesNotExist:
        await update.message.reply_text("❌ Вы не являетесь участником этой группы.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при удалении: {e}")
        print(f"Ошибка удаления группы: {e}")
    
    context.user_data.clear()
    return ConversationHandler.END


async def delete_group_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена удаления группы"""
    context.user_data.clear()
    await update.message.reply_text("❌ Удаление отменено.")
    return ConversationHandler.END


async def distribute_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расдача подарков (команда для владельца группы)"""
    user = update.effective_user
    
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user.id)
    except TelegramUser.DoesNotExist:
        await update.message.reply_text("❌ Вы не зарегистрированы в системе. Используйте /start")
        return
    
    # Находим группу со статусом "жеребьевка проведена"
    group = await sync_to_async(Group.objects.filter(owner=telegram_user, status='drawn').first)()
    
    if not group:
        hints = get_command_hints("/my_groups", "/draw", "/help")
        await update.message.reply_text(
            "❌ У вас нет группы со статусом 'Жеребьевка проведена'." + hints
        )
        return
    
    # Получаем все розыгрыши с предзагрузкой связанных объектов
    draws = await sync_to_async(list)(
        Draw.objects.filter(group=group).select_related(
            'giver__user', 
            'receiver__user',
            'giver'
        )
    )
    
    if not draws:
        await update.message.reply_text("❌ В группе нет результатов розыгрыша.")
        return
    
    # Рассылаем подарки
    sent_count = 0
    for draw_obj in draws:
        try:
            receiver_telegram_id = draw_obj.receiver.user.telegram_id
            giver_name = draw_obj.giver.name
            
            if group.gift_via_bot and (draw_obj.giver.gift_message or draw_obj.giver.gift_photo_file_id):
                # Отправляем подарок от бота (без указания дарителя - это Тайный Санта!)
                if draw_obj.giver.gift_photo_file_id:
                    # Если есть фото, отправляем фото с подписью
                    message_text = "🎁 Подарок от Тайного Санты! 🎄"
                    if draw_obj.giver.gift_message:
                        message_text += f"\n\n🎁 Ваш подарок:\n{draw_obj.giver.gift_message}"
                    message_text += "\n\nСчастливого праздника! 🎅"
                    
                    await context.bot.send_photo(
                        chat_id=receiver_telegram_id,
                        photo=draw_obj.giver.gift_photo_file_id,
                        caption=message_text,
                        parse_mode='HTML'
                    )
                else:
                    # Если только текст без фото
                    message_text = (
                        f"🎁 Подарок от Тайного Санты! 🎄\n\n"
                        f"🎁 Ваш подарок:\n{draw_obj.giver.gift_message}\n\n"
                        f"Счастливого праздника! 🎅"
                    )
                    await context.bot.send_message(
                        chat_id=receiver_telegram_id,
                        text=message_text,
                        parse_mode='HTML'
                    )
            else:
                # Если подарок не через бота или не отправлен
                message_text = (
                    f"🎁 Подарок от Тайного Санты! 🎄\n\n"
                    f"Подарок будет в условленном месте! 🎅"
                )
                await context.bot.send_message(
                    chat_id=receiver_telegram_id,
                    text=message_text,
                    parse_mode='HTML'
                )
            sent_count += 1
        except Exception as e:
            print(f"Ошибка отправки подарка получателю {draw_obj.receiver.user.telegram_id}: {e}")
    
    # Меняем статус на "расдача подарков"
    group.status = 'distribution'
    await sync_to_async(group.save)()
    
    # Проверяем, нужно ли автоматически закрыть группу
    from datetime import date
    if group.close_date and group.close_date <= date.today():
        group.status = 'closed'
        await sync_to_async(group.save)()
        close_text = "\n\nГруппа автоматически закрыта (дата закрытия наступила)."
    else:
        close_text = f"\n\nГруппа будет автоматически закрыта {group.close_date.strftime('%d.%m.%Y') if group.close_date else 'на следующий день после расдачи'}."
    
    hints = get_command_hints("/view_gifts", "/my_groups", "/close_group", "/help")
    await update.message.reply_text(
        f"✅ Подарки в группе '{group.name}' разосланы!\n\n"
        f"📨 Отправлено подарков: {sent_count} из {len(draws)}\n\n"
        f"Статус группы изменен на 'Расдача подарков'.{close_text}" + hints
    )


def setup_handlers(application):
    """Настройка обработчиков команд"""
    
    # ConversationHandler для создания группы
    create_group_handler = ConversationHandler(
        entry_points=[CommandHandler('create_group', create_group_start)],
        states={
            WAITING_FOR_GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_group_name)],
            WAITING_FOR_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_group_description)],
            WAITING_FOR_GIFT_VIA_BOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_group_gift_via_bot)],
            WAITING_FOR_DRAW_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_group_draw_date)],
            WAITING_FOR_DISTRIBUTION_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_group_distribution_date)],
            WAITING_FOR_CLOSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_group_close_date)],
        },
        fallbacks=[CommandHandler('cancel', create_group_cancel)],
    )
    
    # ConversationHandler для вступления в группу
    join_group_handler = ConversationHandler(
        entry_points=[CommandHandler('join_group', join_group_start)],
        states={
            WAITING_FOR_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, join_group_code)],
        },
        fallbacks=[CommandHandler('cancel', join_group_cancel)],
    )
    
    # ConversationHandler для установки имени
    set_name_handler = ConversationHandler(
        entry_points=[CommandHandler('set_name', set_name_start)],
        states={
            WAITING_FOR_GROUP_SELECTION_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name_select_group)],
            WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_name)],
        },
        fallbacks=[CommandHandler('cancel', set_name_cancel)],
    )
    
    # ConversationHandler для отправки подарка
    send_gift_handler = ConversationHandler(
        entry_points=[CommandHandler('send_gift', send_gift_start)],
        states={
            WAITING_FOR_GROUP_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_gift_select_group)],
            WAITING_FOR_GIFT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_gift),
                MessageHandler(filters.PHOTO, send_gift),
            ],
        },
        fallbacks=[CommandHandler('cancel', send_gift_cancel)],
    )
    
    # ConversationHandler для закрытия группы
    close_group_handler = ConversationHandler(
        entry_points=[CommandHandler('close_group', close_group_start)],
        states={
            WAITING_FOR_CLOSE_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, close_group_message)],
        },
        fallbacks=[CommandHandler('cancel', close_group_cancel)],
    )
    
    # ConversationHandler для удаления группы
    delete_group_handler = ConversationHandler(
        entry_points=[CommandHandler('delete_group', delete_group_start)],
        states={
            WAITING_FOR_DELETE_GROUP_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_group_selection)],
        },
        fallbacks=[CommandHandler('cancel', delete_group_cancel)],
    )
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(create_group_handler)
    application.add_handler(join_group_handler)
    application.add_handler(CommandHandler('leave_group', leave_group))
    application.add_handler(CommandHandler('my_groups', my_groups))
    application.add_handler(set_name_handler)
    application.add_handler(CommandHandler('draw', draw))
    application.add_handler(send_gift_handler)
    application.add_handler(CommandHandler('distribute_gifts', distribute_gifts))
    application.add_handler(CommandHandler('view_gifts', view_gifts))
    application.add_handler(close_group_handler)
    application.add_handler(delete_group_handler)
    application.add_handler(CommandHandler('invite', get_invite))
    # Обработчик пересланных сообщений
    application.add_handler(MessageHandler(filters.TEXT & filters.FORWARDED, handle_forwarded_message))
    # Обработчик непонятных сообщений (должен быть последним, чтобы не перехватывать сообщения из ConversationHandler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message))
