import json

def min_max_normalize(value, min_value, max_value):
    """
    Normalizes a value within a specified minimum and maximum range.
    Applies min-max normalization to the given value.

    Args:
        value (float): The value to normalize.
        min_value (float): The minimum possible value.
        max_value (float): The maximum possible value.

    Returns:
        float: The normalized value within the range [0, 1].
    """

    return (value - min_value) / (max_value - min_value)

def analyze_sentiment(label, score):
    """
    Analyzes sentiment based on the label and confidence score.
    Converts the sentiment score into a normalized mood indicator.

    Args:
        label (str): The sentiment label ('POSITIVE', 'NEGATIVE', 'NEUTRAL').
        score (float): The confidence score of the predicted sentiment.

    Returns:
        float: A normalized mood indicator ranging from -1 to 1.
     """


    if label == 'NEGATIVE':
        return -min_max_normalize(score, 0.333, 1)
    elif label == 'POSITIVE':
        return min_max_normalize(score, 0.333, 1)
    else:
        return 0

def calculate_weighted_sentiment(new_message_category, new_message_score):
    """
    Calculates the weighted sentiment for a new message.
    Computes the weighted sentiment based on the current and previous messages.

    Args:
        new_message_category (str): The category of the new message ('POSITIVE', 'NEGATIVE', 'NEUTRAL').
        new_message_score (float): The confidence score of the new message's sentiment.

    Returns:
        float: The weighted sentiment score, normalized to a range from 0 to 5.
    """

    if new_message_category == 'POSITIVE':
        default_weighted_score = new_message_score
    elif new_message_category == 'NEUTRAL':
        default_weighted_score = 0.5 * new_message_score
    else:
        default_weighted_score = -1 * new_message_score

    return (default_weighted_score + 1) * 2.5