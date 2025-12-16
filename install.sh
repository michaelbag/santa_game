#!/bin/bash

# Скрипт установки Santa Game на Ubuntu Server 24.04
# Автор: Michael BAG
# Версия: 1.2
#
# Использование:
#   sudo ./install.sh
#
# Скрипт интерактивно запросит все необходимые параметры:
#   - Путь установки
#   - Имя системного пользователя
#   - Токен Telegram бота
#   - Параметры базы данных (PostgreSQL или SQLite)
#   - Создание суперпользователя Django
#
# Автоматически выполнит:
#   - Установку системных зависимостей
#   - Создание пользователя и базы данных
#   - Клонирование репозитория
#   - Настройку виртуальной среды
#   - Создание конфигурационных файлов
#   - Настройку systemd сервиса

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка, что скрипт запущен от root
if [ "$EUID" -ne 0 ]; then 
    error "Пожалуйста, запустите скрипт с правами sudo: sudo ./install.sh"
    exit 1
fi

# Проверка операционной системы
if [ ! -f /etc/os-release ]; then
    error "Не удалось определить операционную систему"
    exit 1
fi

. /etc/os-release
if [[ "$ID" != "ubuntu" ]] || [[ "$VERSION_ID" != "24.04" ]]; then
    warning "Этот скрипт предназначен для Ubuntu 24.04"
    warning "Обнаружена система: $PRETTY_NAME"
    read -p "Продолжить установку? (y/n) [n]: " continue_install
    if [[ ! "$continue_install" =~ ^[Yy]$ ]]; then
        error "Установка прервана"
        exit 1
    fi
fi

info "=== Установка Santa Game Telegram Bot ==="
info "Система: $PRETTY_NAME"
echo ""

# Переменные по умолчанию
INSTALL_DIR="/opt/santa_game"
SYSTEM_USER="santa_game"
REPO_URL="https://github.com/michaelbag/santa_game.git"

# Шаг 1: Запрос пути установки
echo ""
info "Шаг 1: Настройка пути установки"
read -p "Путь установки [$INSTALL_DIR]: " user_install_dir
INSTALL_DIR=${user_install_dir:-$INSTALL_DIR}
info "Используется путь: $INSTALL_DIR"

# Шаг 2: Запрос имени системного пользователя
echo ""
info "Шаг 2: Настройка системного пользователя"
read -p "Имя системного пользователя [$SYSTEM_USER]: " user_system_user
SYSTEM_USER=${user_system_user:-$SYSTEM_USER}
info "Используется пользователь: $SYSTEM_USER"

# Шаг 3: Запрос токена Telegram бота
echo ""
info "Шаг 3: Настройка Telegram бота"
read -p "Telegram Bot Token (от @BotFather): " TELEGRAM_BOT_TOKEN
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    error "Токен бота обязателен для работы!"
    exit 1
fi

# Шаг 4: Настройка PostgreSQL
echo ""
info "Шаг 4: Настройка базы данных PostgreSQL"
read -p "Использовать PostgreSQL? (y/n) [y]: " use_postgresql
use_postgresql=${use_postgresql:-y}

if [[ "$use_postgresql" =~ ^[Yy]$ ]]; then
    DB_ENGINE="postgresql"
    read -p "Имя базы данных [santa_game]: " DB_NAME
    DB_NAME=${DB_NAME:-santa_game}
    
    read -p "Пользователь PostgreSQL [santa_game]: " DB_USER
    DB_USER=${DB_USER:-santa_game}
    
    read -sp "Пароль для пользователя PostgreSQL: " DB_PASSWORD
    echo ""
    if [ -z "$DB_PASSWORD" ]; then
        error "Пароль обязателен!"
        exit 1
    fi
    
    read -p "Хост PostgreSQL [localhost]: " DB_HOST
    DB_HOST=${DB_HOST:-localhost}
    
    read -p "Порт PostgreSQL [5432]: " DB_PORT
    DB_PORT=${DB_PORT:-5432}
else
    DB_ENGINE="sqlite3"
    DB_NAME=""
    DB_USER=""
    DB_PASSWORD=""
    DB_HOST=""
    DB_PORT=""
    info "Будет использоваться SQLite"
fi

