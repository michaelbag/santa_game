from django.shortcuts import render
from django.conf import settings


def index(request):
    """Главная страница с информацией о проекте и ссылкой на админку"""
    context = {
        'project_name': 'Игра "Тайный Санта"',
        'version': '1.1',
        'author': 'Michael BAG',
        'author_telegram': '@michaelbag',
        'author_email': 'mk@remark.pro',
        'admin_url': '/admin/',
    }
    return render(request, 'bot/index.html', context)
