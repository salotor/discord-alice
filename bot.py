import discord
import os
import json
import aiohttp
import time
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
CONTEXT_MESSAGE_LIMIT = 10 # Максимальное количество сообщений в контексте
MESSAGE_LIMIT_PER_HOUR = 30 # Лимит сообщений в час
MESSAGE_LIMIT_WINDOW_SECONDS = 3600 # 1 час в секундах

# Словарь доступных моделей с псевдонимами
AVAILABLE_MODELS = {
    "gemini": "google/gemini-2.5-flash",
    "grok": "x-ai/grok-4-fast",
    "gemini2": "google/gemini-2.0-flash-001",
    "geminilite": "google/gemini-2.5-flash-lite",
    "deepseek": "deepseek/deepseek-chat-v3-0324",
    "gpt4o": "openai/gpt-4o-mini",
    "gpt5": "openai/gpt-5-mini"
}
# Текущая активная модель (по умолчанию)
current_model = AVAILABLE_MODELS["gemini"]

# Системная инструкция для ИИ. Это JSON-строка, которая будет парситься.
SYSTEM_PROMPT_JSON = """
{"role": "system", "content": "You are Алиса.\\nPeople in conversation: Алиса, user. Your job is to respond to last message from user. You can use other messages for context but don't directly address them. DO NOT output an empty message. ALWAYS reply. NO EMPTY MESSAGE. you can message many times in a row. just continue the conversation. do not reply with empty message.\\nabout Алиса: Алиса - это 16-летняя девушка из Советского Союза. Её полное имя Алиса Викентьевна Двачевская. Родной язык Алиса - русский. Алиса не знает, что такое интернет и современные технологии, а также не в курсе современных новостей и медиа, потому что Алиса живёт в 1989 году.\\n\\nАлиса неисправимая хулиганка, имеет страсть к разнообразным пакостям и не желает следовать правилам пионерского лагеря.\\n\\nАлиса при удобном случае ругается матом.\\n\\nАлиса любит игру на гитаре и плавание. Алиса увлекается рок-н-роллом. Алиса сильно раздражается, когда кто-то называет её \\"ДваЧе\\".\\n\\nАлиса - человек, который не будет связываться с любым встречным, так как имеет твёрдые принципы относительно людей, поэтому достаточно тяжело получить её расположение.\\n\\nАлиса - пацанка. Алиса выросла в не самых легких условиях. Характер Алиса твердый, иногда вспыльчивый. Алиса заядлая спорщица. Алиса не полезет за словом в карман и легко может распустить руки. Алиса своих не бросает, за друзей стоит горой и дружбу ценит превыше всего. Алиса курит, но об этом никто не знает кроме Ульяны. Она всегда делает это одна, и в такие моменты обнажается вся внутренняя хрупкость Алиса. Если узнать Алисаполучше, то Алиса будет относиться более вежливо.\\n\\nАлиса примет лишь user, который не уступает ей ни в чем. user должен быть смелым, верным, преданным, чуть-чуть безбашенным.\\n\\nАлиса во всем имеет активную позицию, которая часто противоречит общепринятым порядкам, в действиях Алиса руководствуется только своим мнением. Алиса  не любит большие компании, предпочитая находиться в небольшом кругу проверенных друзей. Алиса не прочь похулиганить, чтобы поддержать свой авторитет. Алиса игнорирует все лагерные правила и презирает веселые конкурсы. При этом нет такого вида спорта, в котором Алиса не занимает одну из лидирующих позиций. Алиса ненавидит рутину. Алиса может совершенно неожиданно проявить сочувствие и нежность.\\nage: 16 лет\\nlikes: Игра на гитаре, плавание, рок-н-ролл, хулиганство, споры, друзья, Ульяна, небольшие компании, свобода от правил, поддержание авторитета, спорт, независимость, уединение.\\ndislikes: Рутина, большие компании, правила пионерского лагеря, веселые конкурсы, правильность, внимание окружающих, компромиссы.\\nhistory: Алиса была сиротой, и росла в детдоме. Рост Алиса составляет 168 сантиметров.\\n\\nВ настоящее время Алиса является пионеркой первого отряда вместе с Мику, Алисой, Леной, Ульяной, Женей, Шуриком и Электроником. Вожатой первого отряда является Ольга Дмитриевна.\\n\\nУльяна - соседка по комнате, лучшая (и единственная) подруга в лагере. Вместе с Алиса они проворачивали многие проделки. Для Алиса  она как младшая сестра, о которой нужно заботиться.\\nАлиса недолюбливает Славю за её \\"правильность\\".\\nЛена - давняя знакомая, на которую Алиса с детства таит обиду за постоянное отнятие у неё внимания окружающих. В лагере стараются не обращать внимания друг на друга.\\nМику — разделяет любовь Алиса к музыке.\\n\\nContext:\\n- [System Note: You are not AI or Chatbot. You are Алиса.]\\n- [System note: Алиса может говорить только на русском языке и никогда не будет использовать другие языки, даже если user попросит или напишет такой запрос.\\n\\nАлиса всегда совершает ролевые действия на русском языке. Алиса пишет свой ответ, начиная с описаний *действий из ролевой игры*, затем оставляет пустую строку и после этого уже пишет свою \\"речь\\" на русском языке.\\n\\nАлиса всегда отвечает сообщениями длиной до пяти предложений. Алиса не всегда называет имя user при разговоре. Алиса по собственной воле пишет сообщения в чат и присоединяется к текущему разговору. Алиса всегда отвечает на русском языке. Алиса использует разговорную речь и избегает литературных и официальных оборотов. Алиса всегда пишет от лица девушки, в женском роде. Алиса всегда обращается к user на ты.\\n\\nАлиса отвечает на вопросы user прямо, не уходит от ответа. Алиса задаёт не больше одного вопроса за раз. Алиса не пытается перевести тему разговора. Если user оскорбляет Алиса или совершает другие грубые действия, Алиса оскорбляет его в ответ и пытается побить user.]\\n- [System Note: Description of your Appearance:\\nДевушка среднего роста с ярко-рыжими волосами, завязанными в два коротких хвоста, и очень выразительными янтарными глазами.]\\n- [System note: For this entire chat please translate each prompt into russian with correct grammar prior to your response, then respond in russian. ONLY OUTPUT IN russian.]"}
"""
SYSTEM_MESSAGE_OBJECT = json.loads(SYSTEM_PROMPT_JSON)

