"""
Language detection for the bilingual pipeline.

Rule: if more than 20% of the characters are in the Arabic Unicode
block (U+0600–U+06FF), the question is treated as Arabic.

Why a character ratio and not a language-ID model:
  - The system only needs a binary Arabic / English decision.
  - It is deterministic, free, and takes microseconds.
  - Mixed input such as "ما هو total sales؟" still routes to the
    translation step, which is what we want.
Known limit: Arabizi (Arabic written in Latin letters) is detected as
English.
"""

from src.text_to_sql.constants import LANG_ARABIC, LANG_ENGLISH

ARABIC_CHAR_RATIO_THRESHOLD = 0.2


def arabic_char_ratio(text: str) -> float:
    """Fraction of characters that fall in the Arabic Unicode block."""
    if not text:
        return 0.0
    arabic_chars = sum(1 for c in text if "؀" <= c <= "ۿ")
    return arabic_chars / len(text)


def detect_language(text: str) -> str:
    """Return 'ar' if the text is mostly Arabic, otherwise 'en'."""
    return (
        LANG_ARABIC
        if arabic_char_ratio(text) > ARABIC_CHAR_RATIO_THRESHOLD
        else LANG_ENGLISH
    )
