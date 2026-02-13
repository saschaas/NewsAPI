from sqlalchemy import Column, String, DateTime, Text, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    data_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "data_type IN ('string', 'integer', 'float', 'boolean', 'json')",
            name='check_data_type'
        ),
    )