# Шаг 5: Проверка системных зависимостей
echo ""
info "Шаг 5: Проверка системных зависимостей"

# Проверка Python
if ! command -v python3.14 &> /dev/null && ! command -v python3 &> /dev/null; then
    warning "Python 3 не найден. Устанавливаю..."
    apt update
    apt install -y python3 python3-venv python3-pip
else
    success "Python найден"
fi

# Проверка git
if ! command -v git &> /dev/null; then
    warning "Git не найден. Устанавливаю..."
    apt install -y git
else
    success "Git найден"
fi

# Проверка PostgreSQL (если используется)
if [[ "$DB_ENGINE" == "postgresql" ]]; then
    if ! command -v psql &> /dev/null; then
        warning "PostgreSQL не найден. Устанавливаю..."
        apt install -y postgresql postgresql-contrib libpq-dev
        systemctl start postgresql
        systemctl enable postgresql
    else
        success "PostgreSQL найден"
    fi
fi

# Установка дополнительных зависимостей
if ! dpkg -l | grep -q build-essential; then
    info "Устанавливаю build-essential..."
    apt install -y build-essential python3-dev
fi

# Шаг 6: Создание системного пользователя
echo ""
info "Шаг 6: Создание системного пользователя"
if id "$SYSTEM_USER" &>/dev/null; then
    warning "Пользователь $SYSTEM_USER уже существует"
    read -p "Использовать существующего пользователя? (y/n) [y]: " use_existing_user
    if [[ ! "$use_existing_user" =~ ^[Yy]$ ]] && [ -n "$use_existing_user" ]; then
        error "Установка прервана"
        exit 1
    fi
    success "Используется существующий пользователь $SYSTEM_USER"
else
    useradd -r -s /bin/bash -d "$INSTALL_DIR" "$SYSTEM_USER"
    success "Пользователь $SYSTEM_USER создан"
fi

# Создание директории установки
mkdir -p "$INSTALL_DIR"
chown "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR"

# Шаг 7: Настройка PostgreSQL (если используется)
if [[ "$DB_ENGINE" == "postgresql" ]]; then
    echo ""
    info "Шаг 7: Настройка базы данных PostgreSQL"
    
    # Проверка существования пользователя
    if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
        warning "Пользователь PostgreSQL $DB_USER уже существует"
        read -p "Изменить пароль? (y/n) [y]: " change_password
        if [[ "$change_password" =~ ^[Yy]$ ]] || [ -z "$change_password" ]; then
            sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
            success "Пароль обновлен"
        else
            info "Пароль не изменен"
        fi
    else
        sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
        success "Пользователь PostgreSQL $DB_USER создан"
    fi
    
    # Проверка существования базы данных
    if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
        warning "База данных $DB_NAME уже существует"
        read -p "Использовать существующую базу? (y/n) [y]: " use_existing_db
        if [[ ! "$use_existing_db" =~ ^[Yy]$ ]] && [ -n "$use_existing_db" ]; then
            error "Установка прервана"
            exit 1
        fi
        success "Используется существующая база данных $DB_NAME"
    else
        sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
        success "База данных $DB_NAME создана"
    fi
    
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
    success "Права на базу данных предоставлены"
fi

