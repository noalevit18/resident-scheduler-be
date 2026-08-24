from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os
from dotenv import load_dotenv


load_dotenv()

USER = os.getenv("POSTGRES_USER")
PASSWORD = os.getenv("POSTGRES_PASSWORD")
HOST = os.getenv("POSTGRES_HOST")
PORT = os.getenv("POSTGRES_PORT")
DBNAME = os.getenv("POSTGRES_DB_NAME")

DATABASE_URL = f"postgresql+psycopg://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"



engine = create_engine(
    DATABASE_URL,
    connect_args={"prepare_threshold": None},
    pool_pre_ping=True
)

# expire_on_commit=False: keep ORM objects' attributes populated after commit
# instead of marking them all stale. Postgres/psycopg already returns
# server-generated values (UUID PKs, created_at/updated_at) via an implicit
# RETURNING clause on INSERT/UPDATE, so without this flag every create/update
# repository method needed an extra explicit `db.refresh()` round trip just to
# re-fetch what the DB had already returned — doubling/tripling write latency.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
