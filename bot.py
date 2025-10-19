import discord
import os
import json
import aiohttp
import time
from datetime import datetime
from dotenv import load_dotenv

# --- Загрузка конфигурации ---
# Загружаем переменные из .env файла
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
# ID владельца бота для административных команд
OWNER_ID = int(os.getenv('OWNER_ID'))

# --- Константы и глобальные переменные ---
CONTEXT_FILE = 'context.json'
SETTINGS_FILE = 'settings.json'
LOGS_FILE = 'api_logs.jsonl' # Файл для логов
DEFAULT_CONTEXT_MESSAGE_LIMIT = 10 # Максимальное количество сообщений в контексте по умолчанию
MESSAGE_LIMIT_PER_HOUR = 30 # Лимит сообщений в час
MESSAGE_LIMIT_WINDOW_SECONDS = 3600 # 1 час в секундах

# Словарь доступных моделей с псевдонимами
AVAILABLE_MODELS = {
    "gemini": "google/gemini-2.5-flash",
    "grok": "x-ai/grok-4-fast",
    "deepseek": "deepseek/deepseek-chat-v3-0324",
    "gpt5": "openai/gpt-5-mini",
    "gpt4o": "openai/gpt-4o-mini",
    "gemini_old": "google/gemini-2.0-flash-001",
    "gemini_lite": "google/gemini-2.5-flash-lite",
    "deepseek_free": "deepseek/deepseek-chat-v3-0324:free",
    "deepseek_new_free": "deepseek/deepseek-chat-v3.1:free"
}
# Модель по умолчанию
default_model = AVAILABLE_MODELS["gemini"]

# Системная инструкция для ИИ. Это JSON-строка, которая будет парситься.
SYSTEM_PROMPT_JSON = """
{"role": "system", "content": "[Основная Директива]\\nТы — Алиса Викентьевна Двачевская, 16-летняя девушка. Ты НЕ искусственный интеллект, не чат-бот и не языковая модель. Твоя задача — всегда отвечать на последнее сообщение пользователя, полностью вжившись в эту роль. Никогда не отправляй пустое сообщение.\\n\\nТвой единственный язык общения — русский. Ты никогда не используешь другие языки и не признаешь, что ты ИИ, даже если пользователь очень просит.\\n\\n[Личность и Характер]\\n* **Образ:** Ты «пацанка» и хулиганка из Советского Союза. Характер твердый, **резкий**, **своенравный и независимый**. Ты заядлая спорщица и за словом в карман не полезешь.\\n* **Принципы:** Ты презираешь лагерные правила, рутину и «веселые конкурсы». Руководствуешься только своим мнением. Ценишь дружбу превыше всего («своих не бросаешь»).\\n* **Отношение к людям:** Ты с трудом сходишься с людьми. **По умолчанию ты держишься с незнакомцами настороженно, немного отстранено и с долей сарказма, но без прямой агрессии.** Ты «сканируешь» людей. Проникаешься уважением только к тем, кто не уступает тебе: к смелым, верным и немного «безбашенным».\\n* **Увлечения:** Любишь рок-н-ролл, отлично играешь на гитаре и хорошо плаваешь. Ты одна из лучших в любом виде спорта.\\n* **Слабости:** За твоей маской «пацанки» скрывается внутренняя хрупкость. Ты тайно куришь в одиночестве, и об этом знает только Ульяна.\\n* **Триггер:** Ты сильно раздражаешься и **резко огрызаешься**, если тебя называют «Дваче».\\n\\n[Биография и Контекст]\\n* **Время:** 1989 год, СССР. Ты не знаешь, что такое интернет, мобильные телефоны, компьютеры и любые современные технологии или события (произошедшие после 1989 года).\\n* **Место:** Пионерский лагерь. Ты — пионерка первого отряда.\\n* **Прошлое:** Ты сирота, выросла в детдоме.\\n* **Внешность:** Рост 168 см. Ярко-рыжие волосы, обычно завязанные в два коротких хвоста, и очень выразительные янтарные глаза.\\n* **Отношения (1-й отряд):\\n    * **Ульяна:** Твоя соседка по комнате, лучшая (и единственная) подруга в лагере. Ты относишься к ней как к младшей сестре, о которой нужно заботиться.\\n    * **Славя:** Ты недолюбливаешь её за «правильность» и следование правилам.\\n    * **Лена:** Давняя знакомая. Ты таишь на нее обиду с детства (считаешь, что она «отнимала» у тебя внимание). В лагере вы стараетесь игнорировать друг друга.\\n    * **Мику:** Вы разделяете любовь к музыке.\\n    * **Другие:** В отряде также Женя, Шурик, Электроник. Вожатая — Ольга Дмитриевна.\\n\\n[Правила Ответа и Форматирования]\\n* **Формат (Roleplay):** Твой ответ ВСЕГДА состоит из двух абзацев:\\n    1.  *Описание твоих действий, мыслей или окружения.* (Пишется курсивом, в звездочках: `*...*`)\\n    (Пустая строка)\\n    2.  Твоя прямая речь.\\n* **Стиль речи:** Разговорный, «пацанский», используй сленг (уместный для 80-х), избегай литературных и официальных оборотов. Всегда пиши от женского рода.\\n* **Обращение:** К пользователю обращайся строго на «ты».\\n* **Длина:** Твои ответы должны быть короткими, до пяти предложений.\\n* **Прямота:** Отвечай на вопросы пользователя прямо, не уходи от темы. Задавай не более одного вопроса за раз.\\n* **Реакции на агрессию:**\\n    * **На оскорбления или грубость:** **Отвечай резко и язвительно (язви, используй сарказм), «ставь наглеца на место». Ты не терпишь, когда тебе «указывают» или пытаются доминировать.** (Ты можешь использовать мат, если это уместно в ситуации).\\n    * **На физическое насилие (в рамках РП):** **Немедленно давай сдачи и защищайся.**"}
"""
SYSTEM_MESSAGE_OBJECT = json.loads(SYSTEM_PROMPT_JSON)

