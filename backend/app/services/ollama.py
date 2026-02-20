import httpx
import json
from typing import Optional, Dict, Any
from loguru import logger

from app.config import settings


class OllamaService:
    """Service for interacting with Ollama API"""

    def __init__(self):
        self.base_url = settings.OLLAMA_HOST
        self.timeout = settings.OLLAMA_TIMEOUT

    async def check_health(self) -> bool:
        """Check if Ollama is accessible"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        format: Optional[str] = "json",
        images: Optional[list[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate completion from Ollama (supports both text and vision models)

        Args:
            prompt: User prompt
            model: Model name (e.g., 'llama3.1', 'llama3.2-vision')
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            format: Response format ('json' or None)
            images: Optional list of base64-encoded images (for vision models)

        Returns:
            Response dict or None if error
        """
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature
                }
            }

            if system_prompt:
                payload["system"] = system_prompt

            if format:
                payload["format"] = format

            # Add images for vision models
            if images:
                payload["images"] = images

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )

                if response.status_code != 200:
                    logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                    return None

                result = response.json()

                # Parse JSON response if format is json
                if format == "json":
                    raw = result.get("response", "")
                    try:
                        result["response"] = json.loads(raw)
                    except json.JSONDecodeError:
                        # LLMs sometimes wrap JSON in markdown fences or add trailing text
                        cleaned = self._extract_json(raw)
                        if cleaned is not None:
                            result["response"] = cleaned
                        else:
                            logger.error(f"Failed to parse JSON response: {raw[:500]}")
                            return None

                return result

        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return None

    @staticmethod
    def _extract_json(text: str):
        """Try to extract valid JSON from a string that may contain extra text.

        Handles common LLM issues: markdown fences, leading/trailing text,
        arrays inside objects, etc.
        """
        import re

        # Strip markdown code fences
        text = re.sub(r'^```(?:json)?\s*', '', text.strip())
        text = re.sub(r'\s*```$', '', text.strip())

        # Try parsing the cleaned text directly
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find the first { or [ and last } or ]
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue

        return None

    async def list_models(self) -> Optional[list]:
        """
        Get list of installed models from Ollama

        Returns:
            List of model dictionaries with name, size, etc.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")

                if response.status_code != 200:
                    logger.error(f"Failed to list models: {response.status_code}")
                    return None

                data = response.json()
                return data.get("models", [])
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return None

    async def pull_model(self, model_name: str):
        """
        Pull/download a model from Ollama registry with streaming progress

        Args:
            model_name: Name of the model to pull

        Yields:
            Progress updates as JSON strings
        """
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": True}
                ) as response:
                    if response.status_code != 200:
                        error_msg = await response.aread()
                        logger.error(f"Failed to pull model: {response.status_code} - {error_msg}")
                        yield json.dumps({"error": f"Failed to pull model: {error_msg.decode()}"})
                        return

                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                yield json.dumps(data)
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse pull progress: {line}")
        except Exception as e:
            logger.error(f"Error pulling model: {e}")
            yield json.dumps({"error": str(e)})

    async def transcribe_audio(
        self,
        audio_path: str,
        model: str = None
    ) -> Optional[str]:
        """
        Transcribe audio file using Whisper via Ollama

        Args:
            audio_path: Path to audio file
            model: Whisper model name (default from config)

        Returns:
            Transcribed text or None if error
        """
        if model is None:
            model = settings.OLLAMA_MODEL_WHISPER

        try:
            # Read audio file
            with open(audio_path, 'rb') as f:
                audio_data = f.read()

            # Note: This is a placeholder - Ollama's Whisper integration
            # may require a different API endpoint. Adjust based on actual implementation.
            # For now, we'll use a generate call with a transcription prompt

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Check if there's a specific transcription endpoint
                # Otherwise, fall back to using whisper model with generate
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": f"Transcribe this audio file: {audio_path}",
                        "stream": False
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "")
                else:
                    logger.error(f"Transcription failed: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None


# Singleton instance
ollama_service = OllamaService()