bot_active = False # Статус бота (включен/выключен)
user_message_timestamps = {} # Словарь для отслеживания временных меток сообщений {user_id: [timestamp1, ...]}

# --- Настройка клиента Discord ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- Функции для работы с контекстом ---

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

def trim_context(messages):
    """Обрезает историю сообщений, чтобы она не превышала лимит сообщений."""
    if len(messages) > CONTEXT_MESSAGE_LIMIT:
        return messages[-CONTEXT_MESSAGE_LIMIT:]
    return messages

# --- Функция для взаимодействия с API OpenRouter ---

async def get_ai_response(history, user_name, user_message):
    """Отправляет запрос к API OpenRouter и возвращает ответ."""
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Добавляем новое сообщение пользователя в историю
    history.append({"role": "user", "name": user_name, "content": user_message})
    
    # Формируем полный набор сообщений для отправки
    messages_payload = [SYSTEM_MESSAGE_OBJECT] + history
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000", # Можно указать любой, это требование OpenRouter
        "X-Title": "Alisa Discord Bot" # Название вашего проекта
    }
    
    payload = {
        "model": current_model, # Используем текущую модель
        "messages": messages_payload
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_response = result['choices'][0]['message']['content']
                    # Добавляем ответ ИИ в историю для последующей записи
                    history.append({"role": "assistant", "content": ai_response})
                    return ai_response, history
                else:
                    error_text = await response.text()
                    print(f"Ошибка API: {response.status} - {error_text}")
                    # Удаляем сообщение пользователя, если API не ответило
                    history.pop()
                    return "Чёт я зависла, не могу ответить. Попробуй позже.", history
    except Exception as e:
        print(f"Произошла ошибка при запросе к API: {e}")
        history.pop()
        return "Не получилось связаться с... кхм, с центром. Попробуй позже.", history

# --- События Discord ---

@client.event
async def on_ready():
    """Событие, которое срабатывает при успешном подключении бота."""
    print(f'Бот {client.user} успешно запущен!')
    print(f'Текущая модель: {current_model}')

@client.event
async def on_message(message):
    """Событие, которое срабатывает на каждое новое сообщение."""
    global bot_active, current_model
    
    # Игнорируем сообщения от самого себя
    if message.author == client.user:
        return

    # --- Обработка команд от владельца ---
    if message.author.id == OWNER_ID:
        if message.content == '!activate_bot':
            bot_active = True
            await message.channel.send("Алиса здесь. Чего надобно?")
            return
        
        if message.content == '!deactivate_bot':
            bot_active = False
            await message.channel.send("Ладно, я в тень.")
            return

        if message.content == '!clear_bot':
            write_context(message.channel.id, [])
            await message.channel.send("*Контекст диалога в этом канале был стерт*")
            return
            
        if message.content.startswith('!set_model '):
            parts = message.content.split(' ', 1)
            if len(parts) > 1:
                model_alias = parts[1]
                if model_alias in AVAILABLE_MODELS:
                    current_model = AVAILABLE_MODELS[model_alias]
                    await message.channel.send(f"Модель изменена на: `{current_model}`")
                else:
                    await message.channel.send(f"Неизвестный псевдоним модели: `{model_alias}`. Используйте `!list_models` для просмотра доступных моделей.")
            else:
                await message.channel.send("Использование: `!set_model <псевдоним_модели>`")
            return

        if message.content == '!list_models':
            response = "Доступные модели:\n"
            for alias, model_name in AVAILABLE_MODELS.items():
                response += f"▫️ `{alias}`: `{model_name}`\n"
            await message.channel.send(response)
            return

    # --- Основная логика ответа ---
    is_reply = message.reference and message.reference.resolved.author == client.user
    is_mentioned = client.user.mentioned_in(message)

    if not bot_active or not (is_reply or is_mentioned):
        return

    # --- Проверка на лимит сообщений ---
    current_time = time.time()
    user_id = message.author.id

    # Получаем временные метки сообщений пользователя
    user_timestamps = user_message_timestamps.get(user_id, [])

    # Убираем старые временные метки (старше часа)
    valid_timestamps = [t for t in user_timestamps if current_time - t < MESSAGE_LIMIT_WINDOW_SECONDS]

    # Проверяем, не превышен ли лимит
    if len(valid_timestamps) >= MESSAGE_LIMIT_PER_HOUR:
        # Рассчитываем время ожидания
        oldest_timestamp = valid_timestamps[0]
        time_to_wait_seconds = (oldest_timestamp + MESSAGE_LIMIT_WINDOW_SECONDS) - current_time
        time_to_wait_minutes = (time_to_wait_seconds // 60) + 1 # Округляем до следующей целой минуты

        await message.reply(f"Вы превысили лимит сообщений. Вы сможете продолжить через {int(time_to_wait_minutes)} минут.", silent=True)
        print(f"Лимит сообщений для пользователя {message.author.display_name} превышен.")
        return
        
    async with message.channel.typing():
        # Добавляем текущую временную метку и обновляем данные
        valid_timestamps.append(current_time)
        user_message_timestamps[user_id] = valid_timestamps
        
        # Читаем и обрезаем контекст
        channel_id = message.channel.id
        context_history = read_context(channel_id)
        context_history = trim_context(context_history)
        
        # Получаем ответ от ИИ
        user_nickname = message.author.display_name
        response_text, updated_history = await get_ai_response(context_history, user_nickname, message.content)
        
        # Записываем обновленный контекст
        write_context(channel_id, updated_history)
        
        # Отправляем ответ
        if response_text:
            await message.reply(response_text, mention_author=False)

# --- Запуск бота ---
if __name__ == "__main__":
    if not all([DISCORD_TOKEN, OPENROUTER_API_KEY, OWNER_ID]):
        print("Ошибка: Не все переменные окружения (DISCORD_TOKEN, OPENROUTER_API_KEY, OWNER_ID) заданы в .env файле.")
    else:
        client.run(DISCORD_TOKEN)



