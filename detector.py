import re
from dataclasses import dataclass
from mapper import convert_layout, direction

try:
    from wordfreq import zipf_frequency
except ImportError:
    zipf_frequency = None

WORD_RE = re.compile(r"[A-Za-z]+|[\u0590-\u05FF]+")

@dataclass
class Detection:
    original: str
    converted: str
    confidence: float
    source_lang: str
    target_lang: str


def _words(text: str):
    return WORD_RE.findall(text)


def _score_with_wordfreq(text: str, lang: str) -> float:
    words = _words(text)
    if not words:
        return 0.0
    vals = [max(0.0, zipf_frequency(w, lang)) for w in words]
    # Reward several plausible words; one very common word alone should not trigger strongly.
    avg = sum(vals) / len(vals)
    known_ratio = sum(v >= 2.2 for v in vals) / len(vals)
    return avg + 2.0 * known_ratio


COMMON_HE = {
    'אני','אתה','את','הוא','היא','אנחנו','הם','הן','של','על','עם','לא','כן','מה','זה','זו','יש','אין','גם','אבל','אם','כי',
    'איך','למה','מתי','איפה','פה','שם','רוצה','צריך','יכול','יכולה','לעשות','להיות','היה','הייתה','היום','מחר','עכשיו','טוב',
    'תודה','שלום','בבקשה','אפשר','משהו','אחד','אחת','יותר','פחות','כמו','כל','עוד','מאוד','שלי','שלך','אותו','אותה','לכתוב'
}
COMMON_EN = {
    'i','you','he','she','we','they','the','a','an','and','or','but','if','because','of','to','in','on','with','for','from','is','are',
    'was','were','be','been','have','has','do','does','did','what','why','when','where','how','this','that','there','here','can','could',
    'want','need','please','thanks','thank','hello','good','today','tomorrow','now','more','less','something','write','make','like'
}


def _fallback_score(text: str, lang: str) -> float:
    words = [w.lower() for w in _words(text)]
    if not words:
        return 0.0
    common = COMMON_HE if lang == 'he' else COMMON_EN
    hits = sum(w in common for w in words)
    letter_count = sum(c.isalpha() for c in text)
    if lang == 'he':
        script = sum('\u0590' <= c <= '\u05ff' for c in text) / max(1, letter_count)
    else:
        script = sum('a' <= c.lower() <= 'z' for c in text) / max(1, letter_count)
    return hits * 1.7 + script


def language_score(text: str, lang: str) -> float:
    if zipf_frequency:
        return _score_with_wordfreq(text, lang)
    return _fallback_score(text, lang)


def detect_wrong_layout(text: str, min_chars: int = 8, threshold: float = 2.2) -> Detection | None:
    clean = text.strip()
    if len(clean) < min_chars:
        return None
    d = direction(clean)
    if not d:
        return None

    converted = convert_layout(clean, d)
    if converted == clean:
        return None

    if d == 'en_to_he':
        source_lang, target_lang = 'en', 'he'
    else:
        source_lang, target_lang = 'he', 'en'

    src = language_score(clean, source_lang)
    dst = language_score(converted, target_lang)
    gap = dst - src

    # Require the converted text to be meaningfully more language-like.
    if gap < threshold:
        return None

    # Squash to a useful 0..1 display confidence rather than pretending this is calibrated probability.
    confidence = min(0.99, 0.55 + gap / 10)
    return Detection(clean, converted, confidence, source_lang, target_lang)
