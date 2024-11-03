import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    Filters,
)

from moodmeter.modules import transformers_mood, mood_calculator
from lib.postgresql_manager import PostgreSQLConnector
from moodmeter.utils.utils import hash_password, logger

# Загрузка переменных окружения
load_dotenv()

# Получение токена бота и ID чата администратора из переменных окружения
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

# Инициализация подключения к базе данных
conn = PostgreSQLConnector()


def save_message_to_sql(
        chat_id: int,
        user_id: int,
        message_text: str,
        message_label: str,
        label_score: float,
        chat_mood: float,
        message_datetime: datetime,
        table_name: str = 'message_analysis'
) -> None:
    """
    Сохраняет данные анализа сообщения в базу данных.

    Args:
        chat_id (int): ID чата.
        user_id (int): ID пользователя.
        message_text (str): Текст сообщения.
        message_label (str): Метка настроения сообщения.
        label_score (float): Уверенность в метке.
        chat_mood (float): Общий показатель настроения чата.
        message_datetime (datetime): Время отправки сообщения.
        table_name (str, optional): Название таблицы в БД. По умолчанию 'message_analysis'.
    """
    data = [
        (
            chat_id,
            user_id,
            message_text,
            message_datetime,
            message_label,
            label_score,
            chat_mood
        )
    ]
    columns = [
        'chat_id',
        'user_id',
        'message_text',
        'message_datetime',
        'message_label',
        'label_score',
        'chat_mood'
    ]
    conn.insert_data(data, table_name, columns)


def save_user_to_sql(
        user_id: int,
        password: str,
        table_name: str = 'user_credentials'
) -> None:
    """
    Сохраняет данные пользователя в базу данных.

    Args:
        user_id (int): ID пользователя.
        password (str): Захешированный пароль.
        table_name (str, optional): Название таблицы в БД. По умолчанию 'user_credentials'.
    """
    data = [(user_id, password)]
    columns = ['user_id', 'password']
    conn.insert_data(data, table_name, columns)


def save_chat_to_sql(
        user_id: int,
        chat_id: int,
        table_name: str = 'user_chat'
) -> None:
    """
    Сохраняет связь пользователя с чатом в базу данных.

    Args:
        user_id (int): ID пользователя.
        chat_id (int): ID чата.
        table_name (str, optional): Название таблицы в БД. По умолчанию 'user_chat'.
    """
    data = [(user_id, chat_id)]
    columns = ['user_id', 'chat_id']
    conn.insert_data(data, table_name, columns)


def deactivate_chat_in_sql(chat_id: int, table_name: str = 'chat') -> None:
    """
    Деактивирует чат в базе данных.

    Args:
        chat_id (int): ID чата.
        table_name (str, optional): Название таблицы в БД. По умолчанию 'chat'.
    """
    conn.update_data(table_name, 'chat_id', chat_id, 'status', 'deactivated')


