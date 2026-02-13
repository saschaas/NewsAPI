from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class LLMCache(Base):
    __tablename__ = "llm_cache"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    content_hash = Column(String, nullable=False, unique=True, index=True)
    model_name = Column(String, nullable=False)
    prompt_type = Column(String, nullable=False, index=True)
    response_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    last_used_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    use_count = Column(Integer, default=1)
