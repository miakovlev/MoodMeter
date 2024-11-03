from datetime import datetime, date, timedelta
from typing import List, Optional

import pandas as pd
import plotly.graph_objs as go
import streamlit as st

from lib.postgresql_manager import PostgreSQLConnector
from moodmeter.utils.utils import hash_password, logger

# Инициализация подключения к базе данных
conn = PostgreSQLConnector()

# Словарь для преобразования меток настроения в числовые значения
MOOD_MAP = {
    'POSITIVE': 1,
    'NEGATIVE': -1,
    'NEUTRAL': 0
}


def authenticate_user(username: str, password: str) -> bool:
    """
    Аутентифицирует пользователя, сравнивая захешированный пароль из БД с введенным паролем.

    Args:
        username (str): Имя пользователя.
        password (str): Введенный пароль.

    Returns:
        bool: True, если аутентификация успешна, иначе False.
    """
    query = "SELECT password FROM user_credentials WHERE user_id = %s"
    try:
        result = conn.read_data(query, (username,))
        if result:
            stored_hashed_password = result[0][0]
            return hash_password(password) == stored_hashed_password
        return False
    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        return False


def get_user_id(username: str) -> Optional[int]:
    """
    Получает user_id, связанный с заданным именем пользователя.

    Args:
        username (str): Имя пользователя.

    Returns:
        Optional[int]: user_id, если найден, иначе None.
    """
    query = "SELECT user_id FROM user_credentials WHERE user_id = %s"
    try:
        result = conn.read_data(query, (username,))
        if result:
            return result[0][0]
        return None
    except Exception as e:
        logger.error(f"Error fetching user ID: {e}")
        return None


def get_user_chats(user_id: int) -> List[int]:
    """
    Получает список активных chat_id, связанных с пользователем.

    Args:
        user_id (int): Идентификатор пользователя.

    Returns:
        List[int]: Список chat_id.
    """
    query = """
        SELECT uc.chat_id
        FROM user_chat uc
        JOIN chat c ON uc.chat_id = c.chat_id
        WHERE uc.user_id = %s AND c.status = 'active'
    """
    try:
        result = conn.read_data(query, (user_id,))
        return [row[0] for row in result]
    except Exception as e:
        logger.error(f"Error fetching user chats: {e}")
        return []


def get_cache_key_for_dates(start_date: datetime, end_date: datetime) -> str:
    """
    Возвращает ключ для кэша, который обновляется каждые 5 минут, только если end_date >= сегодня.
    """
    today = datetime.now().date()
    if end_date < today:
        # Если end_date в прошлом, используем постоянный ключ
        return f"historical_data_{start_date}_{end_date}"
    else:
        # Иначе возвращаем ключ, который обновляется каждые 5 минут
        now = datetime.now()
        nearest_5_min = now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond)
        return nearest_5_min.strftime("%Y-%m-%d %H:%M")


@st.cache_data
def load_message_data(chat_id: int, start_date: date, end_date: date, grouping: str, cache_key: str) -> pd.DataFrame:
    """
    Загружает данные сообщений для заданного chat_id с фильтрацией по дате и группировкой.

    Args:
        chat_id (int): Идентификатор чата.
        start_date (date): Начальная дата для фильтрации.
        end_date (date): Конечная дата для фильтрации.
        grouping (str): Интервал группировки ('Hours', 'Days', 'Weeks').

    Returns:
        pd.DataFrame: Датафрейм с данными сообщений.
    """
    # Определение интервала группировки для SQL
    if grouping == 'Hours':
        interval = 'hour'
    elif grouping == 'Days':
        interval = 'day'
    elif grouping == 'Weeks':
        interval = 'week'
    else:
        interval = 'day'  # По умолчанию группировка по дням

    # SQL-запрос с фильтрацией по дате и группировкой
    query = f"""
        SELECT date_trunc('{interval}', message_datetime) AS period, 
               chat_id, 
               AVG(CASE message_label 
                   WHEN 'POSITIVE' THEN 1 
                   WHEN 'NEGATIVE' THEN -1 
                   ELSE 0 END) AS mood_score
        FROM message_analysis
        WHERE chat_id = %s AND message_datetime BETWEEN %s AND %s
        GROUP BY period, chat_id
        ORDER BY period;
    """

    try:
        # Преобразуем даты в datetime
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Выполнение запроса
        data = conn.read_data(query, (chat_id, start_datetime, end_datetime))
        df = pd.DataFrame(data, columns=['date', 'chat_id', 'mood_score'])
        df.set_index('date', inplace=True)

        return df
    except Exception as e:
        logger.error(f"Error loading message data: {e}")
        return pd.DataFrame()


