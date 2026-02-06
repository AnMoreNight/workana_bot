"""
Translation utility for translating job descriptions without requiring an API key.

Currently implemented using `deep-translator`'s GoogleTranslator, which:
- Does *not* need an explicit API key
- Auto-detects source language
"""
from typing import Optional

try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None  # type: ignore


class DeepLTranslator:
    """
    Backwards‑compatible translator wrapper used across the project.

    NOTE: Even though the class name mentions "DeepL", the implementation now
    uses `deep-translator` (GoogleTranslator) so that it can work without any
    API key. The public methods / interface are kept the same so other modules
    (Slack, main script) do not need to change.
    """

    def __init__(self, *_args, **_kwargs):
        """
        Initialize translator.

        No API key is required. If `deep-translator` is not installed or
        initialization fails, `is_available()` will return False and all
        translation calls will safely fall back.
        """
        self.translator = None

        if GoogleTranslator is None:
            print("⚠️  Warning: deep-translator is not installed; translation disabled")
            return

        try:
            # Use auto source language, target English.
            self.translator = GoogleTranslator(source="auto", target="en")
        except Exception as e:
            print(f"⚠️  Warning: Could not initialize translator (deep-translator): {e}")
            self.translator = None

    def is_available(self) -> bool:
        """Check if translator is available."""
        return self.translator is not None

    def translate_text(
        self,
        text: str,
        target_lang: str = "EN-US",
        source_lang: str = None,  # kept for compatibility; ignored
    ) -> Optional[str]:
        """
        Translate text to target language (currently English).

        Args:
            text: Text to translate
            target_lang: Target language code (kept for compatibility; any
                         English variant like 'en', 'en-us' is treated as English)
            source_lang: Ignored (auto-detected by GoogleTranslator)

        Returns:
            Translated text or None if translation fails
        """
        if not self.translator:
            return None

        if not text or not text.strip():
            return text

        # For now we always translate to English; normalize target_lang just in case.
        try:
            # Recreate translator if target differs and is supported,
            # but default to English to avoid surprises.
            target = "en"
            if isinstance(target_lang, str) and target_lang:
                tl = target_lang.lower()
                if tl.startswith("es"):
                    target = "es"
                elif tl.startswith("pt"):
                    target = "pt"
                elif tl.startswith("de"):
                    target = "de"
                elif tl.startswith("fr"):
                    target = "fr"
                else:
                    target = "en"

            if getattr(self.translator, "target", None) != target:
                self.translator = GoogleTranslator(source="auto", target=target)

            return self.translator.translate(text)
        except Exception as e:
            print(f"⚠️  Translation error (deep-translator): {e}")
            return None

    def translate_job_description(self, description: str) -> Optional[str]:
        """
        Translate job description to English.

        Returns original description if translation fails or translator is disabled.
        """
        if not description:
            return description

        translated = self.translate_text(description, target_lang="EN-US")
        return translated if translated else description

    def translate_job_data(self, job_data: dict) -> dict:
        """
        Translate job data fields (title, description) to English.

        Returns:
            Job data with translated fields (or original values on failure).
        """
        if not self.translator:
            return job_data

        translated_job = job_data.copy()

        # Translate title
        if job_data.get("title"):
            translated_title = self.translate_text(job_data["title"], target_lang="EN-US")
            if translated_title:
                translated_job["title"] = translated_title

        # Translate description
        if job_data.get("description"):
            translated_desc = self.translate_job_description(job_data["description"])
            if translated_desc:
                translated_job["description"] = translated_desc

        return translated_job

