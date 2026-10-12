from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./vyaparflow.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def ensure_workflow_columns():
    """Apply the two additive columns needed by pre-migration local databases."""
    existing = {column["name"] for column in inspect(engine).get_columns("workflows")}
    additions = {
        "normalized_text": "TEXT",
        "field_confidence": "JSON",
    }
    with engine.begin() as connection:
        for name, column_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE workflows ADD COLUMN {name} {column_type}"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
