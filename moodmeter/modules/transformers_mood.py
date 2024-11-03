from transformers import pipeline


sentiment_pipeline = pipeline("sentiment-analysis",
                              model="blanchefort/rubert-base-cased-sentiment-rurewiews")


def predict_sentiment(message):
    """
    Predicts the sentiment of a given message.
    Utilizes a pre-trained model for sentiment analysis, returning the label
    and confidence score of the predicted sentiment.

    Args:
        message (str): The text message to analyze.

    Returns:
        tuple: A tuple containing the label ('POSITIVE', 'NEGATIVE', or 'NEUTRAL')
        and the confidence score (float).
    """

    sentiment = sentiment_pipeline(message)[0]
    label = sentiment['label']
    score = sentiment['score']
    return label, score
