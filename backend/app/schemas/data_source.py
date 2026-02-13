from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, Literal
from datetime import datetime


class DataSourceBase(BaseModel):
    """Base schema for data source"""
    name: str
    url: str
    source_type: Literal['website', 'youtube']
    fetch_frequency_minutes: int = 60
    cron_expression: Optional[str] = None
    config_json: Optional[str] = None
    extraction_instructions: Optional[str] = None


class DataSourceCreate(DataSourceBase):
    """Schema for creating a data source"""
    pass

    @field_validator('fetch_frequency_minutes')
    @classmethod
    def validate_frequency(cls, v):
        if v < 1:
            raise ValueError('Frequency must be at least 1 minute')
        return v


class DataSourceUpdate(BaseModel):
    """Schema for updating a data source"""
    name: Optional[str] = None
    url: Optional[str] = None
    fetch_frequency_minutes: Optional[int] = None
    cron_expression: Optional[str] = None
    config_json: Optional[str] = None
    extraction_instructions: Optional[str] = None
    status: Optional[Literal['active', 'paused', 'deleted']] = None


class DataSourceStatusUpdate(BaseModel):
    """Schema for updating data source status"""
    status: Literal['active', 'paused']


class DataSourceResponse(DataSourceBase):
    """Schema for data source response"""
    id: int
    status: Literal['active', 'paused', 'deleted']
    health_status: Literal['healthy', 'pending', 'error']
    last_fetch_timestamp: Optional[datetime] = None
    last_fetch_status: Optional[Literal['success', 'error', 'captcha', 'timeout']] = None
    error_message: Optional[str] = None
    error_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DataSourceListResponse(BaseModel):
    """Schema for list of data sources"""
    sources: list[DataSourceResponse]
    total: int
