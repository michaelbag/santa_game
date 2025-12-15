from django.contrib import admin
from .models import TelegramUser, Group, Participant, Draw


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'first_name', 'created_at')
    search_fields = ('telegram_id', 'username', 'first_name')


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'owner', 'status', 'gift_via_bot', 'draw_date', 'gift_distribution_date', 'close_date', 'created_at')
    list_filter = ('status', 'gift_via_bot', 'is_closed', 'created_at')
    search_fields = ('name', 'code')
    readonly_fields = ('code', 'created_at', 'drawn_at')


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'user', 'gift_sent', 'has_gift_photo', 'joined_at')
    list_filter = ('group', 'gift_sent', 'joined_at')
    search_fields = ('name', 'group__name')
    
    def has_gift_photo(self, obj):
        return bool(obj.gift_photo_file_id)
    has_gift_photo.boolean = True
    has_gift_photo.short_description = 'Есть фото'


@admin.register(Draw)
class DrawAdmin(admin.ModelAdmin):
    list_display = ('group', 'giver', 'receiver', 'created_at')
    list_filter = ('group', 'created_at')
    search_fields = ('group__name', 'giver__name', 'receiver__name')
