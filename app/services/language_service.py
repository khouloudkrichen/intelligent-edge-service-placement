from langdetect import DetectorFactory, detect

DetectorFactory.seed = 0

SUPPORTED_LANGUAGES = {"en", "fr", "ar"}


def detect_language(text: str) -> str:
    """Detect English, French, or Arabic. Defaults to English for short text."""
    cleaned = text.strip()
    if not cleaned:
        return "en"

    if any("\u0600" <= char <= "\u06ff" for char in cleaned):
        return "ar"

    try:
        language = detect(cleaned)
    except Exception:
        return _simple_language_fallback(cleaned)

    if language in SUPPORTED_LANGUAGES:
        return language
    return _simple_language_fallback(cleaned)


def _simple_language_fallback(text: str) -> str:
    words = set(text.lower().split())
    french_words = {
        "je",
        "tu",
        "il",
        "nous",
        "vous",
        "la",
        "le",
        "les",
        "un",
        "une",
        "est",
        "que",
        "qui",
        "comment",
        "pourquoi",
        "quand",
        "quel",
        "faire",
        "dois",
        "puis",
        "peut",
        "faut",
        "quoi",
        "mon",
        "ma",
        "des",
        "sur",
        "dans",
        "avec",
        "pour",
    }
    return "fr" if words & french_words else "en"