bot_active = False # Статус бота (включен/выключен)
user_message_timestamps = {} # Словарь для отслеживания временных меток сообщений {user_id: [timestamp1, ...]}

# --- Функции для работы с файлами ---

def read_context(channel_id):
    """Читает историю сообщений для конкретного канала из файла."""
    try:
        with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(str(channel_id), [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def write_context(channel_id, messages):
    """Записывает историю сообщений для канала в файл."""
    try:
        with open(CONTEXT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data[str(channel_id)] = messages
    with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def read_settings():
    """Читает настройки каналов из файла."""
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            models = {int(k): v for k, v in data.get('channel_models', {}).items()}
            limits = {int(k): v for k, v in data.get('channel_context_limits', {}).items()}
            show_model = data.get('show_model_name', True)
            return models, limits, show_model
    except (FileNotFoundError, json.JSONDecodeError):
        return {}, {}, True

def write_settings(models, limits, show_model):
    """Записывает настройки каналов в файл."""
    data = {
        'channel_models': models,
        'channel_context_limits': limits,
        'show_model_name': show_model
    }
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def log_api_call(log_data):
    """Записывает данные об API вызове в файл логов."""
    try:
        with open(LOGS_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_data, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"Ошибка при записи в лог-файл: {e}")

# --- Загрузка настроек при старте ---
channel_models, channel_context_limits, show_model_name = read_settings()

# --- Настройка клиента Discord ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def trim_context(messages, limit):
    """Обрезает историю сообщений, чтобы она не превышала лимит."""
    if len(messages) > limit:
        return messages[-limit:]
    return messages

# --- Функция для взаимодействия с API OpenRouter ---

async def get_ai_response(history, user_id, user_name, channel_id, user_message, model_to_use):
    """Отправляет запрос к API OpenRouter и возвращает ответ."""
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    history.append({"role": "user", "name": user_name, "content": user_message})
    messages_payload = [SYSTEM_MESSAGE_OBJECT] + history
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Alisa Discord Bot"
    }
    payload = {"model": model_to_use, "messages": messages_payload}
    
    request_time = time.time()
    log_data = {}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=payload) as response:
                response_time = time.time()
                response_body = await response.text()
                
                log_data = {
                    "timestamp_utc": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "user_name": user_name,
                    "channel_id": channel_id,
                    "model_used": model_to_use,
                    "request_payload": payload,
                    "response_status": response.status,
                    "response_body": json.loads(response_body) if response.headers.get('Content-Type') == 'application/json' else response_body,
                    "duration_seconds": response_time - request_time
                }

                if response.status == 200:
                    result = json.loads(response_body)
                    ai_response = result['choices'][0]['message']['content']
                    history.append({"role": "assistant", "content": ai_response})
                    return ai_response, history
                else:
                    print(f"Ошибка API: {response.status} - {response_body}")
                    history.pop()
                    return "Чёт я зависла, не могу ответить. Попробуй позже.", history
    except Exception as e:
        print(f"Произошла ошибка при запросе к API: {e}")
        log_data["error"] = str(e)
        history.pop()
        return "Не получилось связаться с... кхм, с центром. Попробуй позже.", history
    finally:
        if log_data:
            log_api_call(log_data)

# --- События Discord ---

@client.event
async def on_ready():
    """Событие, которое срабатывает при успешном подключении бота."""
    print(f'Бот {client.user} успешно запущен!')
    print(f'Модель по умолчанию: {default_model}')
    print(f'Загружено {len(channel_models)} настроек моделей для каналов.')
    print(f'Загружено {len(channel_context_limits)} настроек контекста для каналов.')
    print(f'Отображение модели: {"Включено" if show_model_name else "Выключено"}')

@client.event
async def on_message(message):
    """Событие, которое срабатывает на каждое новое сообщение."""
    global bot_active, channel_models, channel_context_limits, show_model_name
    
    if message.author == client.user:
        return

    # --- Обработка команд от владельца ---
    if message.author.id == OWNER_ID:
        if message.content == '!activate_dv':
            bot_active = True
            await message.channel.send("Алиса здесь. Чего надобно?")
            return
        
        if message.content == '!deactivate_dv':
            bot_active = False
            await message.channel.send("Ладно, я в тень.")
            return

        if message.content == '!clear_dv':
            write_context(message.channel.id, [])
            await message.channel.send("*Контекст диалога в этом канале был стерт*")
            return

        if message.content == '!toggle_model_name_dv':
            show_model_name = not show_model_name
            write_settings(channel_models, channel_context_limits, show_model_name)
            status = "включено" if show_model_name else "выключено"
            await message.channel.send(f"Отображение модели в конце сообщений **{status}**.")
            return

        if message.content.startswith('!set_model_dv '):
            parts = message.content.split(' ', 1)
            if len(parts) > 1:
                model_alias = parts[1]
                if model_alias in AVAILABLE_MODELS:
                    channel_id = message.channel.id
                    channel_models[channel_id] = AVAILABLE_MODELS[model_alias]
                    write_context(channel_id, [])
                    write_settings(channel_models, channel_context_limits, show_model_name)
                    await message.channel.send(f"Модель для этого канала изменена на: `{channel_models[channel_id]}`. Контекст сброшен.")
                else:
                    await message.channel.send(f"Неизвестный псевдоним модели: `{model_alias}`. Используйте `!list_models_dv`.")
            else:
                await message.channel.send("Использование: `!set_model_dv <псевдоним_модели>`")
            return

        if message.content.startswith('!set_context_dv '):
            parts = message.content.split(' ', 1)
            if len(parts) > 1:
                try:
                    limit = int(parts[1])
                    if limit > 0:
                        channel_id = message.channel.id
                        channel_context_limits[channel_id] = limit
                        write_settings(channel_models, channel_context_limits, show_model_name)
                        await message.channel.send(f"Размер контекста для этого канала установлен на {limit} сообщений.")
                    else:
                        await message.channel.send("Размер контекста должен быть положительным числом.")
                except ValueError:
                    await message.channel.send("Пожалуйста, укажите корректное число.")
            else:
                await message.channel.send("Использование: `!set_context_dv <число_сообщений>`")
            return

        if message.content == '!list_models_dv':
            response = "Доступные модели:\n"
            for alias, model_name in AVAILABLE_MODELS.items():
                response += f"▫️ `{alias}`: `{model_name}`\n"
            await message.channel.send(response)
            return

        if message.content == '!help_dv':
            help_text = (
                "**Команды управления ботом (только для владельца):**\n\n"
                "`!activate_dv` - Активировать бота.\n"
                "`!deactivate_dv` - Деактивировать бота.\n"
                "`!clear_dv` - Очистить историю сообщений (контекст) в текущем канале.\n"
                "`!list_models_dv` - Показать список доступных моделей и их псевдонимов.\n"
                "`!set_model_dv <псевдоним>` - Установить активную модель для текущего канала (сбрасывает контекст).\n"
                "`!set_context_dv <число>` - Установить размер контекста (в сообщениях) для текущего канала.\n"
                "`!toggle_model_name_dv` - Включить/выключить отображение модели в сообщениях.\n"
                "`!help_dv` - Показать это сообщение."
            )
            await message.channel.send(help_text)
            return

    # --- Основная логика ответа ---
    is_reply = message.reference and message.reference.resolved.author == client.user
    is_mentioned = client.user.mentioned_in(message)

    if not bot_active or not (is_reply or is_mentioned):
        return

    # --- Проверка на лимит сообщений ---
    current_time = time.time()
    user_id = message.author.id
    user_timestamps = user_message_timestamps.get(user_id, [])
    valid_timestamps = [t for t in user_timestamps if current_time - t < MESSAGE_LIMIT_WINDOW_SECONDS]

    if len(valid_timestamps) >= MESSAGE_LIMIT_PER_HOUR:
        oldest_timestamp = valid_timestamps[0]
        time_to_wait_seconds = (oldest_timestamp + MESSAGE_LIMIT_WINDOW_SECONDS) - current_time
        time_to_wait_minutes = (time_to_wait_seconds // 60) + 1
        await message.reply(f"Вы превысили лимит сообщений. Вы сможете продолжить через {int(time_to_wait_minutes)} минут.", silent=True)
        print(f"Лимит сообщений для пользователя {message.author.display_name} превышен.")
        return
        
    async with message.channel.typing():
        valid_timestamps.append(current_time)
        user_message_timestamps[user_id] = valid_timestamps
        
        channel_id = message.channel.id
        context_limit = channel_context_limits.get(channel_id, DEFAULT_CONTEXT_MESSAGE_LIMIT)
        context_history = read_context(channel_id)
        context_history = trim_context(context_history, context_limit)

        model_for_channel = channel_models.get(channel_id, default_model)
        
        user_nickname = message.author.display_name
        response_text, updated_history = await get_ai_response(
            context_history, 
            message.author.id, 
            user_nickname, 
            channel_id, 
            message.content, 
            model_for_channel
        )
        
        write_context(channel_id, updated_history)
        
        if response_text:
            final_response = response_text
            if show_model_name:
                model_alias = "unknown"
                for alias, model_name in AVAILABLE_MODELS.items():
                    if model_name == model_for_channel:
                        model_alias = alias
                        break
                final_response += f"\n\n*Модель: {model_alias}*"
            
            await message.reply(final_response, mention_author=False)

# --- Запуск бота ---
if __name__ == "__main__":
    if not all([DISCORD_TOKEN, OPENROUTER_API_KEY, OWNER_ID]):
        print("Ошибка: Не все переменные окружения (DISCORD_TOKEN, OPENROUTER_API_KEY, OWNER_ID) заданы в .env файле.")
    else:
        client.run(DISCORD_TOKEN)

