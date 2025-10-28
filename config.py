﻿import os
from dotenv import load_dotenv

load_dotenv()

DEBUG = os.getenv('DEBUG', 'True').lower() in ('1', 'true', 'yes')

API_URL = os.getenv('API_URL')
BOT_TOKEN = os.getenv('BOT_TOKEN')

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

ACCESS_EXPIRES_IN = int(os.getenv('ACCESS_EXPIRES_IN'))
REFRESH_EXPIRES_IN = int(os.getenv('REFRESH_EXPIRES_IN'))
PARSE_MODE = os.getenv('PARSE_MODE', 'HTML')
