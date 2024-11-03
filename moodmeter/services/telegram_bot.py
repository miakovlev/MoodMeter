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

# Load environment variables
load_dotenv()

# Retrieve bot token and admin chat ID from environment variables
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')

# Initialize database connection
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
    Saves message analysis data to the database.

    Args:
        chat_id (int): Chat ID.
        user_id (int): User ID.
        message_text (str): Message text.
        message_label (str): Mood label of the message.
        label_score (float): Confidence in the label.
        chat_mood (float): Overall chat mood score.
        message_datetime (datetime): Message timestamp.
        table_name (str, optional): Table name in the DB. Defaults to 'message_analysis'.
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
    Saves user data to the database.

    Args:
        user_id (int): User ID.
        password (str): Hashed password.
        table_name (str, optional): Table name in the DB. Defaults to 'user_credentials'.
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
    Saves user-chat relationship to the database.

    Args:
        user_id (int): User ID.
        chat_id (int): Chat ID.
        table_name (str, optional): Table name in the DB. Defaults to 'user_chat'.
    """
    data = [(user_id, chat_id)]
    columns = ['user_id', 'chat_id']
    conn.insert_data(data, table_name, columns)


def deactivate_chat_in_sql(chat_id: int, table_name: str = 'chat') -> None:
    """
    Deactivates a chat in the database.

    Args:
        chat_id (int): Chat ID.
        table_name (str, optional): Table name in the DB. Defaults to 'chat'.
    """
    conn.update_data(table_name, 'chat_id', chat_id, 'status', 'deactivated')


def handle_message(update: Update, context: CallbackContext) -> None:
    """
    Processes incoming messages, analyzes mood, and sends alerts if needed.

    Args:
        update (Update): Telegram update object.
        context (CallbackContext): Bot context.
    """
    message = update.message
    if not message:
        return  # Ignore non-text messages

    message_datetime = message.date
    chat_id = message.chat_id
    user = message.from_user
    message_text = message.text

    try:
        query_status_chat = (
            f"SELECT status FROM public.chat "
            f"WHERE chat_id = %s"
        )
        status_chat_data = conn.read_data(query_status_chat, (chat_id,))
        if not status_chat_data:
            context.bot.send_message(
                chat_id=chat_id,
                text="This chat is not set up for mood monitoring. Please contact the administrator for more information."
            )
            return

        status_chat = status_chat_data[0][0]
    except Exception as e:
        logger.error(f"Error checking chat status: {e}")
        context.bot.send_message(
            chat_id=chat_id,
            text="An error occurred while processing your message. Please try again later."
        )
        return

    if status_chat == 'active':
        try:
            message_label, label_score = transformers_mood.predict_sentiment(message_text)
            chat_mood = mood_calculator.calculate_weighted_sentiment(message_label, label_score)

            save_message_to_sql(
                chat_id=chat_id,
                user_id=user.id,
                message_text=message_text,
                message_datetime=message_datetime,
                message_label=message_label,
                label_score=label_score,
                chat_mood=chat_mood
            )

            if message_label == "NEGATIVE" and label_score > 0.65:
                query_chat_id = (
                    f"select user_id, chat_name from public.user_chat "
                    f"join public.chat using(chat_id)"
                    f"WHERE chat_id = %s"
                )
                chat_id_data = conn.read_data(query_chat_id, (chat_id,))
                admin_chat_id = chat_id_data[0][0]
                chat_name = chat_id_data[0][1]
                alert_message = (
                    f"Attention! A negative message detected in chat {chat_id} ({chat_name}):\n\n"
                    f"User: {user.full_name} (@{user.username})\n"
                    f"Message: {message_text}\n"
                    f"Negativity Score: {label_score:.2f}"
                )
                context.bot.send_message(chat_id=admin_chat_id, text=alert_message)

            logger.info(f"User: {user.full_name} (@{user.username})")
            logger.info(f"Message: {message_text}")
            logger.info(f"Label: {message_label}, Score: {label_score}, Mood: {chat_mood}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            context.bot.send_message(
                chat_id=chat_id,
                text="An error occurred while analyzing your message. Please try again later."
            )
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text="This chat is currently not monitored by MoodMeter."
        )
        logger.info(f"Chat with ID {chat_id} is inactive. Message from user {user.full_name} ignored.")


def start(update: Update, context: CallbackContext) -> None:
    """
    Sends a welcome message with instructions.

    Args:
        update (Update): Telegram update object.
        context (CallbackContext): Bot context.
    """
    update.message.reply_text(
        "Hello! Welcome to the MoodMeter bot. Here are the available commands:\n\n"
        "1. /add_user — add your user_id.\n"
        "2. /add_chat chat_id chat_name — add chat to MoodMeter. If name is not provided, it will be empty.\n"
        "3. /deactivate_chat chat_id — remove chat from MoodMeter.\n\n"
        "Important: specify chat_id after the command with a space!"
    )


def add_user_command(update: Update, context: CallbackContext) -> None:
    """
    Handles /add_user command to register a user.

    Args:
        update (Update): Telegram update object.
        context (CallbackContext): Bot context.
    """
    if update.effective_chat.type != 'private':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='This command is available only in private messages.'
        )
        return

    user_id = update.message.from_user.id
    password = hash_password(str(user_id))

    query_user = f"SELECT user_id FROM public.user_credentials WHERE user_id={user_id}"

    try:
        users = conn.read_data_to_dataframe(query_user)

        if users.empty:
            save_user_to_sql(user_id, password)
            update.message.reply_text(f"Your user_id: {user_id} has been successfully registered.")
        else:
            update.message.reply_text(f"Your user_id: {user_id} is already registered.")
    except Exception as e:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='An error occurred while registering the user. Please try again later.'
        )


def add_chat_command(update: Update, context: CallbackContext) -> None:
    """
    Handles /add_chat command to add a chat to the system.

    Args:
        update (Update): Telegram update object.
        context (CallbackContext): Bot context.
    """
    if update.effective_chat.type != 'private':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='This command is available only in private messages.'
        )
        return

    if len(context.args) == 0:
        update.message.reply_text('Please specify chat ID and name after the command.')
        return

    try:
        user_id = update.message.from_user.id
        chat_id = int(context.args[0])
        chat_name = context.args[1] if len(context.args) == 2 else ''
    except ValueError:
        update.message.reply_text('Chat ID must be a number.')
        return

    query_chat = f"SELECT status FROM public.chat WHERE chat_id = {chat_id}"
    chat_data = conn.read_data_to_dataframe(query_chat)

    if chat_data.empty:
        conn.insert_data([(chat_id, 'active', chat_name)], 'chat', ['chat_id', 'status', 'chat_name'])
        save_chat_to_sql(user_id, chat_id)
        update.message.reply_text(f'Chat with ID {chat_id} and name {chat_name} created and activated.')
    else:
        chat_status = chat_data.iloc[0]['status']
        if chat_status == 'deactivated':
            conn.update_data('chat', 'chat_id', chat_id, 'status', 'active')
            update.message.reply_text(f'Chat with ID {chat_id} has been activated.')

        query_user_chat = (
            f"SELECT user_id FROM public.user_chat "
            f"WHERE chat_id = {chat_id} AND user_id = {user_id}"
        )
        user_chat_data = conn.read_data_to_dataframe(query_user_chat)

        if user_chat_data.empty:
            save_chat_to_sql(user_id, chat_id)
            update.message.reply_text(f'You have been added to chat with ID {chat_id}.')
        else:
            update.message.reply_text(f'You are already linked to chat with ID {chat_id}.')


def deactivate_chat_command(update: Update, context: CallbackContext) -> None:
    """
    Handles /deactivate_chat command to remove a chat from the system.

    Args:
        update (Update): Telegram update object.
        context (CallbackContext): Bot context.
    """
    if update.effective_chat.type != 'private':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='This command is available only in private messages.'
        )
        return

    if len(context.args) < 1:
        update.message.reply_text('Please specify chat ID after the command.')
        return

    try:
        user_id = update.message.from_user.id
        chat_id = int(context.args[0])
    except ValueError:
        update.message.reply_text('Chat ID must be a number.')
        return

    query_admin = f"SELECT user_id FROM public.user_chat WHERE chat_id = {chat_id}"
    admin_data = conn.read_data_to_dataframe(query_admin)

    if admin_data.empty or user_id not in admin_data['user_id'].values:
        update.message.reply_text('You are not the administrator of this chat.')
        return

    deactivate_chat_in_sql(chat_id)
    update.message.reply_text(f'Chat with ID {chat_id} has been removed from MoodMeter.')


def rename_chat_command(update: Update, context: CallbackContext) -> None:
    """
    Handles /rename_chat command to rename a chat in the system.

    Args:
        update (Update): Telegram update object.
        context (CallbackContext): Bot context.
    """
    if update.effective_chat.type != 'private':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='This command is available only in private messages.'
        )
        return

    if len(context.args) != 2:
        update.message.reply_text('Please specify chat ID and new name after the command.')
        return

    try:
        user_id = update.message.from_user.id
        chat_id = int(context.args[0])
        new_chat_name = context.args[1]
    except ValueError:
        update.message.reply_text('Chat ID must be a number.')
        return

    query_admin = f"SELECT user_id FROM public.user_chat WHERE chat_id = {chat_id}"
    admin_data = conn.read_data_to_dataframe(query_admin)

    if admin_data.empty or user_id not in admin_data['user_id'].values:
        update.message.reply_text('You are not the administrator of this chat.')
        return

    conn.update_data('chat', 'chat_id', chat_id, 'chat_name', new_chat_name)
    update.message.reply_text(f'Chat with ID {chat_id} has been renamed to {new_chat_name}.')


def main() -> None:
    """
    Initializes the bot and starts processing messages.
    """
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('add_user', add_user_command))
    dispatcher.add_handler(CommandHandler('add_chat', add_chat_command))
    dispatcher.add_handler(CommandHandler('deactivate_chat', deactivate_chat_command))
    dispatcher.add_handler(CommandHandler('rename_chat', rename_chat_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
