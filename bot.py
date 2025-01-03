import json
import os
import random
import logging

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    PicklePersistence
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------
# Константы для состояний ConversationHandler
# -------------------------
ASK_NAME, CHOOSE_CATEGORY, ASK_QUESTION = range(3)

# -------------------------
# Путь к файлу для хранения результатов
# -------------------------
SCOREBOARD_FILE = "scoreboard.json"

# -------------------------
# Функции загрузки и сохранения результатов
# -------------------------
def load_scoreboard():
    """
    Загружает scoreboard.json, если он существует.
    Возвращает словарь вида:
    {
        "user_id_1": {"username": "Имя", "score": 10},
        "user_id_2": {"username": "Другое имя", "score": 5},
        ...
    }
    """
    if os.path.exists(SCOREBOARD_FILE):
        with open(SCOREBOARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}

def save_scoreboard(scoreboard):
    """
    Сохраняет словарь scoreboard в файл scoreboard.json
    """
    with open(SCOREBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(scoreboard, f, ensure_ascii=False, indent=2)

# -------------------------
# Данные викторины
# В каждой категории - по 20 вопросов
# -------------------------
quiz_data = {
    "Правила волейбола": [
        {
            "question": "Какой размер площадки для классического волейбола?",
            "options": ["9 м x 9 м", "18 м x 9 м", "16 м x 8 м", "20 м x 10 м"],
            "answer": "18 м x 9 м",
            "explanation": "По официальным правилам FIVB длина площадки составляет 18 метров, а ширина – 9 метров."
        },
        {
            "question": "Сколько игроков находится на площадке в одной команде в классическом волейболе?",
            "options": ["4", "5", "6", "7"],
            "answer": "6",
            "explanation": "В классическом формате на площадке в каждой команде играют по 6 человек."
        },
        {
            "question": "Какой максимальный вес разрешён для мяча в волейболе?",
            "options": ["250 г", "280 г", "300 г", "320 г"],
            "answer": "280 г",
            "explanation": "Официальный вес мяча лежит в диапазоне 260-280 граммов."
        },
        {
            "question": "Сколько очков нужно набрать, чтобы выиграть сет в классическом волейболе?",
            "options": ["15", "21", "25", "30"],
            "answer": "25",
            "explanation": "Необходимо набрать 25 очков с разницей минимум в 2 очка. При 24:24 игра продолжается."
        },
        {
            "question": "Какая высота сетки для мужского классического волейбола?",
            "options": ["2.24 м", "2.35 м", "2.43 м", "2.50 м"],
            "answer": "2.43 м",
            "explanation": "Стандарт FIVB для мужчин — 2,43 м над площадкой."
        },
        {
            "question": "Сколько тайм-аутов разрешено каждой команде в одном сете?",
            "options": ["1", "2", "3", "4"],
            "answer": "2",
            "explanation": "Каждая команда может взять два 30-секундных тайм-аута за сет (исключая тай-брейк)."
        },
        {
            "question": "Сколько касаний мяча разрешено одной команде до передачи через сетку?",
            "options": ["2", "3", "4", "5"],
            "answer": "3",
            "explanation": "Команда имеет право на максимум три касания (не считая касания блоком)."
        },
        {
            "question": "Какой размер площадки для пляжного волейбола?",
            "options": ["8 м x 8 м", "9 м x 9 м", "16 м x 8 м", "18 м x 9 м"],
            "answer": "16 м x 8 м",
            "explanation": "Пляжная площадка короче и уже — 16×8 м."
        },
        {
            "question": "Сколько игроков в команде на площадке в пляжном волейболе?",
            "options": ["2", "3", "4", "6"],
            "answer": "2",
            "explanation": "В пляжном волейболе играют 2 на 2, без запасных."
        },
        {
            "question": "В каком случае команде начисляется очко?",
            "options": [
                "Мяч касается пола соперника",
                "Мяч выходит за пределы от соперника",
                "Нарушение правил соперником",
                "Все вышеперечисленные"
            ],
            "answer": "Все вышеперечисленные",
            "explanation": "Очко даётся, если мяч упал на площадку соперника, соперник ошибся, либо нарушил правила."
        },
        {
            "question": "Какая высота сетки в женском пляжном волейболе?",
            "options": ["2.10 м", "2.15 м", "2.24 м", "2.43 м"],
            "answer": "2.24 м",
            "explanation": "Для женщин обычно используется высота сетки 2,24 м."
        },
        {
            "question": "Какой максимальный счёт может быть в сете, если разница очков не достигает двух?",
            "options": ["25", "30", "35", "Неограниченный"],
            "answer": "Неограниченный",
            "explanation": "Теоретически сет может продолжаться бесконечно, пока не будет разницы в 2 очка."
        },
        {
            "question": "Что означает термин «блок» в волейболе?",
            "options": [
                "Удар по мячу снизу",
                "Перекрытие пути мячу возле сетки",
                "Защитный пас",
                "Ошибка при подаче"
            ],
            "answer": "Перекрытие пути мячу возле сетки",
            "explanation": "Блок — это попытка игроков передней линии остановить атаку соперника, подняв руки над сеткой."
        },
        {
            "question": "Какова минимальная температура для проведения соревнований по снежному волейболу?",
            "options": ["-5 °C", "-10 °C", "-15 °C", "-20 °C"],
            "answer": "-10 °C",
            "explanation": "Обычно соревнования не проводят, если температура ниже -10 °C, чтобы сохранить здоровье игроков."
        },
        {
            "question": "Сколько игроков в одной команде в снежном волейболе?",
            "options": ["2", "3", "4", "5"],
            "answer": "3",
            "explanation": "На площадке играют по три человека (при этом могут быть запасные)."
        },
        {
            "question": "Сколько сетов играют в классическом волейболе для определения победителя?",
            "options": ["3", "4", "5", "6"],
            "answer": "5",
            "explanation": "Матч идёт до трёх выигранных сетов, максимум — 5 сетов."
        },
        {
            "question": "Сколько длится технический перерыв в классическом волейболе?",
            "options": ["30 секунд", "60 секунд", "90 секунд", "120 секунд"],
            "answer": "60 секунд",
            "explanation": "Раньше технические перерывы при 8 и 16 очках длились по 60 секунд."
        },
        {
            "question": "Что происходит, если мяч касается линии площадки?",
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
            "question": "Каково максимальное время для подачи после свистка судьи?",
            "options": ["5 секунд", "8 секунд", "10 секунд", "12 секунд"],
            "answer": "8 секунд",
            "explanation": "Игрок имеет 8 секунд, чтобы выполнить подачу, после сигнала судьи."
        },
        {
            "question": "Может ли либеро атаковать из передней зоны?",
            "options": [
                "Нет, никогда",
                "Да, только если мяч ниже уровня сетки",
                "Да, без ограничений",
                "Нет, но может выполнять передачи"
            ],
            "answer": "Да, только если мяч ниже уровня сетки",
            "explanation": "Либеро не может атаковать выше верхнего края сетки. Если мяч ниже, разрешается удар."
        }
    ],
    "История волейбола": [
        {
            "question": "Кто считается основателем волейбола?",
            "options": [
                "Джеймс Нейсмит",
                "Уильям Дж. Морган",
                "Пьер де Кубертен",
                "Джордж Фишер"
            ],
            "answer": "Уильям Дж. Морган",
            "explanation": "Уильям Морган создал волейбол (изначально «минтонет») в 1895 году."
        },
        {
            "question": "В каком году был изобретён волейбол?",
            "options": ["1891", "1895", "1900", "1912"],
            "answer": "1895",
            "explanation": "Именно в 1895 году Морган представил первую версию игры «минтонет»."
        },
        {
            "question": "Как первоначально называлась игра, придуманная Уильямом Морганом?",
            "options": ["Бадминтон", "Теннибол", "Минтонет", "Сферобол"],
            "answer": "Минтонет",
            "explanation": "Название «минтонет» позже заменили на «волейбол» (volleyball)."
        },
        {
            "question": "Кто изобрёл баскетбол, что позже вдохновило Моргана на создание волейбола?",
            "options": [
                "Джеймс Нейсмит",
                "Альфред Халстед",
                "Пьер де Кубертен",
                "Генри Морган"
            ],
            "answer": "Джеймс Нейсмит",
            "explanation": "Нейсмит изобрёл баскетбол в 1891 году, а Морган преподавал рядом с ним."
        },
        {
            "question": "В каком году волейбол официально вошёл в программу Олимпийских игр?",
            "options": ["1924", "1948", "1964", "1988"],
            "answer": "1964",
            "explanation": "Волейбол дебютировал на Олимпиаде 1964 года в Токио."
        },
        {
            "question": "В какой стране прошли первые Олимпийские игры, на которых был представлен волейбол?",
            "options": ["Япония", "Бразилия", "США", "Мексика"],
            "answer": "Япония",
            "explanation": "В 1964 году Олимпиада проходила в Токио (Япония)."
        },
        {
            "question": "Какой международный орган управляет волейболом во всём мире?",
            "options": [
                "ФИФА (FIFA)",
                "ФИВБ (FIVB)",
                "МОК (IOC)",
                "ФИБА (FIBA)"
            ],
            "answer": "ФИВБ (FIVB)",
            "explanation": "Международная федерация волейбола (FIVB) регулирует этот спорт."
        },
        {
            "question": "В каком году была основана Международная федерация волейбола (FIVB)?",
            "options": ["1895", "1908", "1947", "1952"],
            "answer": "1947",
            "explanation": "FIVB была создана в 1947 году после Второй мировой войны."
        },
        {
            "question": "Где находится штаб-квартира Международной федерации волейбола (FIVB)?",
            "options": [
                "Лозанна (Швейцария)",
                "Париж (Франция)",
                "Нью-Йорк (США)",
                "Монреаль (Канада)"
            ],
            "answer": "Лозанна (Швейцария)",
            "explanation": "FIVB, как и многие другие федерации, базируется в Лозанне."
        },
        {
            "question": "Какая страна считалась одной из ведущих по развитию волейбола в первой половине XX века?",
            "options": ["Испания", "Россия (СССР)", "Египет", "Великобритания"],
            "answer": "Россия (СССР)",
            "explanation": "СССР активно развивал и популяризировал волейбол, завоевывая высокие награды."
        },
        {
            "question": "В каком году прошёл первый официальный чемпионат мира по волейболу среди мужчин?",
            "options": ["1949", "1952", "1956", "1960"],
            "answer": "1949",
            "explanation": "Первый чемпионат мира состоялся в Праге (Чехословакия)."
        },
        {
            "question": "Когда в СССР состоялся первый чемпионат страны по волейболу среди мужчин?",
            "options": ["1923", "1933", "1938", "1947"],
            "answer": "1933",
            "explanation": "В 1933 году прошёл первый всесоюзный чемпионат, давший толчок развитию."
        },
        {
            "question": "Каково было первоначальное количество игроков на площадке в самой ранней версии волейбола?",
            "options": [
                "Не было чёткого ограничения",
                "По 6 человек",
                "По 9 человек",
                "По 4 человека"
            ],
            "answer": "Не было чёткого ограничения",
            "explanation": "Морган не оговаривал точного числа участников в самых первых правилах."
        },
        {
            "question": "В каком году впервые провели Кубок мира по волейболу?",
            "options": ["1959", "1965", "1969", "1977"],
            "answer": "1969",
            "explanation": "Кубок мира FIVB впервые состоялся в 1969 году."
        },
        {
            "question": "Какая страна является рекордсменом по количеству побед на мужских чемпионатах мира?",
            "options": ["Бразилия", "СССР / Россия", "США", "Италия"],
            "answer": "СССР / Россия",
            "explanation": "Советская, а затем российская сборная чаще других становилась чемпионом мира."
        },
        {
            "question": "Кто стал первым олимпийским чемпионом в мужском волейболе на Играх 1964 года?",
            "options": ["Япония", "Польша", "СССР", "США"],
            "answer": "СССР",
            "explanation": "На дебютном турнире по волейболу золото взяла команда СССР."
        },
        {
            "question": "В каком году пляжный волейбол был впервые включён в программу Олимпийских игр?",
            "options": ["1984", "1992", "1996", "2000"],
            "answer": "1996",
            "explanation": "Пляжный волейбол дебютировал на Олимпиаде в Атланте (1996 год)."
        },
        {
            "question": "Где прошёл первый официальный чемпионат мира по пляжному волейболу?",
            "options": [
                "Лос-Анджелес (США)",
                "Рио-де-Жанейро (Бразилия)",
                "Марсель (Франция)",
                "Майами (США)"
            ],
            "answer": "Рио-де-Жанейро (Бразилия)",
            "explanation": "Первый чемпионат мира по пляжному волейболу FIVB состоялся в Бразилии."
        },
        {
            "question": "В каком году состоялся первый чемпионат мира по волейболу среди женщин?",
            "options": ["1949", "1952", "1956", "1957"],
            "answer": "1952",
            "explanation": "Женский ЧМ впервые прошёл в Москве в 1952 году."
        },
        {
            "question": "Когда в официальных правилах волейбола появилась позиция «либеро»?",
            "options": ["1994", "1996", "1998", "2000"],
            "answer": "1998",
            "explanation": "Либеро ввели, чтобы усилить защиту и приём. Это произошло в 1998 году."
        },
    ]
}

# -------------------------
# Хендлеры команд
# -------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /start: приветствие + запрос имени.
    """
    await update.message.reply_text(
        "Привет! Я бот-викторина по волейболу.\n"
        "Для отмены в любой момент используйте /cancel.\n\n"
        "Как тебя зовут?"
    )
    return ASK_NAME

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /cancel: досрочное завершение викторины.
    """
    await update.message.reply_text("Викторина прервана. Возвращайся снова!")
    context.user_data.clear()
    return ConversationHandler.END

# -------------------------
# Логика регистрации и выбора категории
# -------------------------
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение имени пользователя, выбор категории.
    """
    user_id = update.effective_user.id
    username_input = update.message.text.strip()

    # Загрузим текущее состояние результатов
    scoreboard = load_scoreboard()

    # Если пользователя нет — создадим
    if str(user_id) not in scoreboard:
        scoreboard[str(user_id)] = {"username": username_input, "score": 0}
    else:
        # Обновим имя, если нужно
        scoreboard[str(user_id)]["username"] = username_input

    save_scoreboard(scoreboard)

    context.user_data["username"] = username_input

    # Предложим выбрать категорию
    categories = list(quiz_data.keys())  # ["Правила волейбола", "История волейбола"]
    keyboard = [[cat] for cat in categories]

    await update.message.reply_text(
        f"Отлично, {username_input}! Теперь выбери категорию викторины:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSE_CATEGORY

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Пользователь выбирает категорию, бот перемешивает вопросы и варианты ответов,
    затем переходит к задаванию вопросов.
    """
    category = update.message.text.strip()

    if category not in quiz_data:
        await update.message.reply_text(
            "Пожалуйста, выбери категорию из предложенных вариантов."
        )
        return CHOOSE_CATEGORY

    context.user_data["category"] = category

    # Скопируем список вопросов и перемешаем
    questions = quiz_data[category][:]
    random.shuffle(questions)
    for q in questions:
        random.shuffle(q["options"])

    # Сохраним вопросы и счёт
    context.user_data["questions"] = questions
    context.user_data["current_question_index"] = 0
    context.user_data["score_this_round"] = 0

    await update.message.reply_text(
        f"Вы выбрали категорию: {category}.\n"
        "Начинаем викторину!\n"
        "Чтобы прервать, используйте /cancel."
    )

    return await ask_question(update, context)

# -------------------------
# Логика вопросов
# -------------------------
async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Задаём очередной вопрос из списка. Если вопросы закончились, завершаем.
    """
    index = context.user_data["current_question_index"]
    questions = context.user_data["questions"]

    # Если вопросы закончились — завершаем
    if index >= len(questions):
        return await end_quiz(update, context)

    question_data = questions[index]
    question_text = question_data["question"]
    options = question_data["options"]

    # Сформируем клавиатуру
    keyboard = [[option] for option in options]

    await update.message.reply_text(
        f"Вопрос {index+1}/{len(questions)}:\n{question_text}",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_QUESTION

async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Проверяем ответ пользователя, показываем правильный ответ и пояснение.
    """
    user_answer = update.message.text.strip()
    index = context.user_data["current_question_index"]
    questions = context.user_data["questions"]
    question_data = questions[index]

    correct_answer = question_data["answer"]
    explanation = question_data["explanation"]

    # Проверяем, верно ли
    if user_answer == correct_answer:
        context.user_data["score_this_round"] += 1
        response = (
            "Верно! +1 очко.\n"
            f"Правильный ответ: {correct_answer}\n"
            f"Пояснение: {explanation}"
        )
    else:
        response = (
            "Неверно.\n"
            f"Правильный ответ: {correct_answer}\n"
            f"Пояснение: {explanation}"
        )

    await update.message.reply_text(response)

    # Переходим к следующему вопросу
    context.user_data["current_question_index"] += 1
    return await ask_question(update, context)

async def end_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Завершаем викторину, показываем итоговый счёт и рейтинг.
    """
    user_id = update.effective_user.id
    score_this_round = context.user_data["score_this_round"]
    username = context.user_data["username"]

    # Загрузим общую таблицу, обновим счёт
    scoreboard = load_scoreboard()
    if str(user_id) in scoreboard:
        scoreboard[str(user_id)]["score"] += score_this_round
        total_score = scoreboard[str(user_id)]["score"]
    else:
        # Теоретически не должно случиться, но на всякий случай
        scoreboard[str(user_id)] = {"username": username, "score": score_this_round}
        total_score = score_this_round

    save_scoreboard(scoreboard)

    await update.message.reply_text(
        f"Викторина завершена!\n"
        f"Ты набрал {score_this_round} очк(а/ов) за эту игру.\n"
        f"Твой общий счёт: {total_score}."
    )

    # Выведем топ-5
    sorted_users = sorted(scoreboard.items(), key=lambda x: x[1]["score"], reverse=True)
    top_5 = sorted_users[:5]
    rating_text = "Топ-5 участников:\n"
    for i, (uid, data) in enumerate(top_5, start=1):
        rating_text += f"{i}. {data['username']}: {data['score']} очков\n"

    await update.message.reply_text(rating_text, reply_markup=ReplyKeyboardRemove())

    # Сбросим внутреннее состояние
    context.user_data.clear()
    return ConversationHandler.END

# -------------------------
# Функция main для запуска бота
# -------------------------
def main():
    # Для запуска локально: замените на свой токен
    # При деплое на Railway — используйте os.environ.get("BOT_TOKEN")
    token = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

    # Можно сохранить состояние диалога между рестартами бота — PicklePersistence
    persistence = PicklePersistence(filepath="bot_state.pkl")

    application = ApplicationBuilder().token(token).persistence(persistence).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            CHOOSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_category)],
            ASK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_answer)]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )

    application.add_handler(conv_handler)

    logger.info("Бот запущен. Ожидание сообщений...")
  
