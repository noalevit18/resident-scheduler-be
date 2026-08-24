from logging.config import fileConfig
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool

# Add the project root (resident-scheduler-be) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base
from app.models.models import * # Import all models so they register with Base.metadata

from alembic import context

target_metadata = Base.metadata

env_path = os.path.join(os.path.dirname(__file__), '..', 'app', '.env')

load_dotenv(env_path)
USER = os.getenv("POSTGRES_USER")
PASSWORD = os.getenv("POSTGRES_PASSWORD")
HOST = os.getenv("POSTGRES_HOST")
PORT = os.getenv("POSTGRES_PORT")
DB_NAME = os.getenv("POSTGRES_DB_NAME")
database_url = f"postgresql+psycopg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}?sslmode=require"

if not USER:
    raise ValueError("DATABASE_USER not found in environment variables. Check your .env file.")
if not PASSWORD:
    raise ValueError("DATABASE_PASSWORD not found in environment variables. Check your .env file.")
if not HOST:
    raise ValueError("DATABASE_HOST not found in environment variables. Check your .env file.")
if not PORT:
    raise ValueError("DATABASE_PORT not found in environment variables. Check your .env file.")
if not DB_NAME:
    raise ValueError("DATABASE_DB_NAME not found in environment variables. Check your .env file.")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url", database_url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # Create the engine directly using the URL
    # prepare_threshold=None disables server-side prepared statements, which
    # Supabase's transaction-mode pooler (pgbouncer/Supavisor) does not support
    # and which otherwise causes "DuplicatePreparedStatement" errors during
    # autogenerate's heavy schema introspection. Mirrors app/database.py.
    connectable = create_engine(database_url, connect_args={"prepare_threshold": None})
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

