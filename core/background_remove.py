from __future__ import annotations

from io import BytesIO

from PIL import Image


class BackgroundRemoveUnavailable(RuntimeError):
    """Raised when rembg is not installed or cannot run."""


class BackgroundRemover:
    def __init__(self, model_name: str = "u2net") -> None:
        self.model_name = model_name
        self._session = None

    def is_available(self) -> bool:
        try:
            import rembg  # noqa: F401
        except ImportError:
            return False
        return True

    def remove(self, image: Image.Image) -> Image.Image:
        try:
            from rembg import new_session, remove
        except ImportError as exc:
            raise BackgroundRemoveUnavailable(
                "rembg is not installed. Install dependencies with: "
                "pip install -r requirements.txt"
            ) from exc

        if self._session is None:
            self._session = new_session(self.model_name)

        input_buffer = BytesIO()
        image.convert("RGBA").save(input_buffer, format="PNG")
        output_bytes = remove(input_buffer.getvalue(), session=self._session)

        with Image.open(BytesIO(output_bytes)) as result:
            return result.convert("RGBA")