# Шаг 8: Клонирование репозитория
echo ""
info "Шаг 8: Клонирование репозитория"
if [ -d "$INSTALL_DIR/.git" ]; then
    warning "Репозиторий уже существует в $INSTALL_DIR"
    read -p "Обновить существующий репозиторий? (y/n) [y]: " update_repo
    if [[ "$update_repo" =~ ^[Yy]$ ]] || [ -z "$update_repo" ]; then
        # Исправляем права владения репозитория
        chown -R "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR"
        
        # Добавляем директорию в safe.directory для git (если нужно)
        sudo -u "$SYSTEM_USER" bash -c "git config --global --add safe.directory $INSTALL_DIR 2>/dev/null || true"
        
        # Проверяем и настраиваем remote, если нужно
        sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && \
            if ! git remote get-url origin &>/dev/null; then
                git remote add origin $REPO_URL
            elif [ \"\$(git remote get-url origin)\" != \"$REPO_URL\" ]; then
                git remote set-url origin $REPO_URL
            fi && \
            git fetch origin && \
            git pull origin main"
        success "Репозиторий обновлен"
    fi
elif [ "$(ls -A $INSTALL_DIR 2>/dev/null)" ]; then
    error "Директория $INSTALL_DIR не пуста и не является git репозиторием"
    read -p "Очистить директорию и продолжить? (y/n) [n]: " clean_dir
    if [[ "$clean_dir" =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"/*
        sudo -u "$SYSTEM_USER" git clone "$REPO_URL" "$INSTALL_DIR"
        # Убеждаемся, что права владения установлены правильно
        chown -R "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR"
        # Добавляем директорию в safe.directory для git
        sudo -u "$SYSTEM_USER" bash -c "git config --global --add safe.directory $INSTALL_DIR 2>/dev/null || true"
        success "Репозиторий склонирован"
    else
        error "Установка прервана"
        exit 1
    fi
else
    sudo -u "$SYSTEM_USER" git clone "$REPO_URL" "$INSTALL_DIR"
    # Убеждаемся, что права владения установлены правильно
    chown -R "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR"
    # Добавляем директорию в safe.directory для git
    sudo -u "$SYSTEM_USER" bash -c "git config --global --add safe.directory $INSTALL_DIR 2>/dev/null || true"
    success "Репозиторий склонирован"
fi

# Шаг 9: Создание виртуальной среды
echo ""
info "Шаг 9: Создание виртуальной среды Python"
if [ -d "$INSTALL_DIR/venv" ]; then
    warning "Виртуальная среда уже существует"
    read -p "Пересоздать виртуальную среду? (y/n) [n]: " recreate_venv
    if [[ "$recreate_venv" =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR/venv"
        sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && python3 -m venv venv"
        success "Виртуальная среда пересоздана"
    fi
else
    sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && python3 -m venv venv"
    success "Виртуальная среда создана"
fi

# Шаг 10: Установка зависимостей
echo ""
info "Шаг 10: Установка зависимостей Python"
sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
success "Зависимости установлены"

# Шаг 11: Запрос домена для Django админки
echo ""
info "Шаг 11: Настройка домена для Django админки"
read -p "Имя домена для Django админки (например: example.com) [localhost]: " ADMIN_DOMAIN
ADMIN_DOMAIN=${ADMIN_DOMAIN:-localhost}
info "Используется домен: $ADMIN_DOMAIN"

# Шаг 12: Создание файла .env
echo ""
info "Шаг 12: Создание файла конфигурации .env"
cat > "$INSTALL_DIR/.env" << EOF
# Telegram Bot Token
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN

# Database Configuration
EOF

if [[ "$DB_ENGINE" == "postgresql" ]]; then
    cat >> "$INSTALL_DIR/.env" << EOF
DB_ENGINE=postgresql
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
EOF
else
    cat >> "$INSTALL_DIR/.env" << EOF
# Используется SQLite по умолчанию
# DB_ENGINE=sqlite3
EOF
fi

chown "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR/.env"
chmod 600 "$INSTALL_DIR/.env"
success "Файл .env создан"

# Обновление ALLOWED_HOSTS в settings.py
if [ -f "$INSTALL_DIR/santagame/settings.py" ]; then
    # Формируем список доменов для ALLOWED_HOSTS
    if [[ "$ADMIN_DOMAIN" == "localhost" ]] || [[ "$ADMIN_DOMAIN" == "127.0.0.1" ]]; then
        ALLOWED_HOSTS_STR="['$ADMIN_DOMAIN', '127.0.0.1']"
    else
        ALLOWED_HOSTS_STR="['$ADMIN_DOMAIN', 'www.$ADMIN_DOMAIN', 'localhost', '127.0.0.1']"
    fi
    
    # Обновляем ALLOWED_HOSTS в settings.py используя sed
    sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && \
        sed -i \"s/^ALLOWED_HOSTS = .*/ALLOWED_HOSTS = $ALLOWED_HOSTS_STR/\" santagame/settings.py"
    success "ALLOWED_HOSTS обновлен в settings.py: $ALLOWED_HOSTS_STR"
    
    # Настраиваем CSRF_TRUSTED_ORIGINS для работы без DEBUG
    if [[ "$ADMIN_DOMAIN" != "localhost" ]] && [[ "$ADMIN_DOMAIN" != "127.0.0.1" ]]; then
        CSRF_ORIGINS_STR="['https://$ADMIN_DOMAIN', 'https://www.$ADMIN_DOMAIN', 'http://localhost:8000', 'http://127.0.0.1:8000']"
        sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && \
            sed -i \"s/^CSRF_TRUSTED_ORIGINS = .*/CSRF_TRUSTED_ORIGINS = $CSRF_ORIGINS_STR/\" santagame/settings.py"
        success "CSRF_TRUSTED_ORIGINS обновлен в settings.py: $CSRF_ORIGINS_STR"
    else
        CSRF_ORIGINS_STR="['http://localhost:8000', 'http://127.0.0.1:8000']"
        sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && \
            sed -i \"s/^CSRF_TRUSTED_ORIGINS = .*/CSRF_TRUSTED_ORIGINS = $CSRF_ORIGINS_STR/\" santagame/settings.py"
        success "CSRF_TRUSTED_ORIGINS обновлен в settings.py: $CSRF_ORIGINS_STR"
    fi
fi

# Шаг 13: Применение миграций
echo ""
info "Шаг 13: Применение миграций базы данных"
sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && source venv/bin/activate && python manage.py migrate"
success "Миграции применены"

# Шаг 13.5: Сбор статических файлов
echo ""
info "Шаг 13.5: Сбор статических файлов"
sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && source venv/bin/activate && python manage.py collectstatic --noinput"
success "Статические файлы собраны"

# Шаг 14: Создание суперпользователя (опционально)
echo ""
read -p "Создать суперпользователя Django для доступа к админке? (y/n) [n]: " create_superuser
if [[ "$create_superuser" =~ ^[Yy]$ ]]; then
    sudo -u "$SYSTEM_USER" bash -c "cd $INSTALL_DIR && source venv/bin/activate && python manage.py createsuperuser"
fi

# Шаг 15: Создание systemd сервиса
echo ""
info "Шаг 15: Создание systemd сервиса"
SERVICE_FILE="/etc/systemd/system/santa-game-bot.service"

# Формируем зависимости для systemd
if [[ "$DB_ENGINE" == "postgresql" ]]; then
    AFTER_DEPS="After=network.target postgresql.service"
    REQUIRES_DEPS="Requires=postgresql.service"
else
    AFTER_DEPS="After=network.target"
    REQUIRES_DEPS=""
fi

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Santa Game Telegram Bot
$AFTER_DEPS
$REQUIRES_DEPS

[Service]
Type=simple
User=$SYSTEM_USER
Group=$SYSTEM_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/manage.py runbot
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
success "Systemd сервис создан: $SERVICE_FILE"

# Шаг 16: Настройка прав доступа
echo ""
info "Шаг 16: Настройка прав доступа"
chown -R "$SYSTEM_USER:$SYSTEM_USER" "$INSTALL_DIR"
chmod 700 "$INSTALL_DIR"
success "Права доступа настроены"

# Шаг 17: Создание сервиса Django Admin (опционально)
echo ""
info "Шаг 17: Настройка Django Admin сервиса"
ADMIN_SERVICE_CREATED="no"
read -p "Создать systemd сервис для Django Admin? (y/n) [n]: " create_admin_service
if [[ "$create_admin_service" =~ ^[Yy]$ ]]; then
    ADMIN_SERVICE_CREATED="yes"
    ADMIN_SERVICE_FILE="/etc/systemd/system/santa-game-admin.service"
    read -p "Порт для Django Admin [8000]: " ADMIN_PORT
    ADMIN_PORT=${ADMIN_PORT:-8000}
    
    # Формируем зависимости для systemd
    if [[ "$DB_ENGINE" == "postgresql" ]]; then
        AFTER_DEPS="After=network.target postgresql.service"
        REQUIRES_DEPS="Requires=postgresql.service"
    else
        AFTER_DEPS="After=network.target"
        REQUIRES_DEPS=""
    fi
    
    cat > "$ADMIN_SERVICE_FILE" << EOF
[Unit]
Description=Santa Game Django Admin
$AFTER_DEPS
$REQUIRES_DEPS

[Service]
Type=simple
User=$SYSTEM_USER
Group=$SYSTEM_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/manage.py runserver 0.0.0.0:$ADMIN_PORT
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    success "Systemd сервис для Django Admin создан: $ADMIN_SERVICE_FILE"
    
    read -p "Запустить и включить автозапуск Django Admin? (y/n) [n]: " start_admin_service
    if [[ "$start_admin_service" =~ ^[Yy]$ ]]; then
        systemctl enable santa-game-admin.service
        systemctl start santa-game-admin.service
        success "Django Admin запущен на порту $ADMIN_PORT"
        info "Доступ к админке: http://$(hostname -I | awk '{print $1}'):$ADMIN_PORT/admin/"
    fi
    
    # Сохраняем порт в переменную для итогового вывода
    ADMIN_PORT_FINAL=$ADMIN_PORT
else
    ADMIN_PORT_FINAL=""
fi

# Шаг 18: Запуск сервиса бота
echo ""
info "Шаг 18: Запуск сервиса бота"
read -p "Запустить и включить автозапуск сервиса бота? (y/n) [y]: " start_service
if [[ "$start_service" =~ ^[Yy]$ ]] || [ -z "$start_service" ]; then
    systemctl enable santa-game-bot.service
    systemctl start santa-game-bot.service
    success "Сервис бота запущен и включен автозапуск"
    
    echo ""
    info "Проверка статуса сервиса:"
    systemctl status santa-game-bot.service --no-pager -l
else
    warning "Сервис бота не запущен. Для запуска выполните:"
    echo "  sudo systemctl enable santa-game-bot.service"
    echo "  sudo systemctl start santa-game-bot.service"
fi

# Итоговая информация
echo ""
echo ""
success "=== Установка завершена успешно! ==="
echo ""
info "Полезные команды для бота:"
echo "  Статус сервиса:    sudo systemctl status santa-game-bot.service"
echo "  Остановить:         sudo systemctl stop santa-game-bot.service"
echo "  Запустить:          sudo systemctl start santa-game-bot.service"
echo "  Перезапустить:      sudo systemctl restart santa-game-bot.service"
echo "  Просмотр логов:     sudo journalctl -u santa-game-bot.service -f"
if [[ "$ADMIN_SERVICE_CREATED" == "yes" ]]; then
    echo ""
    info "Полезные команды для Django Admin:"
    echo "  Статус сервиса:    sudo systemctl status santa-game-admin.service"
    echo "  Остановить:         sudo systemctl stop santa-game-admin.service"
    echo "  Запустить:          sudo systemctl start santa-game-admin.service"
    echo "  Перезапустить:      sudo systemctl restart santa-game-admin.service"
    echo "  Просмотр логов:     sudo journalctl -u santa-game-admin.service -f"
fi
echo ""
info "Файлы конфигурации:"
echo "  .env файл:          $INSTALL_DIR/.env"
echo "  Systemd сервис бота: $SERVICE_FILE"
if [[ "$ADMIN_SERVICE_CREATED" == "yes" ]]; then
    echo "  Systemd сервис админки: $ADMIN_SERVICE_FILE"
    echo "  Порт админки:         $ADMIN_PORT_FINAL"
    echo ""
    info "Настройка Nginx:"
    echo "  Пример конфигурации:   $INSTALL_DIR/nginx-santa-game-admin.conf.example"
    echo "  Для настройки HTTPS через Nginx см. README.md"
fi
echo ""
info "Хранение данных:"
echo "  База данных:       В PostgreSQL (если выбран) или SQLite файл"
echo "  Картинки подарков:  Хранятся как file_id в базе данных"
echo "                     (файлы находятся на серверах Telegram)"
echo ""
info "Обновление проекта:"
echo "  Для обновления до последней версии выполните:"
echo "    cd $INSTALL_DIR"
echo "    sudo -u $SYSTEM_USER git fetch origin"
echo "    sudo -u $SYSTEM_USER git pull origin main"
echo "    sudo systemctl restart santa-game-bot.service"
if [[ "$DB_ENGINE" == "postgresql" ]]; then
    echo ""
    info "База данных PostgreSQL:"
    echo "  Имя БД:            $DB_NAME"
    echo "  Пользователь:      $DB_USER"
    echo "  Хост:              $DB_HOST:$DB_PORT"
fi
echo ""

