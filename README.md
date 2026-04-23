Для обновления бота:

1. Перейти в папку

cd ~/discord_alice

2. Обновить только код

./update.sh

3. Если изменился requirements.txt, обновить код и синхронизировать зафиксированные зависимости

./update.sh --sync-deps

Посмотреть логи:

screen -r discord_alice

Отсоединиться от сессии:

Нажмите Ctrl+A, затем D (detach)

Скачать логи:

scp root@IP:~/discord_alice/api_logs.jsonl .
