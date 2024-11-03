import pytest
from transformers_mood import predict_sentiment

@pytest.mark.parametrize("message, expected_label", [
    ("Я люблю тебя!", "POSITIVE"),
    ("Ты ужасен!", "NEGATIVE"),
    ("Это нормальное сообщение", "NEUTRAL")
])
def test_predict_sentiment(message, expected_label):
    label, _ = predict_sentiment(message)
    assert label == expected_label