def create_mood_chart(df: pd.DataFrame, grouping: str) -> go.Figure:
    """
    Создает график настроения на основе данных.

    Args:
        df (pd.DataFrame): Данные для графика.
        grouping (str): Интервал группировки.

    Returns:
        go.Figure: Объект графика Plotly.
    """
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df.index,
        y=df['mood_score'].clip(lower=0),
        name='Positive Mood',
        marker_color='green'
    ))

    fig.add_trace(go.Bar(
        x=df.index,
        y=df['mood_score'].clip(upper=0),
        name='Negative Mood',
        marker_color='red'
    ))

    fig.update_layout(
        title=f'Mood over Time ({grouping})',
        xaxis_title='Time',
        yaxis_title='Mood Score',
        showlegend=False,
        plot_bgcolor='white',
        barmode='relative'
    )

    return fig


def login_screen():
    """
    Отображает экран входа и обрабатывает аутентификацию пользователя.
    """
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if authenticate_user(username, password):
            login_callback(username)
        else:
            st.error("Username/password is incorrect")


def login_callback(username):
    st.session_state["authenticated"] = True
    st.session_state["username"] = username
    st.success("Welcome")


def logout_callback():
    st.session_state.clear()
    st.session_state["authenticated"] = False
    st.success("Logged out successfully")


def display_dashboard(user_id: int):
    """
    Отображает дашборд для аутентифицированного пользователя.

    Args:
        user_id (int): Идентификатор пользователя.
    """
    # Добавляем кнопку выхода
    if st.sidebar.button("Logout"):
        logout_callback()

    # Получаем список chat_id для этого пользователя
    user_chats = get_user_chats(user_id)
    if not user_chats:
        st.error("No chats found for this user.")
        return

    # Выбор чата из доступных
    chat_id = st.sidebar.selectbox("Select Chat", options=user_chats)

    # Фильтрация по дате
    st.sidebar.header("Filter by Date")
    start_date = st.sidebar.date_input("Start date", value=date.today())
    end_date = st.sidebar.date_input("End date", value=date.today())

    # Проверка корректности дат
    if start_date > end_date:
        st.error("Start date cannot be after end date.")
        return

    # Выбор интервала группировки
    grouping = st.sidebar.selectbox(
        'Choose interval for grouping:',
        ['Hours', 'Days', 'Weeks']
    )

    # Загружаем данные сообщений для выбранного чата с фильтрацией и группировкой
    cache_key = get_cache_key_for_dates(start_date, end_date)
    df = load_message_data(chat_id, start_date, end_date, grouping, cache_key)

    if df.empty:
        st.warning("No data available for the selected chat.")
        fig = go.Figure()
        st.title("Mood grouping by time interval")
        st.plotly_chart(fig)
    else:
        # Создаем график
        fig = create_mood_chart(df, grouping)
        st.markdown(f"<h3>Mood grouping by {grouping.lower()}</h3>", unsafe_allow_html=True)
        st.plotly_chart(fig)


def main():
    """
    Главная функция приложения.
    """
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        login_screen()
    else:
        user_id = get_user_id(st.session_state["username"])
        if user_id is None:
            st.error("User ID not found.")
        else:
            display_dashboard(user_id)


if __name__ == "__main__":
    main()
