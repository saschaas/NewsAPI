from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


class APIResponse(BaseModel):
    """Standard API response wrapper"""
    status: str  # 'success' or 'error'
    data: Optional[Any] = None
    error: Optional[dict] = None
    metadata: dict


class PaginationMetadata(BaseModel):
    """Pagination metadata"""
    page: int
    limit: int
    total_pages: int
    total_items: int
    timestamp: datetime


class ErrorDetail(BaseModel):
    """Error detail"""
    code: str
    message: str
    details: Optional[dict] = None
