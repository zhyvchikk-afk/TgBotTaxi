from os import getenv
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")

DB_USERS = getenv("DB_USERS")
DB_PRICES = getenv("DB_PRICES")
DB_ORDERS = getenv("DB_ORDERS")
DB_COUNTORDERS = getenv("DB_COUNTORDERS")
DB_CAS = getenv("DB_CAS")

ADMIN_ID = int(getenv("ADMIN_ID"))
