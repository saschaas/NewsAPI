from pydantic import BaseModel
from typing import Literal, Any, Optional


class SystemConfigResponse(BaseModel):
    """Schema for system configuration"""
    key: str
    value: str
    data_type: Literal['string', 'integer', 'float', 'boolean', 'json']
    description: Optional[str] = None

    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    """Schema for updating system configuration"""
    configs: dict[str, Any]


class GlobalPauseUpdate(BaseModel):
    """Schema for updating global pause"""
    paused: bool


class HealthCheckResponse(BaseModel):
    """Schema for health check response"""
    status: str
    timestamp: str
    database: str
    ollama: str


class SystemStatusResponse(BaseModel):
    """Schema for system status"""
    active_sources: int
    paused_sources: int
    total_articles: int
    processing_queue_size: int
    global_pause: bool
    ollama_status: str
