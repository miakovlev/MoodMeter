import pytest
from dashboard import authenticate_user, get_user_id, get_user_chats, load_message_data
from unittest.mock import patch

@patch("dashboard.PostgreSQLConnector.read_data")
def test_get_user_id(mock_read_data):
    mock_read_data.return_value = [(123,)]
    
    assert get_user_id("username") == 123

@patch("dashboard.PostgreSQLConnector.read_data")
def test_get_user_chats(mock_read_data):
    mock_read_data.return_value = [(1,), (2,)]
    
    assert get_user_chats(123) == [1, 2]

@patch("dashboard.PostgreSQLConnector.read_data")
def test_load_message_data(mock_read_data):
    mock_read_data.return_value = [("2023-10-01", 1, "POSITIVE")]
    
    df = load_message_data(1)
    assert not df.empty
    assert df["label_value"].iloc[0] == 1
