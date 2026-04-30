"""
Database models for BookMaker multi-user application
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

class User(Base):
    """User model for authentication"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    affiliation = Column(String(255), nullable=True)  # 소속
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Project(Base):
    """Project model to store book creation projects"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    book_idea = Column(Text, nullable=False)
    master_prompt_template = Column(String(500), nullable=True)  # Path or name of template used
    adapted_prompt = Column(Text, nullable=True)
    user_feedback = Column(Text, nullable=True)  # User feedback on the plan before proceeding
    generated_content = Column(Text, nullable=True)  # Generated English book content
    conversation_history = Column(Text, nullable=True)  # JSON array of user-AI conversation for iterative refinement
    model_used = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    stage = Column(String(50), nullable=True, default=None)  # Current workflow stage (1단계, 2단계, etc.)
    stage_status = Column(String(50), nullable=True, default=None)  # Status: pending, in_progress, completed, error
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    owner = relationship("User", back_populates="projects")
    logs = relationship("ProgressLog", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class ProgressLog(Base):
    """Progress log model to track book creation progress"""
    __tablename__ = "progress_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    stage = Column(String(50), nullable=False)  # Which stage this log belongs to
    message = Column(Text, nullable=False)
    level = Column(String(20), default="info")  # info, warning, error, success
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    project = relationship("Project", back_populates="logs")

    def __repr__(self):
        return f"<ProgressLog(id={self.id}, project_id={self.project_id}, stage='{self.stage}')>"


class UserSettings(Base):
    """User settings for LLM configuration"""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    llm_provider = Column(String(50), default="groq")  # groq, openai, deepseek, etc.
    llm_model = Column(String(100), default="llama-3.3-70b-versatile")
    translation_system_prompt = Column(Text, default="""You are a professional Korean translator specializing in educational books.

TRANSLATION GUIDELINES:
- Translate all English text to natural, fluent Korean (한글)
- Use formal Korean style (존댓말/합쇼체)
- Keep technical terms in English with Korean explanation in parentheses when first introduced
- Preserve all markdown formatting (##, **, -, code blocks, etc.)
- Keep code examples in English but translate comments to Korean
- Maintain the educational tone suitable for Korean readers
- Do NOT add any translator notes or explanations outside the content
- Do NOT output Chinese characters under any circumstances
- Do NOT include random code snippets that are not part of the original content""")
    temperature = Column(String(10), default="0.3")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", backref="settings")

    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, model='{self.llm_model}')>"


# Database setup
DATABASE_URL = "sqlite:///./bookmaker.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
