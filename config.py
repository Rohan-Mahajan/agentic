# config.py
from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env

EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# File paths
DEFECTS_CSV = os.getenv("DEFECTS_CSV", "defects.csv")
TEST_CASES_CSV = os.getenv("TEST_CASES_CSV", "test_cases.csv")

# LLM API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
