"""
Utility functions for LLM configuration management
"""
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import SystemConfig


def is_vision_model(model_name: str) -> bool:
    """
    Check if a model name indicates a vision/multimodal model

    Args:
        model_name: Model name (e.g., 'llama3.1', 'llama3.2-vision', 'granite3.2-vision')

    Returns:
        True if it's a vision model, False otherwise
    """
    if not model_name:
        return False

    model_lower = model_name.lower()
    vision_keywords = ['vision', 'visual', 'multimodal', 'llava']

    return any(keyword in model_lower for keyword in vision_keywords)


def get_model_for_step(step_name: str) -> str:
    """
    Get the configured LLM model for a specific workflow step

    Args:
        step_name: Name of the workflow step (scraper, analyzer, ner, etc.)

    Returns:
        Model name to use for this step
    """
    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == "llm_config").first()

        if not config:
            # Return default model if config doesn't exist
            return "llama3.1"

        config_data = json.loads(config.value)
        model_assignments = config_data.get("model_assignments", {})

        # Return assigned model or first available model as fallback
        return model_assignments.get(step_name, config_data.get("available_models", ["llama3.1"])[0])

    finally:
        db.close()


def get_available_models() -> list[str]:
    """
    Get list of available LLM models

    Returns:
        List of available model names
    """
    db = SessionLocal()
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == "llm_config").first()

        if not config:
            return ["llama3.1", "mistral", "gemma2"]

        config_data = json.loads(config.value)
        return config_data.get("available_models", ["llama3.1"])

    finally:
        db.close()
