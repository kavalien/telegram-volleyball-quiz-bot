import os
import random
import logging
import psycopg2

from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    PicklePersistence
)

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------
# Состояния ConversationHandler
# -------------------------
MAIN_MENU, ASK_NAME, CHOOSE_CATEGORY, ASK_QUESTION = range(4)

# -------------------------
# Глобальные переменные подключения к PostgreSQL
# -------------------------
conn = None
cursor = None

def init_db():
    """
    Устанавливаем соединение с PostgreSQL (переменные окружения берём из Railway),
    создаём таблицу scoreboard, если её нет.
    """
    global conn, cursor
    
    # Считываем параметры из окружения
    dbname = os.environ.get("PGDATABASE")
    user = os.environ.get("PGUSER")
    password = os.environ.get("PGPASSWORD")
    host = os.environ.get("PGHOST")
    port = os.environ.get("PGPORT", "5432")  # обычно 5432
    
    if not (dbname and user and password and host):
        logger.error("Не найдены переменные окружения PostgreSQL (PGDATABASE, PGUSER, PGPASSWORD, PGHOST)!")
        return
    
    # Подключаемся к базе
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cursor = conn.cursor()
    
    # Создадим таблицу scoreboard, если не существует
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scoreboard (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            score INT
        );
    """)
    conn.commit()
    logger.info("init_db(): Таблица scoreboard проверена/создана.")

def update_score_db(user_id, username, increment):
    """
    Увеличить счёт пользователя (user_id) на increment.
    Если user_id нет в таблице — вставляем новую строку.
    """
    global conn, cursor
    if not cursor:
        logger.error("update_score_db() вызван до init_db()!")
        return
    
    cursor.execute("SELECT score FROM scoreboard WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    if row is None:
        # Вставляем новую запись
        cursor.execute(
            "INSERT INTO scoreboard (user_id, username, score) VALUES (%s, %s, %s)",
            (user_id, username, increment)
        )
    else:
        current_score = row[0]
        new_score = current_score + increment
        cursor.execute(
            "UPDATE scoreboard SET username = %s, score = %s WHERE user_id = %s",
            (username, new_score, user_id)
        )
    conn.commit()

def get_top_players_db(limit=10):
    """
    Возвращает топ-игроков (username, score),
    отсортированных по убыванию score, максимум limit штук.
    """
    global conn, cursor
    if not cursor:
        logger.error("get_top_players_db() вызван до init_db()!")
        return []
    
    cursor.execute("SELECT username, score FROM scoreboard ORDER BY score DESC LIMIT %s", (limit,))
    rows = cursor.fetchall()  # [(username, score), ...]
    return rows

# -------------------------
# Полный список из 40 вопросов (2 категории)
# -------------------------
quiz_data = {
    "Правила волейбола \U0001F3D0": [
        {
            "question": "1. Какой размер площадки для классического волейбола?",
            "options": ["9 м x 9 м", "18 м x 9 м", "16 м x 8 м", "20 м x 10 м"],
            "answer": "18 м x 9 м",
            "explanation": "По официальным правилам FIVB длина классической площадки 18 м, ширина – 9 м."
        },
        {
            "question": "2. Сколько игроков находится на площадке в одной команде в классическом волейболе?",
            "options": ["4", "5", "6", "7"],
            "answer": "6",
            "explanation": "В классическом формате на площадке 6 человек (плюс запасные)."
        },
        {
            "question": "3. Какой максимальный вес разрешён для мяча в волейболе?",
            "options": ["250 г", "280 г", "300 г", "320 г"],
            "answer": "280 г",
            "explanation": "Официальный вес мяча должен быть 260–280 г."
        },
        {
            "question": "4. Сколько очков нужно набрать, чтобы выиграть сет в классическом волейболе?",
            "options": ["15", "21", "25", "30"],
            "answer": "25",
            "explanation": "Необходимо минимум 25 очков с разницей в 2 очка."
        },
        {
            "question": "5. Какая высота сетки для мужского классического волейбола?",
            "options": ["2.24 м", "2.35 м", "2.43 м", "2.50 м"],
            "answer": "2.43 м",
            "explanation": "Стандарт FIVB для мужчин — 2,43 м."
        },
        {
            "question": "6. Сколько тайм-аутов разрешено каждой команде в одном сете?",
            "options": ["1", "2", "3", "4"],
            "answer": "2",
            "explanation": "В каждом сете (кроме тай-брейка) — два тайм-аута по 30 секунд."
        },
        {
            "question": "7. Сколько касаний мяча разрешено одной команде до передачи через сетку?",
            "options": ["2", "3", "4", "5"],
            "answer": "3",
            "explanation": "Команда имеет право на максимум три касания (не считая блок)."
        },
        {
            "question": "8. Какой размер площадки для пляжного волейбола?",
            "options": ["8 м x 8 м", "9 м x 9 м", "16 м x 8 м", "18 м x 9 м"],
            "answer": "16 м x 8 м",
            "explanation": "Пляжная площадка 16×8 м, короче и уже классической."
        },
        {
            "question": "9. Сколько игроков в команде на площадке в пляжном волейболе?",
            "options": ["2", "3", "4", "6"],
            "answer": "2",
            "explanation": "Пляжный волейбол играют 2 на 2, без замен."
        },
        {
            "question": "10. В каком случае команде начисляется очко?",
            "options": [
                "Мяч касается пола соперника",
                "Мяч выходит за пределы от соперника",
                "Нарушение правил соперником",
                "Все вышеуказанные"
            ],
            "answer": "Все вышеуказанные",
            "explanation": "Очко за любую ошибку соперника или падение мяча на их площадку."
        },
        {
            "question": "11. Какая высота сетки в женском пляжном волейболе?",
            "options": ["2.10 м", "2.15 м", "2.24 м", "2.43 м"],
            "answer": "2.24 м",
            "explanation": "Женская сетка в пляжном волейболе — 2,24 м."
        },
        {
            "question": "12. Какой максимальный счёт может быть в сете, если разница очков не достигает двух?",
            "options": ["25", "30", "35", "Неограниченный"],
            "answer": "Неограниченный",
            "explanation": "Сет продолжается, пока одна из команд не добьётся +2 очка."
        },
        {
            "question": "13. Что означает термин «блок»?",
            "options": [
                "Удар по мячу снизу",
                "Перекрытие пути мячу возле сетки",
                "Защитный пас",
                "Ошибка при подаче"
            ],
            "answer": "Перекрытие пути мячу возле сетки",
            "explanation": "Блок — это попытка игроков передней линии остановить атаку соперника."
        },
        {
            "question": "14. Какова минимальная температура для проведения соревнований по снежному волейболу?",
            "options": ["-5 °C", "-10 °C", "-15 °C", "-20 °C"],
            "answer": "-10 °C",
            "explanation": "Часто устанавливают минимум -10 °C для безопасности."
        },
        {
            "question": "15. Сколько игроков в одной команде в снежном волейболе?",
            "options": ["2", "3", "4", "5"],
            "answer": "3",
            "explanation": "В снежном волейболе играют по три человека в каждой команде."
        },
        {
            "question": "16. Сколько сетов играют в классическом волейболе для определения победителя?",
            "options": ["3", "4", "5", "6"],
            "answer": "5",
            "explanation": "Игра до 3 выигранных сетов, максимум 5 сетов."
        },
        {
            "question": "17. Сколько длится технический перерыв в классическом волейболе?",
            "options": ["30 секунд", "60 секунд", "90 секунд", "120 секунд"],
            "answer": "60 секунд",
            "explanation": "Технические перерывы (ранее при счёте 8 и 16) по 60 секунд."
        },
        {
            "question": "18. Что происходит, если мяч касается линии площадки?",
            "options": [
                "Мяч считается в ауте",
                "Мяч считается в игре",
                "Игроки должны остановить игру",
                "Судья принимает решение"
            ],
            "answer": "Мяч считается в игре",
            "explanation": "Касание линий считается попаданием в поле."
        },
        {
            "question": "19. Каково максимальное время для подачи после свистка судьи?",
            "options": ["5 секунд", "8 секунд", "10 секунд", "12 секунд"],
            "answer": "8 секунд",
            "explanation": "Подающий имеет 8 секунд на выполнение подачи."
        },
        {
            "question": "20. Может ли либеро атаковать из передней зоны?",
            "options": [
                "Нет, никогда",
                "Да, только если мяч ниже уровня сетки",
                "Да, без ограничений",
                "Нет, но может выполнять передачи"
            ],
            "answer": "Да, только если мяч ниже уровня сетки",
            "explanation": "Либеро не может атаковать выше верхнего края сетки."
        },
    ],
    "История волейбола \U0001F4D6": [
        {
            "question": "21. Кто считается основателем волейбола?",
            "options": ["Джеймс Нейсмит", "Уильям Дж. Морган", "Пьер де Кубертен", "Джордж Фишер"],
            "answer": "Уильям Дж. Морган",
            "explanation": "Уильям Морган создал «минтонет» (1895), впоследствии волейбол."
        },
        {
            "question": "22. В каком году был изобретён волейбол?",
            "options": ["1891", "1895", "1900", "1912"],
            "answer": "1895",
            "explanation": "Именно в 1895 Морган провёл первую демонстрацию новой игры."
        },
        {
            "question": "23. Как первоначально называлась игра, придуманная Морганом?",
            "options": ["Бадминтон", "Теннибол", "Минтонет", "Сферобол"],
            "answer": "Минтонет",
            "explanation": "Изначальное название — «минтонет»."
        },
        {
            "question": "24. Кто изобрёл баскетбол, что вдохновило Моргана на создание волейбола?",
            "options": ["Джеймс Нейсмит", "Альфред Халстед", "Пьер де Кубертен", "Генри Морган"],
            "answer": "Джеймс Нейсмит",
            "explanation": "Нейсмит создал баскетбол (1891), а Морган вдохновился и придумал волейбол."
        },
        {
            "question": "25. В каком году волейбол официально вошёл в программу Олимпийских игр?",
            "options": ["1924", "1948", "1964", "1988"],
            "answer": "1964",
            "explanation": "Официально вошёл в программу в Токио-1964."
        },
        {
            "question": "26. В какой стране прошли первые Олимпийские игры, на которых был представлен волейбол?",
            "options": ["Япония", "Бразилия", "США", "Мексика"],
            "answer": "Япония",
            "explanation": "Это была Япония, Олимпиада 1964 года (Токио)."
        },
        {
            "question": "27. Какой международный орган управляет волейболом во всём мире?",
            "options": ["ФИФА (FIFA)", "ФИВБ (FIVB)", "МОК (IOC)", "ФИБА (FIBA)"],
            "answer": "ФИВБ (FIVB)",
            "explanation": "Международная федерация волейбола (FIVB) учреждена для организации турниров."
        },
        {
            "question": "28. В каком году была основана Международная федерация волейбола (FIVB)?",
            "options": ["1895", "1908", "1947", "1952"],
            "answer": "1947",
            "explanation": "FIVB создана в 1947, сразу после Второй мировой войны."
        },
        {
            "question": "29. Где находится штаб-квартира Международной федерации волейбола (FIVB)?",
            "options": ["Лозанна (Швейцария)", "Париж (Франция)", "Нью-Йорк (США)", "Монреаль (Канада)"],
            "answer": "Лозанна (Швейцария)",
            "explanation": "Многие спортивные организации располагаются в Лозанне."
        },
        {
            "question": "30. Какая страна считалась одной из ведущих по развитию волейбола в первой половине XX века?",
            "options": ["Испания", "Россия (СССР)", "Египет", "Великобритания"],
            "answer": "Россия (СССР)",
            "explanation": "СССР активно развивал волейбол и добился больших успехов."
        },
        {
            "question": "31. В каком году прошёл первый официальный чемпионат мира по волейболу среди мужчин?",
            "options": ["1949", "1952", "1956", "1960"],
            "answer": "1949",
            "explanation": "Первый ЧМ — в Праге (Чехословакия) в 1949 году."
        },
        {
            "question": "32. Когда в СССР состоялся первый чемпионат страны по волейболу среди мужчин?",
            "options": ["1923", "1933", "1938", "1947"],
            "answer": "1933",
            "explanation": "В 1933 году провели первый всесоюзный чемпионат."
        },
        {
            "question": "33. Каково было первоначальное количество игроков на площадке в самой ранней версии волейбола?",
            "options": [
                "Не было чёткого ограничения",
                "По 6 человек с каждой стороны",
                "По 9 человек с каждой стороны",
                "По 4 человека с каждой стороны"
            ],
            "answer": "Не было чёткого ограничения",
            "explanation": "Морган изначально не оговаривал точного числа игроков."
        },
        {
            "question": "34. В каком году впервые провели Кубок мира по волейболу?",
            "options": ["1959", "1965", "1969", "1977"],
            "answer": "1969",
            "explanation": "Кубок мира FIVB впервые состоялся в 1969 году."
        },
        {
            "question": "35. Какая страна является рекордсменом по количеству побед на мужских чемпионатах мира?",
            "options": ["Бразилия", "СССР / Россия", "США", "Италия"],
            "answer": "СССР / Россия",
            "explanation": "Советская/российская сборная чаще всех становилась чемпионом."
        },
        {
            "question": "36. Кто стал первым олимпийским чемпионом в мужском волейболе на Играх 1964 года?",
            "options": ["Япония", "Польша", "СССР", "США"],
            "answer": "СССР",
            "explanation": "На первом олимпийском турнире по волейболу (1964) золото у СССР."
        },
        {
            "question": "37. В каком году пляжный волейбол был впервые включён в программу Олимпийских игр?",
            "options": ["1984", "1992", "1996", "2000"],
            "answer": "1996",
            "explanation": "Пляжный волейбол дебютировал в Атланте (США) в 1996 году."
        },
        {
            "question": "38. Где прошёл первый официальный чемпионат мира по пляжному волейболу?",
            "options": ["Лос-Анджелес (США)", "Рио-де-Жанейро (Бразилия)", "Марсель (Франция)", "Майами (США)"],
            "answer": "Рио-де-Жанейро (Бразилия)",
            "explanation": "Первый ЧМ провели именно в Бразилии, одной из сильнейших в пляжном волейболе."
        },
        {
            "question": "39. В каком году состоялся первый чемпионат мира по волейболу среди женщин?",
            "options": ["1949", "1952", "1956", "1957"],
            "answer": "1952",
            "explanation": "В 1952 году в Москве прошёл первый ЧМ среди женщин."
        },
        {
            "question": "40. Когда в официальных правилах волейбола появилась позиция «либеро»?",
            "options": ["1994", "1996", "1998", "2000"],
            "answer": "1998",
            "explanation": "Позицию либеро ввели в 1998 году, чтобы усилить защиту."
        },
    ]
}

# -------------------------
# Команды /start и /cancel
# -------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — Переход в главное меню.
    """
    return await show_main_menu(update, context)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cancel — прерывание викторины (и возврат к меню).
    """
    context.user_data.clear()
    await update.message.reply_text("Викторина прервана. Возвращаемся в главное меню!")
    return await show_main_menu(update, context)

# -------------------------
# Главное меню
# -------------------------
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выводим меню с тремя кнопками:
    1) Начать викторину
    2) Лучшие игроки (топ-10)
    3) Наш магазин
    """
    keyboard = [
        ["\U0001F3AF Начать викторину"],   # 🎯
        ["\U0001F3C6 Лучшие игроки"],      # 🏆
        ["\U0001F6D2 Наш магазин"]         # 🛒
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        text="Выберите действие:",
        reply_markup=reply_markup
    )
    return MAIN_MENU

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатываем выбор пользователя в главном меню.
    """
    choice = update.message.text.strip()

    if choice == "\U0001F3AF Начать викторину":
        # Запрашиваем имя (ASK_NAME)
        await update.message.reply_text(
            "Отлично! Давайте знакомиться. Как вас зовут?",
            reply_markup=ReplyKeyboardRemove()
        )
        return ASK_NAME

    elif choice == "\U0001F3C6 Лучшие игроки":
        # Показать топ-10
        rows = get_top_players_db(limit=10)
        if not rows:
            text = "\U0001F3C6 Топ-10 игроков:\nПока никто не играл."
        else:
            text = "\U0001F3C6 Топ-10 игроков:\n"
            for i, (uname, score) in enumerate(rows, start=1):
                text += f"{i}. {uname}: {score}\n"
        await update.message.reply_text(text)
        return await show_main_menu(update, context)

    elif choice == "\U0001F6D2 Наш магазин":
        # Ссылка на канал или магазин
        await update.message.reply_text(
            "Наш магазин \U0001F6CD здесь: https://t.me/<ваш_канал_магазина>\n\nЖдём вас!",
            reply_markup=ReplyKeyboardRemove()
        )
        # Вернёмся к меню
        return await show_main_menu(update, context)

    else:
        # Непонятный ввод — вернёмся к меню
        await update.message.reply_text("Пожалуйста, выберите пункт из меню.")
        return MAIN_MENU

# -------------------------
# Логика регистрации (ASK_NAME) -> выбор категории (CHOOSE_CATEGORY)
# -------------------------
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение имени пользователя -> спрашиваем категорию.
    """
    user_id = str(update.effective_user.id)
    username_input = update.message.text.strip()

    # Обновим или создадим запись в БД (добавим 0, если нет)
    update_score_db(user_id, username_input, 0)

    context.user_data["username"] = username_input

    categories = list(quiz_data.keys())  # ["Правила волейбола 🏐", "История волейбола 📖"]
    keyboard = [[cat] for cat in categories]

    await update.message.reply_text(
        f"Приятно познакомиться, {username_input}!\n"
        "Выберите категорию викторины:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSE_CATEGORY

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text.strip()
    if category not in quiz_data:
        await update.message.reply_text("Пожалуйста, выберите категорию из списка!")
        return CHOOSE_CATEGORY

    context.user_data["category"] = category
    questions = quiz_data[category][:]
    random.shuffle(questions)
    for q in questions:
        random.shuffle(q["options"])

    context.user_data["questions"] = questions
    context.user_data["current_question_index"] = 0
    context.user_data["score_this_round"] = 0

    await update.message.reply_text(
        f"Вы выбрали: {category}\nНачинаем викторину! Для выхода — /cancel."
    )
    return await ask_question(update, context)

# -------------------------
# Логика вопросов (ASK_QUESTION)
# -------------------------
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    index = context.user_data["current_question_index"]
    questions = context.user_data["questions"]

    if index >= len(questions):
        return await end_quiz(update, context)

    question_data = questions[index]
    question_text = question_data["question"]
    options = question_data["options"]

    keyboard = [[opt] for opt in options]
    await update.message.reply_text(
        f"\U0001F4AC Вопрос {index+1}/{len(questions)}:\n{question_text}",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_QUESTION

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_answer = update.message.text.strip()
    index = context.user_data["current_question_index"]
    questions = context.user_data["questions"]
    question_data = questions[index]

    correct_answer = question_data["answer"]
    explanation = question_data["explanation"]
    username = context.user_data["username"]

    if user_answer == correct_answer:
        context.user_data["score_this_round"] += 1
        text = (
            "\U00002705 Верно! +1 очко.\n"
            f"Правильный ответ: {correct_answer}\n"
            f"Пояснение: {explanation}"
        )
    else:
        text = (
            "\U0000274C Неверно.\n"
            f"Правильный ответ: {correct_answer}\n"
            f"Пояснение: {explanation}"
        )

    await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())

    context.user_data["current_question_index"] += 1
    return await ask_question(update, context)

async def end_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    score_this_round = context.user_data["score_this_round"]
    username = context.user_data["username"]

    # Добавляем очки в БД
    update_score_db(user_id, username, score_this_round)

    await update.message.reply_text(
        f"\U0001F389 Викторина завершена!\n"
        f"Ты набрал {score_this_round} очк(а/ов) за эту игру.\n"
        f"Посмотрим твой общий счёт — он обновлён!"
    )

    # Предложим вернуться в меню
    keyboard = [["\U000021A9 Вернуться в меню"]]
    await update.message.reply_text(
        text="Нажмите, чтобы вернуться в главное меню:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

    # Сбросим данные викторины
    context.user_data["questions"] = []
    context.user_data["current_question_index"] = 0
    context.user_data["score_this_round"] = 0

    # Возвращаемся в MAIN_MENU, когда пользователь нажмёт кнопку
    return MAIN_MENU

# -------------------------
# Функция main
# -------------------------
def main():
    # Читаем токен из переменной окружения
    token = os.environ.get("BOT_TOKEN")
    if not token:
        logger.error("Не найден BOT_TOKEN в окружении!")
        return

    # Инициализируем базу (PostgreSQL)
    init_db()

    # Можно использовать PicklePersistence для хранения состояний
    persistence = PicklePersistence(filepath="bot_state.pkl")
    application = ApplicationBuilder().token(token).persistence(persistence).build()

    # Описываем ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            CHOOSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_category)],
            ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    application.add_handler(conv_handler)

    logger.info("Бот запущен. Ожидание сообщений...")
    application.run_polling()

if __name__ == "__main__":
    main()
