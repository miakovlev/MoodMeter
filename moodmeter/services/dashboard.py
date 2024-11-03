from datetime import datetime, date, timedelta
from typing import List, Optional

import pandas as pd
import plotly.graph_objs as go
import streamlit as st

from lib.postgresql_manager import PostgreSQLConnector
from moodmeter.utils.utils import hash_password, logger

# Initialize database connection
conn = PostgreSQLConnector()

# Mapping mood labels to numeric values
MOOD_MAP = {
    'POSITIVE': 1,
    'NEGATIVE': -1,
    'NEUTRAL': 0
}


def authenticate_user(username: str, password: str) -> bool:
    """
    Authenticates the user by comparing the hashed password from the DB with the entered password.

    Args:
        username (str): Username.
        password (str): Entered password.

    Returns:
        bool: True if authentication is successful, otherwise False.
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
    Retrieves the user_id associated with the given username.

    Args:
        username (str): Username.

    Returns:
        Optional[int]: user_id if found, otherwise None.
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
    Retrieves a list of active chat_ids associated with the user.

    Args:
        user_id (int): User identifier.

    Returns:
        List[int]: List of chat_ids.
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
    Returns a cache key that updates every 5 minutes, only if end_date >= today.
    """
    today = datetime.now().date()
    if end_date < today:
        return f"historical_data_{start_date}_{end_date}"
    else:
        now = datetime.now()
        nearest_5_min = now - timedelta(minutes=now.minute % 5, seconds=now.second, microseconds=now.microsecond)
        return nearest_5_min.strftime("%Y-%m-%d %H:%M")


@st.cache_data
def load_message_data(chat_id: int, start_date: date, end_date: date, grouping: str, cache_key: str) -> pd.DataFrame:
    """
    Loads message data for the specified chat_id with date filtering and grouping.

    Args:
        chat_id (int): Chat identifier.
        start_date (date): Start date for filtering.
        end_date (date): End date for filtering.
        grouping (str): Grouping interval ('Hours', 'Days', 'Weeks').

    Returns:
        pd.DataFrame: DataFrame with message data.
    """
    if grouping == 'Hours':
        interval = 'hour'
    elif grouping == 'Days':
        interval = 'day'
    elif grouping == 'Weeks':
        interval = 'week'
    else:
        interval = 'day'

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
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        data = conn.read_data(query, (chat_id, start_datetime, end_datetime))
        df = pd.DataFrame(data, columns=['date', 'chat_id', 'mood_score'])
        df.set_index('date', inplace=True)

        return df
    except Exception as e:
        logger.error(f"Error loading message data: {e}")
        return pd.DataFrame()


def create_mood_chart(df: pd.DataFrame, grouping: str) -> go.Figure:
    """
    Creates a mood chart based on the data.

    Args:
        df (pd.DataFrame): Data for the chart.
        grouping (str): Grouping interval.

    Returns:
        go.Figure: Plotly chart object.
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
    Displays the login screen and handles user authentication.
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
    Displays the dashboard for the authenticated user.

    Args:
        user_id (int): User identifier.
    """
    if st.sidebar.button("Logout"):
        logout_callback()

    user_chats = get_user_chats(user_id)
    if not user_chats:
        st.error("No chats found for this user.")
        return

    chat_id = st.sidebar.selectbox("Select Chat", options=user_chats)

    st.sidebar.header("Filter by Date")
    start_date = st.sidebar.date_input("Start date", value=date.today())
    end_date = st.sidebar.date_input("End date", value=date.today())

    if start_date > end_date:
        st.error("Start date cannot be after end date.")
        return

    grouping = st.sidebar.selectbox(
        'Choose interval for grouping:',
        ['Hours', 'Days', 'Weeks']
    )

    cache_key = get_cache_key_for_dates(start_date, end_date)
    df = load_message_data(chat_id, start_date, end_date, grouping, cache_key)

    if df.empty:
        st.warning("No data available for the selected chat.")
        fig = go.Figure()
        st.title("Mood grouping by time interval")
        st.plotly_chart(fig)
    else:
        fig = create_mood_chart(df, grouping)
        st.markdown(f"<h3>Mood grouping by {grouping.lower()}</h3>", unsafe_allow_html=True)
        st.plotly_chart(fig)


def main():
    """
    Main function of the application.
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
