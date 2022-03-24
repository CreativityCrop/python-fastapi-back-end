from databases import Database

from app.config import DB_NAME, DB_PASS, DB_USER, DB_HOST

DB_URL = f'mysql+asyncmy://{DB_USER}:{DB_PASS}@{DB_HOST}:3306/{DB_NAME}'

database = Database(DB_URL)
