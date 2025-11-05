# Развёртывание на виртуальной машине (systemd + venv)

Инструкция описывает полный цикл подготовки чистой Ubuntu Server 22.04 (подойдёт любая современная Debian/Ubuntu) для запуска бота через `systemd` и настройки резервного копирования SQLite-базы.

## 1. Подготовка ОС

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git sqlite3 unzip
sudo apt install -y cron # обычно уже установлен
```

> При необходимости дополнительно установите `ufw`, `fail2ban` и другое окружение безопасности.

Создайте отдельного пользователя без прав `sudo`, под которым будет работать бот (по желанию):

```bash
sudo adduser --system --home /opt/cleaning-bot --group cleaningbot
```

## 2. Получение кода

```bash
sudo -iu cleaningbot
cd /opt/cleaning-bot
# Склонируйте репозиторий (замените URL на свой)
git clone https://example.com/home-tasks.git app
cd app
```

Если используется приватный репозиторий, предварительно настройте SSH-ключи.

## 3. Создание виртуального окружения

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> Для воспроизводимости можно закрепить версию `pip` и выполнять установку через `pip install --no-deps --require-hashes`. Это выходит за рамки базовой инструкции.

## 4. Настройка конфигурации

1. Скопируйте пример `.env` и задайте токен:
   ```bash
   cp cleaning_bot/.env.example .env
   echo "TELEGRAM_BOT_TOKEN=xxx" >> .env
   ```
2. Отредактируйте `cleaning_bot/config.yaml`, `cleaning_bot/users.json`, `cleaning_bot/tasks.json` под ваш чат.
3. Убедитесь, что в `cleaning_bot/config.yaml` указан путь к базе, например:
   ```yaml
   database:
     path: /opt/cleaning-bot/data/db.sqlite3
   ```

Создайте каталог под данные (если используете путь вне репозитория):

```bash
mkdir -p /opt/cleaning-bot/data
sudo chown cleaningbot:cleaningbot /opt/cleaning-bot/data
```

## 5. Подготовка окружения для systemd

Создайте файл окружения, который будет читать `systemd` (отдельно от `.env`, чтобы не давать лишние права на репозиторий). Например `/etc/cleaning-bot/bot.env`:

```bash
sudo mkdir -p /etc/cleaning-bot
sudo tee /etc/cleaning-bot/bot.env > /dev/null <<'ENV'
TELEGRAM_BOT_TOKEN=xxx
ENV
sudo chown root:cleaningbot /etc/cleaning-bot/bot.env
sudo chmod 640 /etc/cleaning-bot/bot.env
```

Добавьте туда и другие переменные окружения, если они требуются.

## 6. Установка systemd unit

Скопируйте файл `deploy/systemd/cleaning-bot.service` в `/etc/systemd/system/`:

```bash
sudo cp deploy/systemd/cleaning-bot.service /etc/systemd/system/
sudo chown root:root /etc/systemd/system/cleaning-bot.service
sudo chmod 644 /etc/systemd/system/cleaning-bot.service
```

Обновите пути внутри файла при необходимости (например, если репозиторий находится не в `/opt/cleaning-bot/app`). После копирования выполните:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cleaning-bot.service
```

Проверьте статус:

```bash
sudo systemctl status cleaning-bot.service
```

Логи доступны через `journalctl -u cleaning-bot.service -f`.

## 7. Настройка резервного копирования базы данных

### Скрипт бэкапа

Скопируйте `deploy/scripts/backup_sqlite.sh` в каталог, доступный сервису, например `/opt/cleaning-bot/bin/`:

```bash
sudo mkdir -p /opt/cleaning-bot/bin
sudo cp deploy/scripts/backup_sqlite.sh /opt/cleaning-bot/bin/
sudo chown cleaningbot:cleaningbot /opt/cleaning-bot/bin/backup_sqlite.sh
sudo chmod 750 /opt/cleaning-bot/bin/backup_sqlite.sh
sudo mkdir -p /opt/cleaning-bot/backups
sudo chown cleaningbot:cleaningbot /opt/cleaning-bot/backups
```

Скрипт принимает три параметра: путь к базе, каталог для бэкапов и количество копий для хранения.

### Systemd unit + timer

Скопируйте файлы таймера:

```bash
sudo cp deploy/systemd/cleaning-bot-backup.service /etc/systemd/system/
sudo cp deploy/systemd/cleaning-bot-backup.timer /etc/systemd/system/
sudo chown root:root /etc/systemd/system/cleaning-bot-backup.*
sudo chmod 644 /etc/systemd/system/cleaning-bot-backup.*
```

Отредактируйте `Environment` в сервисе под ваш путь к данным и каталог бэкапов.

Активируйте таймер:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cleaning-bot-backup.timer
```

Для ручной проверки можно единоразово запустить сервис:

```bash
sudo systemctl start cleaning-bot-backup.service
```

Проверить ближайший запуск можно командой:

```bash
systemctl list-timers cleaning-bot-backup.timer
```

Готовые бэкапы будут появляться, например, в `/opt/cleaning-bot/backups`. Для дополнительной надёжности синхронизируйте каталог с внешним хранилищем (`rclone`, `scp`, S3 и т.д.).

## 8. Обновление приложения

1. Остановите сервис: `sudo systemctl stop cleaning-bot.service`.
2. Переключитесь в репозиторий под пользователем `cleaningbot` и выполните `git pull`.
3. Обновите зависимости: `source .venv/bin/activate && pip install -r requirements.txt`.
4. Прогоните тесты при необходимости: `pytest`.
5. Запустите сервис: `sudo systemctl start cleaning-bot.service`.

## 9. Восстановление из бэкапа

Скрипт создаёт архивы вида `db-YYYYmmdd-HHMMSS.sqlite3.gz`. Для восстановления:

```bash
sudo systemctl stop cleaning-bot.service
sudo -iu cleaningbot
cd /opt/cleaning-bot
gzip -dc /opt/cleaning-bot/backups/db-20240101-220000.sqlite3.gz > /opt/cleaning-bot/data/db.sqlite3
sudo systemctl start cleaning-bot.service
```

## 10. Мониторинг и обслуживание

- Настройте `journalctl` ротацию (по умолчанию systemd управляет журналами автоматически).
- Добавьте внешние метрики/алёртинг (например, Healthchecks.io для проверки, что напоминания отправляются ежедневно).
- Регулярно проверяйте размер SQLite и очищайте старые бэкапы.

Следуя шагам выше, вы получите воспроизводимый деплой бота на одной виртуальной машине с автоматическим резервным копированием базы данных.
