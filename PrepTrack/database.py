from sqlalchemy import Column, Date, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./preptrack.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ProblemDB(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    difficulty = Column(String(20), nullable=False)
    topic = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    notes = Column(String, nullable=True)
    last_solved_date = Column(Date, nullable=True)
    revision_reminder = Column(Date, nullable=True)
