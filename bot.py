import logging
import random
import os
import json
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode
import psycopg2
from psycopg2 import sql

# Состояния ConversationHandler
GET_NAME, CHOOSE_CATEGORY, QUIZ = range(3)

# ------------------------ ПРАВИЛА ВОЛЕЙБОЛА (20 вопросов) ------------------------
volleyball_rules_questions = [
    # ... (ваши 20 вопросов по правилам)
]

# ------------------------ ИСТОРИЯ ВОЛЕЙБОЛА (20 вопросов) ------------------------
volleyball_history_questions = [
    # ... (ваши 20 вопросов по истории)
]

# -------------------- ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ---------------------
def get_db_connection():
    """
    Устанавливает соединение с базой данных PostgreSQL.
    """
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    return conn

def initialize_database():
    """
    Создает таблицу для рейтинга, если она еще не существует.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scoreboard (
            username TEXT PRIMARY KEY,
            score INTEGER NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def get_user_score(username):
    """
    Возвращает текущий счёт пользователя.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT score FROM scoreboard WHERE username = %s;", (username,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result[0] if result else 0

def update_user_score(username, score):
    """
    Обновляет счёт пользователя в базе данных.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    current_score = get_user_score(username)
    if score > current_score:
        cur.execute("""
            INSERT INTO scoreboard (username, score)
            VALUES (%s, %s)
            ON CONFLICT (username) DO UPDATE
            SET score = EXCLUDED.score;
        """, (username, score))
        conn.commit()
    cur.close()
    conn.close()

def get_top_scores(limit=10):
    """
    Возвращает топ пользователей по очкам.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT username, score FROM scoreboard
        ORDER BY score DESC, username ASC
        LIMIT %s;
    """, (limit,))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

def shuffle_questions(questions_list):
    """
    Перемешивает вопросы и варианты ответов.
    """
    random.shuffle(questions_list)
    for q in questions_list:
        correct_answer = q["options"][q["correct_index"]]
        random.shuffle(q["options"])
        q["correct_index"] = q["options"].index(correct_answer)

# ------------------------------- ОБРАБОТЧИКИ -------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Команда /start: приветствие и запрос имени пользователя.
    """
    await update.message.reply_text(
        "<b>\U0001F44B Добро пожаловать в викторину по волейболу!</b>\n\n"
        "Для начала представьтесь, пожалуйста. Введите ваше имя:",
        parse_mode=ParseMode.HTML
    )
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняем введённое имя пользователя и предлагаем выбрать категорию.
    """
    user_name = update.message.text.strip()
    context.user_data["user_name"] = user_name
    context.user_data["score"] = 0

    reply_keyboard = [["Правила волейбола", "История волейбола"]]
    await update.message.reply_text(
        f"<b>Отлично, {user_name}!</b>\n"
        "Выберите категорию викторины:",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return CHOOSE_CATEGORY

async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Сохраняем выбранную категорию, перемешиваем вопросы и переходим к первому вопросу.
    """
    category_text = update.message.text.strip().lower()

    if category_text == "правила волейбола":
        questions = volleyball_rules_questions.copy()
    elif category_text == "история волейбола":
        questions = volleyball_history_questions.copy()
    else:
        await update.message.reply_text(
            "<i>Неверная категория. Попробуйте ещё раз.</i>",
            parse_mode=ParseMode.HTML
        )
        return CHOOSE_CATEGORY

    shuffle_questions(questions)
    context.user_data["questions"] = questions
    context.user_data["current_question_index"] = 0

    return await ask_question(update, context)

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправляем текущий вопрос, если он есть. Иначе — подводим итоги.
    """
    questions = context.user_data["questions"]
    current_index = context.user_data["current_question_index"]

    if current_index >= len(questions):
        return await show_score(update, context)

    question_data = questions[current_index]
    question_text = question_data["question"]
    options = question_data["options"]

    progress_text = f"Вопрос {current_index + 1} из {len(questions)}"
    text_to_send = (
        f"<b>\U00002753 {progress_text}</b>\n\n"
        f"<i>{question_text}</i>\n\n"
        "Выберите один из вариантов:"
    )

    reply_keyboard = [[opt] for opt in options]

    await update.message.reply_text(
        text_to_send,
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return QUIZ

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Проверяем ответ, выводим сообщение «Верно!» или «Неверно! Правильный ответ: ...»,
    затем переходим к следующему вопросу.
    """
    user_answer = update.message.text.strip()
    questions = context.user_data["questions"]
    current_index = context.user_data["current_question_index"]
    question_data = questions[current_index]

    correct_index = question_data["correct_index"]
    correct_answer = question_data["options"][correct_index]

    # Проверяем ответ
    if user_answer == correct_answer:
        context.user_data["score"] += 1
        feedback_text = "<b>\U00002705 Верно!</b>"  # ✅
    else:
        feedback_text = (
            f"<b>\U0000274C Неверно!</b>\n"  # ❌
            f"Правильный ответ: <i>{correct_answer}</i>"
        )

    # Отправляем обратную связь
    await update.message.reply_text(feedback_text, parse_mode=ParseMode.HTML)

    # Переходим к следующему вопросу
    context.user_data["current_question_index"] += 1
    return await ask_question(update, context)

async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Показываем итог, формируем рейтинг участников.
    """
    user_name = context.user_data["user_name"]
    score = context.user_data["score"]

    # Обновляем рейтинг в базе данных
    update_user_score(user_name, score)

    # Получаем топ 10 пользователей
    top_scores = get_top_scores(limit=10)

    # Формируем текст рейтинга
    if top_scores:
        rating_text = "<b>\U0001F4CA Рейтинг участников:</b>\n"  # 📊
        for i, (name, points) in enumerate(top_scores, start=1):
            rating_text += f"{i}. <b>{name}</b> — {points} очков\n"
    else:
        rating_text = "Пока нет участников."

    # Итоговое сообщение
    await update.message.reply_text(
        f"<b>\U0001F3C6 Викторина завершена!</b>\n"  # 🏆
        f"Ваш результат: <b>{score}</b> очков.\n\n"
        f"{rating_text}\n"
        "Спасибо за участие!\n"
        "Чтобы начать заново, введите /start.",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка /cancel (досрочное завершение).
    """
    await update.message.reply_text(
        "<i>Викторина отменена. Возвращайтесь, когда будете готовы!</i>",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

def main():
    # Включаем логирование
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    # Инициализируем базу данных
    initialize_database()

    # Загружаем рейтинг из базы данных (если необходимо)

    # Инициализируем приложение (бота)
    application = ApplicationBuilder().token(os.environ['BOT_TOKEN']).build()

    # Создаём ConversationHandler для управления диалогом
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CHOOSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_category)],
            QUIZ: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Регистрируем ConversationHandler
    application.add_handler(conv_handler)

    # Запускаем бота (поллинг)
    application.run_polling()

if __name__ == "__main__":
    main()
