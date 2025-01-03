import logging
import os
import random

from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------------
# Состояния
# -------------------------
MAIN_MENU, ASK_NAME, CHOOSE_CATEGORY, ASK_QUESTION = range(4)

# -------------------------
# Храним очки игроков в памяти (словарь).
# -------------------------
# Формат: scoreboard[user_id] = {"username": "...", "score": <int>}
scoreboard = {}

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
            "explanation": "В классическом формате на площадке в каждой команде играют по 6 человек (плюс запасные)."
        },
        {
            "question": "3. Какой максимальный вес разрешён для мяча в волейболе?",
            "options": ["250 г", "280 г", "300 г", "320 г"],
            "answer": "280 г",
            "explanation": "Вес официального мяча должен быть в диапазоне 260–280 г."
        },
        {
            "question": "4. Сколько очков нужно набрать, чтобы выиграть сет в классическом волейболе?",
            "options": ["15", "21", "25", "30"],
            "answer": "25",
            "explanation": "Необходимо набрать минимум 25 очков с разницей в 2."
        },
        {
            "question": "5. Какая высота сетки для мужского классического волейбола?",
            "options": ["2.24 м", "2.35 м", "2.43 м", "2.50 м"],
            "answer": "2.43 м",
            "explanation": "Высота сетки для мужчин — 2,43 м."
        },
        {
            "question": "6. Сколько тайм-аутов разрешено каждой команде в одном сете?",
            "options": ["1", "2", "3", "4"],
            "answer": "2",
            "explanation": "В классическом сете обычно два 30-секундных тайм-аута."
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
            "explanation": "В пляжном волейболе площадка 16×8 м, меньше классической."
        },
        {
            "question": "9. Сколько игроков в команде на площадке в пляжном волейболе?",
            "options": ["2", "3", "4", "6"],
            "answer": "2",
            "explanation": "Пляжный волейбол играется 2 на 2, без запасных."
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
            "explanation": "Очко при любой ошибке соперника или попадании мяча на его сторону."
        },
        {
            "question": "11. Какая высота сетки в женском пляжном волейболе?",
            "options": ["2.10 м", "2.15 м", "2.24 м", "2.43 м"],
            "answer": "2.24 м",
            "explanation": "У женщин в пляжном волейболе сетка 2,24 м."
        },
        {
            "question": "12. Какой максимальный счёт может быть в сете, если разница очков не достигает двух?",
            "options": ["25", "30", "35", "Неограниченный"],
            "answer": "Неограниченный",
            "explanation": "Сет продолжается, пока не будет +2 очка."
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
            "explanation": "Блок – это попытка игроков передней линии перекрыть атаку соперника."
        },
        {
            "question": "14. Какова минимальная температура для проведения соревнований по снежному волейболу?",
            "options": ["-5 °C", "-10 °C", "-15 °C", "-20 °C"],
            "answer": "-10 °C",
            "explanation": "Обычно порог -10 °C устанавливается для снежного волейбола."
        },
        {
            "question": "15. Сколько игроков в одной команде в снежном волейболе?",
            "options": ["2", "3", "4", "5"],
            "answer": "3",
            "explanation": "В снежном волейболе играет по три человека в команде."
        },
        {
            "question": "16. Сколько сетов играют в классическом волейболе для определения победителя?",
            "options": ["3", "4", "5", "6"],
            "answer": "5",
            "explanation": "Матч идёт до 3 выигранных сетов, максимум 5."
        },
        {
            "question": "17. Сколько длится технический перерыв в классическом волейболе?",
            "options": ["30 секунд", "60 секунд", "90 секунд", "120 секунд"],
            "answer": "60 секунд",
            "explanation": "Технические перерывы ранее были по 60 секунд (при 8 и 16 очках)."
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
            "explanation": "Игрок имеет 8 секунд на подачу."
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
            "explanation": "Уильям Морган создал эту игру в 1895 году, работая в YMCA."
        },
        {
            "question": "22. В каком году был изобретён волейбол?",
            "options": ["1891", "1895", "1900", "1912"],
            "answer": "1895",
            "explanation": "В 1895 году Морган провёл первую демонстрацию «минтонета»."
        },
        {
            "question": "23. Как первоначально называлась игра, придуманная Уильямом Морганом?",
            "options": ["Бадминтон", "Теннибол", "Минтонет", "Сферобол"],
            "answer": "Минтонет",
            "explanation": "Первоначальное название «минтонет», позже сменили на «волейбол»."
        },
        {
            "question": "24. Кто изобрёл баскетбол, что позже вдохновило Моргана на создание волейбола?",
            "options": ["Джеймс Нейсмит", "Альфред Халстед", "Пьер де Кубертен", "Генри Морган"],
            "answer": "Джеймс Нейсмит",
            "explanation": "Нейсмит изобрёл баскетбол в 1891, Морган вдохновился и сделал волейбол."
        },
        {
            "question": "25. В каком году волейбол официально вошёл в программу Олимпийских игр?",
            "options": ["1924", "1948", "1964", "1988"],
            "answer": "1964",
            "explanation": "В Токио-1964 волейбол стал олимпийским."
        },
        {
            "question": "26. В какой стране прошли первые Олимпийские игры, на которых был представлен волейбол?",
            "options": ["Япония", "Бразилия", "США", "Мексика"],
            "answer": "Япония",
            "explanation": "Олимпиада 1964 года прошла в Токио (Япония)."
        },
        {
            "question": "27. Какой международный орган управляет волейболом во всём мире?",
            "options": ["ФИФА (FIFA)", "ФИВБ (FIVB)", "МОК (IOC)", "ФИБА (FIBA)"],
            "answer": "ФИВБ (FIVB)",
            "explanation": "Международная федерация волейбола (FIVB) регулирует этот спорт."
        },
        {
            "question": "28. В каком году была основана Международная федерация волейбола (FIVB)?",
            "options": ["1895", "1908", "1947", "1952"],
            "answer": "1947",
            "explanation": "FIVB учреждена в 1947 году после Второй мировой войны."
        },
        {
            "question": "29. Где находится штаб-квартира Международной федерации волейбола (FIVB)?",
            "options": ["Лозанна (Швейцария)", "Париж (Франция)", "Нью-Йорк (США)", "Монреаль (Канада)"],
            "answer": "Лозанна (Швейцария)",
            "explanation": "Многие спортивные федерации располагаются в Лозанне."
        },
        {
            "question": "30. Какая страна считалась одной из ведущих по развитию волейбола в первой половине XX века?",
            "options": ["Испания", "Россия (СССР)", "Египет", "Великобритания"],
            "answer": "Россия (СССР)",
            "explanation": "СССР активно развивал волейбол и добивался высоких результатов."
        },
        {
            "question": "31. В каком году прошёл первый официальный чемпионат мира по волейболу среди мужчин?",
            "options": ["1949", "1952", "1956", "1960"],
            "answer": "1949",
            "explanation": "Первый ЧМ состоялся в Праге (Чехословакия)."
        },
        {
            "question": "32. Когда в СССР состоялся первый чемпионат страны по волейболу среди мужчин?",
            "options": ["1923", "1933", "1938", "1947"],
            "answer": "1933",
            "explanation": "В 1933 году прошёл первый всесоюзный чемпионат."
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
            "explanation": "Морган не оговаривал точного числа участников."
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
            "explanation": "Советская/российская сборная чаще всего становилась чемпионом мира."
        },
        {
            "question": "36. Кто стал первым олимпийским чемпионом в мужском волейболе на Играх 1964 года?",
            "options": ["Япония", "Польша", "СССР", "США"],
            "answer": "СССР",
            "explanation": "На дебютном олимпийском волейбольном турнире в 1964 золото взяла СССР."
        },
        {
            "question": "37. В каком году пляжный волейбол был впервые включён в программу Олимпийских игр?",
            "options": ["1984", "1992", "1996", "2000"],
            "answer": "1996",
            "explanation": "Пляжный волейбол дебютировал на Олимпиаде-1996 (Атланта, США)."
        },
        {
            "question": "38. Где прошёл первый официальный чемпионат мира по пляжному волейболу?",
            "options": ["Лос-Анджелес (США)", "Рио-де-Жанейро (Бразилия)", "Марсель (Франция)", "Майами (США)"],
            "answer": "Рио-де-Жанейро (Бразилия)",
            "explanation": "Бразилия — одна из сильнейших стран в пляжном волейболе, ЧМ провели там."
        },
        {
            "question": "39. В каком году состоялся первый чемпионат мира по волейболу среди женщин?",
            "options": ["1949", "1952", "1956", "1957"],
            "answer": "1952",
            "explanation": "Женский ЧМ впервые прошёл в 1952 году в Москве (СССР)."
        },
        {
            "question": "40. Когда в официальных правилах волейбола появилась позиция «либеро»?",
            "options": ["1994", "1996", "1998", "2000"],
            "answer": "1998",
            "explanation": "Позицию либеро ввели в 1998 году, чтобы усилить игру в защите."
        },
    ]
}

