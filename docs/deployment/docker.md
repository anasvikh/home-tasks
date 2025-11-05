# Развёртывание через Docker и GitHub Actions

Эта инструкция описывает, как запустить бота на виртуальной машине в Docker‑контейнере и автоматизировать публикацию обновлений через GitHub Actions. Сценарий покрывает подготовку сервера, выпуск образов, обновление контейнера и резервное копирование базы SQLite.

## 1. Подготовка виртуальной машины

1. Установите Docker и плагин Compose:
   ```bash
   sudo apt-get update
   sudo apt-get install -y ca-certificates curl gnupg lsb-release
   sudo install -m 0755 -d /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
   echo \
     "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release && echo \"$ID\") \
     $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
   ```
2. Добавьте пользователя в группу `docker`, чтобы запускать команды без `sudo`:
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```
3. Создайте каталог для приложения, например `/opt/home-tasks`. В нём будут храниться файлы конфигурации (`.env`),
   каталоги с данными (`storage/`) и резервными копиями (`backups/`). Сам образ приложения мы будем получать из GHCR,
   поэтому код проекта на сервере держать не требуется.

## 2. Подготовка конфигурации

> В отличие от systemd‑развёртывания нам не нужно держать исходники на сервере: GitHub Actions будет загружать только
> необходимые файлы (`deploy/docker-compose.yml`, скрипты и пр.) перед запуском. На сервере должны лежать лишь
> пользовательские данные и секреты.

1. Создайте файл `/opt/home-tasks/.env` и заполните переменные окружения. Ориентируйтесь на
   [`cleaning_bot/.env.example`](../../cleaning_bot/.env.example) — необходимые переменные те же (токен бота, строка
   подключения к базе и т. п.).
2. Обновите конфигурацию `cleaning_bot/config.yaml` и связанные JSON‑файлы в репозитории, чтобы в контейнер попадали
   нужные значения (боевые `group_chat_id`, `admin_ids`, список пользователей и задач). Эти изменения стоит хранить в
   git, чтобы ими управляла CI/CD. После коммита GitHub Actions доставит новые версии файлов на сервер.
3. На сервере создайте каталоги для данных и бэкапов (они будут смонтированы в контейнер):
   ```bash
   mkdir -p /opt/home-tasks/storage /opt/home-tasks/backups
   ```

## 3. Локальная проверка в Docker

1. Соберите образ и поднимите контейнер в фоне:
   ```bash
   IMAGE=home-tasks:dev docker compose -f deploy/docker-compose.yml up -d --build
   ```
2. Проверьте логи:
   ```bash
   docker compose -f deploy/docker-compose.yml logs -f
   ```
3. Остановите контейнер после проверки:
   ```bash
   docker compose -f deploy/docker-compose.yml down
   ```

## 4. Настройка GitHub Actions для сборки образа

1. Создайте secrets репозитория:
   - `DEPLOY_HOST` — IP или доменное имя сервера.
   - `DEPLOY_USER` — пользователь SSH.
   - `DEPLOY_PATH` — путь до каталога с проектом (`/opt/home-tasks`).
   - `SSH_PRIVATE_KEY` — приватный ключ для доступа по SSH.
2. Дайте workflow право пушить образы в GitHub Container Registry (GHCR). В настройках репозитория включите `Packages: write` для `GITHUB_TOKEN`.
3. На сервере выполните вход в GHCR (одноразово), чтобы `docker compose pull` имел доступ:
   ```bash
   echo <GHCR_PAT> | docker login ghcr.io -u <ВАШ_ЛОГИН> --password-stdin
   ```
   Можно использовать классический PAT с правами `write:packages`.

Workflow `.github/workflows/deploy.yml` выполняет три шага:
1. Собирает образ `ghcr.io/<OWNER>/home-tasks:<commit_sha>`.
2. При пуше в `main` дополнительно помечает образ тегом `latest`.
3. Копирует актуальные файлы из каталога `deploy/` на сервер, после чего через SSH вызывает `docker compose pull` и
   `docker compose up -d`, пробрасывая переменную `IMAGE` с новым тегом.

## 5. Первое развёртывание на сервере

GitHub Actions выкладывает compose‑файл и скрипты в каталог `${DEPLOY_PATH}` на сервере. После первой успешной сборки в
`main` на сервере появятся:

- `deploy/docker-compose.yml` — описание контейнера.
- `deploy/scripts/backup_sqlite.sh` — скрипт резервного копирования.

Чтобы запустить сервис впервые:

1. Убедитесь, что `.env`, `storage/` и `backups/` созданы (см. шаг 2).
2. Выполните деплой вручную (или дождитесь его из GitHub Actions):
   ```bash
   IMAGE=ghcr.io/<OWNER>/home-tasks:latest docker compose \
     -f deploy/docker-compose.yml \
     --env-file .env \
     up -d
   ```
3. Убедитесь, что в `storage/db.sqlite3` появились таблицы, а бот отвечает в Telegram.
4. Для просмотра логов используйте:
   ```bash
   docker compose -f deploy/docker-compose.yml --env-file .env logs -f
   ```

## 6. Резервное копирование базы данных

1. Скрипт `deploy/scripts/backup_sqlite.sh` создаёт снапшот базы внутри контейнера и сохраняет его в каталоге `backups`.
2. Добавьте cron‑задачу на сервере, например ежедневный бэкап в 03:00 с хранением 14 дней:
   ```bash
   crontab -e
   0 3 * * * /opt/home-tasks/deploy/scripts/backup_sqlite.sh >> /opt/home-tasks/backups/backup.log 2>&1
   ```
3. Для внепланового восстановления:
   ```bash
   docker compose -f deploy/docker-compose.yml down
   cp backups/assignments-<ДАТА>.db storage/db.sqlite3
   IMAGE=ghcr.io/<OWNER>/home-tasks:latest docker compose -f deploy/docker-compose.yml up -d
   ```

## 7. Типовой цикл обновления

1. Вливайте изменения в ветку `main`.
2. GitHub Actions автоматически соберёт и опубликует образ, затем выполнит деплой на сервер.
3. Контейнер перезапустится с новой версией, сохранив данные в `storage/`.
4. Проверьте логи и статус бота, убедитесь, что уведомления отправляются корректно.

## 8. Отладка и обслуживание

- `docker compose ps` — статус контейнеров.
- `docker compose logs -f` — последние логи бота.
- `docker compose exec cleaning-bot python -m cleaning_bot.bot` — интерактивный запуск внутри контейнера.
- Перед изменениями конфигурации создавайте бэкап.
- Регулярно очищайте старые образы: `docker image prune -f`.

Следуя этим шагам, вы получите предсказуемый процесс выпуска и резервирования данных с минимальными ручными действиями на сервере.
