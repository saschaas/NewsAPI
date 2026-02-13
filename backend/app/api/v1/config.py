from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, List
import json

from app.database import get_db
from app.models import SystemConfig
from app.services.ollama import ollama_service

router = APIRouter(prefix="/config", tags=["config"])


class LLMConfigUpdate(BaseModel):
    """Request model for updating LLM configuration"""
    model_assignments: Dict[str, str]


class AddModelRequest(BaseModel):
    """Request model for adding a new model"""
    model_name: str


@router.get("/llm")
async def get_llm_config(db: Session = Depends(get_db)):
    """Get current LLM configuration with installed models from Ollama"""
    # Get installed models from Ollama
    models = await ollama_service.list_models()

    if models is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Ollama service"
        )

    # Extract model names
    available_models = [model.get("name", "").replace(":latest", "") for model in models]

    # Get or create config
    config = db.query(SystemConfig).filter(SystemConfig.key == "llm_config").first()

    if not config:
        # Create default configuration with first available model or fallback
        default_model = available_models[0] if available_models else "llama3.1"
        default_config = {
            "model_assignments": {
                "scraper": default_model,
                "link_extractor": default_model,
                "analyzer": default_model,
                "ner": default_model
            }
        }

        config = SystemConfig(
            key="llm_config",
            value=json.dumps(default_config),
            data_type="json",
            description="LLM model configuration for workflow steps"
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    config_data = json.loads(config.value)

    # Always return current installed models from Ollama
    config_data["available_models"] = available_models

    return config_data


@router.put("/llm")
async def update_llm_config(
    config_update: LLMConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update LLM model assignments"""
    config = db.query(SystemConfig).filter(SystemConfig.key == "llm_config").first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM configuration not found"
        )

    config_data = json.loads(config.value)
    config_data["model_assignments"] = config_update.model_assignments

    config.value = json.dumps(config_data)
    db.commit()
    db.refresh(config)

    return json.loads(config.value)


@router.post("/llm/models/pull")
async def pull_model(request: AddModelRequest):
    """
    Pull/download a model from Ollama with streaming progress

    This endpoint streams progress updates as Server-Sent Events
    """
    async def generate():
        async for progress in ollama_service.pull_model(request.model_name):
            yield f"data: {progress}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.delete("/llm/models/{model_name}")
async def delete_model(
    model_name: str,
    db: Session = Depends(get_db)
):
    """
    Delete an LLM model from Ollama

    Note: This removes the model from Ollama. Model assignments using this
    model will automatically fall back to the first available model.
    """
    # Get current models
    models = await ollama_service.list_models()
    if not models:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Ollama service"
        )

    # Check if this is the last model
    if len(models) == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last available model"
        )

    # Delete from Ollama by calling the Ollama API
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{ollama_service.base_url}/api/delete",
                json={"name": model_name}
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete model from Ollama: {response.text}"
                )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting model: {str(e)}"
        )

    # Update config assignments if they were using this model
    config = db.query(SystemConfig).filter(SystemConfig.key == "llm_config").first()
    if config:
        config_data = json.loads(config.value)

        # Get remaining models
        remaining_models = await ollama_service.list_models()
        if remaining_models:
            first_available = remaining_models[0].get("name", "").replace(":latest", "")

            # Update any assignments using the deleted model
            for step, assigned_model in config_data["model_assignments"].items():
                if assigned_model == model_name:
                    config_data["model_assignments"][step] = first_available

            config.value = json.dumps(config_data)
            db.commit()

    return {"message": f"Model {model_name} deleted successfully"}
