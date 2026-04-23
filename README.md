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

scp alicebot@IP:~/discord_alice/api_logs.jsonl .

GUI для Windows 10:

1. Установить локальную зависимость для GUI-менеджера

python -m pip install -r manager_requirements.txt

2. Запустить локальный менеджер

python bot_manager_gui.py

Что умеет менеджер:

- проверять SSH-подключение к серверу;
- показывать статус git и screen-сессии `discord_alice`;
- запускать, останавливать и перезапускать бота;
- выполнять `./update.sh` и `./update.sh --sync-deps`;
- показывать последние строки `api_logs.jsonl` и скачивать файл логов на локальную машину.
