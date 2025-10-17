echo ">>> Остановка бота (если запущен в screen 'discord_alice')..."
screen -S discord_alice -X quit # Принудительно завершает сеанс screen с этим име>

echo ">>> Загрузка обновлений из Git..."
git pull origin master

echo ">>> Установка/обновление зависимостей..."
source venv/bin/activate
pip install -r requirements.txt
deactivate

echo ">>> Запуск бота в новом сеансе screen 'discord_alice'..."
screen -dmS discord_alice bash -c 'source venv/bin/activate && python discord_alice>

echo "✅ Готово! Бот должен быть запущен в фоновом режиме."
echo "Используйте 'screen -r discord_alice' для просмотра логов."