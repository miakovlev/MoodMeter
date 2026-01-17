# MoodMeter: Sentiment Analysis in Telegram Chat

![Example Image:](images/screenshot.png)

## Description

MoodMeter is a chat sentiment analysis system that uses machine learning to classify user messages as positive, neutral, or negative. The project is developed using Python, Hugging Face Transformers, PostgreSQL (e.g., Heroku Postgres), and Streamlit.

## Goals

* Develop a chat sentiment analysis system.
* Classify user messages into three categories.
* Visualize analysis results using interactive dashboards.

## Architecture

* **Data Collection**
  * The system receives user messages from the chat via an API (e.g., Telegram webhook).
  * Message data (text, author, timestamp) is stored in PostgreSQL.
* **Sentiment Analysis**
  * A pretrained model, `blanchefort/rubert-base-cased-sentiment-rurewiews` from Hugging Face Transformers, is used.
  * The model classifies each message as positive, neutral, or negative.
* **Data Storage**
  * PostgreSQL stores messages and analysis results.
* **Data Visualization**
  * Streamlit creates interactive dashboards visualizing the analysis results.

## Components

* **Data Collection**
  * API integration for retrieving messages from the chat.
  * Data storage in PostgreSQL.
* **Sentiment Analysis**
  * Uses the `blanchefort/rubert-base-cased-sentiment-rurewiews` model from Hugging Face Transformers.
  * Classifies messages based on the model.
* **Data Storage**
  * Creates tables in PostgreSQL to store message and analysis data.
* **Data Visualization**
  * Builds interactive dashboards in Streamlit using Plotly.

## Technical Details

* **Python**: Programming language for implementing the system.
* **Hugging Face Transformers**: Library for pretrained NLP models.
* **PostgreSQL**: Database for data storage.
* **Streamlit**: Tool for creating a web service with interactive dashboards.

## Run in 2 Commands (Docker Compose)

```bash
cp .env.example .env
# Update .env with your credentials

docker-compose up --build
```

Then open the dashboard at http://localhost:8501.

## Installation Instructions (Local)

### 1. Clone the Repository

```bash
git clone https://github.com/username/MoodMeter.git
cd MoodMeter
```

### 2. Install Python 3.11

```bash
sudo apt install python3.11
python3 --version  # Confirm that version 3.11 is installed
```

### 3. Install System Dependencies

```bash
sudo apt install libpq-dev python3-dev
```

### 4. Create and Activate a Virtual Environment

```bash
python3.11 -m venv myenv
source myenv/bin/activate
```

### 5. Install Python Dependencies

```bash
pip install -r requirements-bot.txt
pip install -r requirements-streamlit.txt
```

### 6. Configure Environment

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

**Environment variables**

| Variable | Description | Example |
| --- | --- | --- |
| `HOST` | PostgreSQL host | `ec2-00-00-00-00.compute-1.amazonaws.com` |
| `DATABASE` | PostgreSQL database name | `moodmeter` |
| `USERSQL` | PostgreSQL username | `db_user` |
| `PASSWORD` | PostgreSQL password | `strong-password` |
| `TELEGRAM_TOKEN` | Telegram bot token from BotFather | `123456789:ABCDEF...` |
| `ADMIN_CHAT_ID` | Telegram chat ID for admin notifications | `123456789` |

### 7. Run the Application

```bash
streamlit run moodmeter/services/dashboard.py
```

### 8. Run the Bot

```bash
python3 moodmeter/services/telegram_bot.py
```

## Usage Examples

* The system can be used for monitoring customer sentiment in support chats.
* It can help identify topics that cause negative emotions among users.
* Data visualization allows for quick information analysis and data-driven decision making.
