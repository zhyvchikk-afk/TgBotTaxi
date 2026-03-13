from os import getenv
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = getenv("BOT_TOKEN")

DB_USERS = getenv("DB_USERS")
DB_PRICES = getenv("DB_PRICES")
DB_ORDERS = getenv("DB_ORDERS")
DB_CAS = getenv("DB_CAS")

ADMIN_ID = int(getenv("ADMIN_ID"))
ADMIN_USERNAME = getenv("ADMIN_USERNAME")

MY_COMPUTER = int(getenv("MY_COMPUTER"))
KRISTINA = int(getenv("KRISTINA"))
EUGENE = int(getenv("EUGENE"))
KOSTYA_LIFE = int(getenv("KOSTYA_LIFE"))