def handle_message(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает входящие сообщения, анализирует настроение и отправляет оповещения.

    Args:
        update (Update): Объект обновления от Telegram.
        context (CallbackContext): Контекст бота.
    """
    message = update.message
    if not message:
        return  # Игнорируем не-текстовые сообщения

    message_datetime = message.date
    chat_id = message.chat_id
    user = message.from_user
    message_text = message.text

    try:
        # Проверка, активен ли чат в БД
        query_status_chat = (
            f"SELECT status FROM public.chat "
            f"WHERE chat_id = %s"
        )
        status_chat_data = conn.read_data(query_status_chat, (chat_id,))
        if not status_chat_data:
            # Если чат не найден в базе данных
            context.bot.send_message(
                chat_id=chat_id,
                text="Этот чат не настроен для мониторинга настроений. Пожалуйста, свяжитесь с администратором для получения дополнительной информации."
            )
            return

        status_chat = status_chat_data[0][0]
    except Exception as e:
        # Обработка ошибок при запросе к базе данных
        logger.error(f"Ошибка при проверке статуса чата: {e}")
        context.bot.send_message(
            chat_id=chat_id,
            text="Произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте позже."
        )
        return

    if status_chat == 'active':
        try:
            # Анализ настроения сообщения
            message_label, label_score = transformers_mood.predict_sentiment(message_text)

            # Вычисление общего настроения чата
            chat_mood = mood_calculator.calculate_weighted_sentiment(message_label, label_score)

            # Сохранение данных в базу
            save_message_to_sql(
                chat_id=chat_id,
                user_id=user.id,
                message_text=message_text,
                message_datetime=message_datetime,
                message_label=message_label,
                label_score=label_score,
                chat_mood=chat_mood
            )

            # Проверка на негативные сообщения с высокой уверенностью
            if message_label == "NEGATIVE" and label_score > 0.65:
                query_chat_id = (
                    f"select user_id, chat_name from public.user_chat "
                    f"join public.chat using(chat_id)"
                    f"WHERE chat_id = %s"
                )
                chat_id_data = conn.read_data(query_chat_id, (chat_id,))
                logger.info(chat_id_data)
                admin_chat_id = chat_id_data[0][0]
                chat_name = chat_id_data[0][1]
                alert_message = (
                    f"Внимание! В чате {chat_id} ({chat_name}) обнаружено негативное сообщение:\n\n"
                    f"Пользователь: {user.full_name} (@{user.username})\n"
                    f"Сообщение: {message_text}\n"
                    f"Оценка негативности: {label_score:.2f}"
                )
                context.bot.send_message(chat_id=admin_chat_id, text=alert_message)

            # Логирование сообщений (опционально можно убрать в продакшене)
            logger.info(f"User: {user.full_name} (@{user.username})")
            logger.info(f"Message: {message_text}")
            logger.info(f"Label: {message_label}, Score: {label_score}, Mood: {chat_mood}")
        except Exception as e:
            # Обработка ошибок при анализе настроений и сохранении данных
            logger.error(f"Ошибка при обработке сообщения: {e}")
            context.bot.send_message(
                chat_id=chat_id,
                text="Произошла ошибка при анализе вашего сообщения. Пожалуйста, попробуйте позже."
            )
    else:
        # Чат не активен, отправляем уведомление пользователю
        context.bot.send_message(
            chat_id=chat_id,
            text="Этот чат в данный момент не мониторится системой MoodMeter."
        )

        # Опционально можно логировать этот случай
        logger.info(f"Чат с ID {chat_id} не активен. Сообщение от пользователя {user.full_name} игнорировано.")


def start(update: Update, context: CallbackContext) -> None:
    """
    Отправляет приветственное сообщение с инструкциями.

    Args:
        update (Update): Объект обновления от Telegram.
        context (CallbackContext): Контекст бота.
    """
    update.message.reply_text(
        "Привет! Добро пожаловать в бота MoodMeter. Вот доступные команды:\n\n"
        "1. /add_user — добавить ваш user_id.\n"
        "2. /add_chat chat_id chat_name — добавить чат в MoodMeter. Если не указать имя, оно будет пустое.\n"
        "3. /deactivate_chat chat_id — удалить чат из MoodMeter.\n\n"
        "Важно: после команды указывайте chat_id через пробел!"
    )


def add_user_command(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает команду /add_user для регистрации пользователя.

    Args:
        update (Update): Объект обновления от Telegram.
        context (CallbackContext): Контекст бота.
    """
    if update.effective_chat.type != 'private':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Эта команда доступна только в личных сообщениях.'
        )
        return

    user_id = update.message.from_user.id
    password = hash_password(str(user_id))

    query_user = f"SELECT user_id FROM public.user_credentials WHERE user_id={user_id}"

    try:
        users = conn.read_data_to_dataframe(query_user)

        if users.empty:
            save_user_to_sql(user_id, password)
            update.message.reply_text(f"Ваш user_id: {user_id} был успешно зарегистрирован.")
        else:
            update.message.reply_text(f"Ваш user_id: {user_id} уже зарегистрирован в системе.")
    except Exception as e:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Произошла ошибка при регистрации пользователя. Пожалуйста, попробуйте позже.'
        )