# -------------------------
# /start — показ меню
# -------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_main_menu(update, context)

# -------------------------
# /cancel — прервать викторину (вернуться в меню)
# -------------------------
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Викторина прервана. Возвращаемся в главное меню!")
    return await show_main_menu(update, context)

# -------------------------
# Главное меню
# -------------------------
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Главное меню на Reply-кнопках:
    1) Начать викторину
    2) Лучшие игроки
    3) Наш магазин
    """
    keyboard = [
        ["Начать викторину"],
        ["Лучшие игроки"],
        ["Наш магазин"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )
    return MAIN_MENU

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()

    if choice == "Начать викторину":
        # Переходим к запросу имени
        await update.message.reply_text("Отлично! Как тебя зовут?", reply_markup=ReplyKeyboardRemove())
        return ASK_NAME

    elif choice == "Лучшие игроки":
        # Формируем топ-10 из scoreboard
        if not scoreboard:
            text = "Пока никто не играл."
        else:
            # Сортируем по убыванию score
            sorted_users = sorted(scoreboard.items(), key=lambda x: x[1]["score"], reverse=True)
            top_10 = sorted_users[:10]
            text = "Топ-10 игроков:\n"
            for i, (uid, data) in enumerate(top_10, start=1):
                text += f"{i}. {data['username']}: {data['score']}\n"

        await update.message.reply_text(text)
        return await show_main_menu(update, context)

    elif choice == "Наш магазин":
        # Отправляем INLINE-кнопку (гибридный подход)
        inline_keyboard = [
            [InlineKeyboardButton(text="Открыть магазин", url="https://t.me/magaz_volley")]
        ]
        inline_markup = InlineKeyboardMarkup(inline_keyboard)
        await update.message.reply_text(
            text="Наш магазин в Telegram. Нажмите кнопку:",
            reply_markup=inline_markup
        )
        # Возвращаемся в меню (или просто оставим так)
        return await show_main_menu(update, context)

    elif choice == "Вернуться в меню":
        # Если пользователь нажал кнопку «Вернуться в меню» после викторины
        return await show_main_menu(update, context)

    else:
        await update.message.reply_text("Пожалуйста, выберите пункт из меню.")
        return MAIN_MENU

# -------------------------
# Логика регистрации имени -> выбор категории
# -------------------------
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    username_input = update.message.text.strip()

    # Если пользователя нет — создадим
    if user_id not in scoreboard:
        scoreboard[user_id] = {"username": username_input, "score": 0}
    else:
        scoreboard[user_id]["username"] = username_input

    context.user_data["username"] = username_input

    # Предлагаем выбрать категорию
    categories = list(quiz_data.keys())  # ["Правила волейбола 🏐", "История волейбола 📖"]
    cat_keyboard = [[cat] for cat in categories]

    await update.message.reply_text(
        f"Приятно познакомиться, {username_input}!\nВыберите категорию викторины:",
        reply_markup=ReplyKeyboardMarkup(cat_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSE_CATEGORY

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text.strip()
    if category not in quiz_data:
        await update.message.reply_text("Пожалуйста, выберите категорию из списка.")
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
        f"Вы выбрали категорию: {category}\nНачинаем викторину! Для отмены — /cancel."
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

    # Клавиатура вариантов
    keyboard = [[opt] for opt in options]

    await update.message.reply_text(
        f"Вопрос {index+1}/{len(questions)}:\n{question_text}",
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
        reply_text = (
            "Верно! +1 очко.\n"
            f"Правильный ответ: {correct_answer}\n"
            f"Пояснение: {explanation}"
        )
    else:
        reply_text = (
            "Неверно.\n"
            f"Правильный ответ: {correct_answer}\n"
            f"Пояснение: {explanation}"
        )

    await update.message.reply_text(reply_text)

    context.user_data["current_question_index"] += 1
    return await ask_question(update, context)

# -------------------------
# Завершение викторины
# -------------------------
async def end_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    score_this_round = context.user_data["score_this_round"]
    username = context.user_data["username"]

    # Обновим общий счёт
    scoreboard[user_id]["score"] += score_this_round

    await update.message.reply_text(
        f"Викторина завершена!\n"
        f"Ты набрал {score_this_round} очк(а/ов) за эту игру.\n"
        f"Твой общий счёт: {scoreboard[user_id]['score']}."
    )

    # Кнопка «Вернуться в меню»
    keyboard = [["Вернуться в меню"]]
    await update.message.reply_text(
        "Нажмите, чтобы вернуться в главное меню:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

    # Сбросим промежуточные данные
    context.user_data["questions"] = []
    context.user_data["current_question_index"] = 0
    context.user_data["score_this_round"] = 0

    # ВНИМАНИЕ: возращаем MAIN_MENU вместо ConversationHandler.END
    return MAIN_MENU

# -------------------------
# Функция main (запуск бота)
# -------------------------
def main():
    token = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

    # Сохраняем состояния в файл (опционально); при перезапусках на локальной машине
    persistence = PicklePersistence(filepath="bot_state.pkl")
    application = ApplicationBuilder().token(token).persistence(persistence).build()

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
