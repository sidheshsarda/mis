import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from dotenv import load_dotenv
load_dotenv()
# /C:/code/mis/db.py


# --------------------------------------------------------------------------- #
# URL builder                                                                 #
# --------------------------------------------------------------------------- #
DEFAULT_MYSQL_DRIVER = "mysql+pymysql"
DEFAULT_MYSQL_PORT = "3306"


@lru_cache(maxsize=1)
def get_database_url() -> str:
    """
    Build the SQLAlchemy URL from environment variables.

    Raises:
        ValueError: If any required variable is missing.
    """
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", DEFAULT_MYSQL_PORT)
    db_name = os.getenv("DB_NAME")
    db_driver = os.getenv("DB_DRIVER", DEFAULT_MYSQL_DRIVER)

    missing = [
        name
        for name, value in {
            "DB_USER": db_user,
            "DB_PASSWORD": db_password,
            "DB_HOST": db_host,
            "DB_NAME": db_name,
        }.items()
        if not value
    ]

    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    return (
        f"{db_driver}://{db_user}:{db_password}"
        f"@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    )

# --------------------------------------------------------------------------- #
# Engine / Session / Base                                                     #
# --------------------------------------------------------------------------- #
DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # recycle disconnected connections
    pool_recycle=280,        # avoid MySQL “gone away”
    echo=False,              # set True for SQL logging
    future=True,
)

SessionLocal = scoped_session(
    sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
)

Base = declarative_base()


# --------------------------------------------------------------------------- #
# Small dependency helper (e.g. FastAPI)                                      #
# --------------------------------------------------------------------------- #
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()