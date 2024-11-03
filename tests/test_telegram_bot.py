import os
from datetime import datetime
import pytest
from unittest.mock import patch, MagicMock
from telegram import Update
from telegram.ext import CallbackContext
from telegram_bot import (
    save_message_to_sql,
    save_user_to_sql,
    add_user_command,
    handle_message
)
from lib.postgresql_manager import PostgreSQLConnector
from utils.utils import hash_password

# Фикстуры для тестирования
@pytest.fixture
def mock_postgresql_connector():
    """Создает фиктивный объект PostgreSQLConnector."""
    mock_conn = MagicMock()
    return mock_conn

@pytest.fixture
def update():
    """Создает фиктивный объект update для тестов."""
    class FakeUpdate:
        def __init__(self):
            self.message = self.FakeMessage()
            self.effective_chat = self.FakeChat(chat_id=self.message.chat_id)

        class FakeMessage:
            def __init__(self):
                self.chat_id = 123
                self.from_user = self.FakeUser()
                self.text = "Привет!"
                self.date = datetime.now()

                # Замокаем метод reply_text
                self.reply_text = MagicMock()

            class FakeUser:
                def __init__(self):
                    self.id = 456
                    self.full_name = "Тестовый Пользователь"
                    self.username = "testuser"

        class FakeChat:
            def __init__(self, chat_id):
                self.id = chat_id
                self.type = 'private'

    return FakeUpdate()



@pytest.fixture
def context():
    """Создает фиктивный объект context для тестов."""
    class FakeContext:
        def __init__(self):
            self.bot = MagicMock()

    return FakeContext()

@patch.object(PostgreSQLConnector, 'insert_data')
def test_save_message_to_sql(mock_insert_data, mock_postgresql_connector):
    # Патчинг класса для использования фиктивного соединения
    with patch('telegram_bot.PostgreSQLConnector', return_value=mock_postgresql_connector):
        save_message_to_sql(
            chat_id=123,
            user_id=456,
            message_text="Тестовое сообщение",
            message_label="POSITIVE",
            label_score=0.85,
            chat_mood=0.75,
            message_datetime=datetime.now()
        )

        # Проверяем, что метод insert_data был вызван
        mock_insert_data.assert_called_once()

@patch.object(PostgreSQLConnector, 'insert_data')
def test_save_user_to_sql(mock_insert_data, mock_postgresql_connector):
    with patch('telegram_bot.PostgreSQLConnector', return_value=mock_postgresql_connector):
        save_user_to_sql(
            user_id=456,
            password="hashed_password"
        )

        # Проверяем, что метод insert_data был вызван
        mock_insert_data.assert_called_once()

@patch("telegram_bot.PostgreSQLConnector")
def test_add_user_invalid_chat_type(mock_postgresql_connector, update, context):
    """Тестируем случай, когда команда вызвана не в личных сообщениях."""
    update.effective_chat.type = 'group'

    add_user_command(update, context)

    # Проверяем, что отправлено сообщение о недоступности команды
    context.bot.send_message.assert_called_once_with(
        chat_id=update.effective_chat.id,
        text='Эта команда доступна только в личных сообщениях.'
    )
    
@patch("telegram_bot.PostgreSQLConnector")
def test_add_user_already_registered(mock_postgresql_connector, update, context):
    """Тестируем случай, когда пользователь уже зарегистрирован."""
    # Мокируем метод для чтения данных, чтобы возвращал зарегистрированного пользователя
    mock_postgresql_connector.return_value.read_data_to_dataframe.return_value = MagicMock(empty=lambda: False)

    add_user_command(update, context)

    # Проверяем, что пользователю отправлено сообщение о том, что он уже зарегистрирован
    update.message.reply_text.assert_called_once_with("Ваш user_id: 456 уже зарегистрирован в системе.")


@patch("telegram_bot.PostgreSQLConnector")
def test_handle_message_inactive_chat(mock_conn, update, context):
    # Настройка: чат не активен
    mock_conn.return_value.read_data.return_value = [("inactive",)]

    handle_message(update, context)

    context.bot.send_message.assert_called_once_with(
        chat_id=update.message.chat_id,
        text="Этот чат не настроен для мониторинга настроений. Пожалуйста, свяжитесь с администратором для получения дополнительной информации."
    )
