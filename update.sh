#!/bin/bash

echo ">>> Остановка бота (если запущен в screen 'discord_alice')..."
screen -S discord_alice -X quit

echo ">>> Загрузка обновлений из Git..."
git pull origin master

echo ">>> Установка/обновление зависимостей..."

./venv/bin/pip install -r requirements.txt

echo ">>> Запуск бота в новом сеансе screen 'discord_alice'..."

screen -dmS discord_alice bash -c 'source venv/bin/activate && python3 bot.py'

echo "✅ Готово! Бот должен быть запущен в фоновом режиме."
echo "Используйте 'screen -r discord_alice' для просмотра логов."