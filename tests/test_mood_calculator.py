import pytest
from mood_calculator import min_max_normalize, analyze_sentiment, calculate_weighted_sentiment

def test_min_max_normalize():
    assert min_max_normalize(0, 0, 10) == 0
    assert min_max_normalize(5, 0, 10) == 0.5
    assert min_max_normalize(10, 0, 10) == 1
    assert min_max_normalize(15, 10, 20) == 0.5
    assert min_max_normalize(0, -10, 10) == 0.5

def test_analyze_sentiment():
    assert analyze_sentiment('POSITIVE', 1.0) == 1.0
    assert round(analyze_sentiment('POSITIVE', 0.5), 2) == 0.25
    assert analyze_sentiment('NEGATIVE', 1.0) == -1 
    assert round(analyze_sentiment('NEGATIVE', 0.5), 2) == -0.25  
    assert analyze_sentiment('NEUTRAL', 0.8) == 0

def test_calculate_weighted_sentiment():
    assert calculate_weighted_sentiment('POSITIVE', 1.0) == 5.0
    assert calculate_weighted_sentiment('POSITIVE', 0.5) == 3.75
    assert calculate_weighted_sentiment('NEUTRAL', 1.0) == 3.75
    assert calculate_weighted_sentiment('NEUTRAL', 0.5) == 3.125
    assert calculate_weighted_sentiment('NEGATIVE', 1.0) == 0.0
    assert calculate_weighted_sentiment('NEGATIVE', 0.5) == 1.25

if __name__ == "__main__":
    pytest.main()