def add_chat_command(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает команду /add_chat для добавления чата в систему.

    Args:
        update (Update): Объект обновления от Telegram.
        context (CallbackContext): Контекст бота.
    """
    if update.effective_chat.type != 'private':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Эта команда доступна только в личных сообщениях.'
        )
        return

    if len(context.args) == 0:
        update.message.reply_text('Укажите ID чата и название через пробел после команды.')
        return

    try:
        user_id = update.message.from_user.id
        chat_id = int(context.args[0])
        if len(context.args) == 2:
            chat_name = context.args[1]
        else:
            chat_name = ''
    except ValueError:
        update.message.reply_text('ID чата должен быть числом.')
        return

    # Проверка наличия чата в базе данных
    query_chat = f"SELECT status FROM public.chat WHERE chat_id = {chat_id}"
    chat_data = conn.read_data_to_dataframe(query_chat)

    if chat_data.empty:
        # Добавление нового чата
        conn.insert_data([(chat_id, 'active', chat_name)], 'chat', ['chat_id', 'status', 'chat_name'])
        save_chat_to_sql(user_id, chat_id)
        update.message.reply_text(f'Чат с ID {chat_id} и названием {chat_name} создан и активирован.')
    else:
        chat_status = chat_data.iloc[0]['status']
        if chat_status == 'deactivated':
            # Активация чата
            conn.update_data('chat', 'chat_id', chat_id, 'status', 'active')
            update.message.reply_text(f'Чат с ID {chat_id} был активирован.')

        # Проверка, привязан ли пользователь к чату
        query_user_chat = (
            f"SELECT user_id FROM public.user_chat "
            f"WHERE chat_id = {chat_id} AND user_id = {user_id}"
        )
        user_chat_data = conn.read_data_to_dataframe(query_user_chat)

        if user_chat_data.empty:
            save_chat_to_sql(user_id, chat_id)
            update.message.reply_text(f'Вы добавлены в чат с ID {chat_id}.')
        else:
            update.message.reply_text(f'Вы уже привязаны к чату с ID {chat_id}.')


def deactivate_chat_command(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает команду /deactivate_chat для удаления чата из системы.

    Args:
        update (Update): Объект обновления от Telegram.
        context (CallbackContext): Контекст бота.
    """
    if update.effective_chat.type != 'private':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Эта команда доступна только в личных сообщениях.'
        )
        return

    if len(context.args) < 1:
        update.message.reply_text('Укажите ID чата через пробел после команды.')
        return

    try:
        user_id = update.message.from_user.id
        chat_id = int(context.args[0])
    except ValueError:
        update.message.reply_text('ID чата должен быть числом.')
        return

    # Проверка, является ли пользователь администратором чата
    query_admin = f"SELECT user_id FROM public.user_chat WHERE chat_id = {chat_id}"
    admin_data = conn.read_data_to_dataframe(query_admin)

    if admin_data.empty or user_id not in admin_data['user_id'].values:
        update.message.reply_text('Вы не являетесь администратором этого чата.')
        return

    # Деактивация чата
    deactivate_chat_in_sql(chat_id)
    update.message.reply_text(f'Чат с ID {chat_id} был удален из MoodMeter.')


def rename_chat_command(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает команду /rename_chat переименования чата в системе.

    Args:
        update (Update): Объект обновления от Telegram.
        context (CallbackContext): Контекст бота.
    """
    if update.effective_chat.type != 'private':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Эта команда доступна только в личных сообщениях.'
        )
        return

    if len(context.args) != 2:
        update.message.reply_text('Укажите ID чата и новое название через пробел после команды.')
        return

    try:
        user_id = update.message.from_user.id
        chat_id = int(context.args[0])
        new_chat_name = context.args[1]
    except ValueError:
        update.message.reply_text('ID чата должен быть числом.')
        return

    # Проверка, является ли пользователь администратором чата
    query_admin = f"SELECT user_id FROM public.user_chat WHERE chat_id = {chat_id}"
    admin_data = conn.read_data_to_dataframe(query_admin)

    if admin_data.empty or user_id not in admin_data['user_id'].values:
        update.message.reply_text('Вы не являетесь администратором этого чата.')
        return

    # Смена имени
    conn.update_data('chat', 'chat_id', chat_id, 'chat_name', new_chat_name)
    update.message.reply_text(f'Чат с ID {chat_id} был переименован на {new_chat_name}.')


def welcome(update: Update, context: CallbackContext) -> None:
    """
    Обрабатывает событие, когда бот добавлен в чат.

    Args:
        update (Update): Объект обновления от Telegram.
        context (CallbackContext): Контекст бота.
    """
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            chat_id = update.effective_chat.id
            # Здесь можно реализовать чтение истории чата
            break


def main() -> None:
    """
    Инициализирует бота и запускает обработку сообщений.
    """
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Обработчики команд и сообщений
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('add_user', add_user_command))
    dispatcher.add_handler(CommandHandler('add_chat', add_chat_command))
    dispatcher.add_handler(CommandHandler('deactivate_chat', deactivate_chat_command))
    dispatcher.add_handler(CommandHandler('rename_chat', rename_chat_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members, welcome))

    # Запуск бота
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
