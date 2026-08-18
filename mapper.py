EN_TO_HE = {
    'q': '/', 'w': "'", 'e': 'ק', 'r': 'ר', 't': 'א', 'y': 'ט', 'u': 'ו', 'i': 'ן', 'o': 'ם', 'p': 'פ',
    '[': ']', ']': '[',
    'a': 'ש', 's': 'ד', 'd': 'ג', 'f': 'כ', 'g': 'ע', 'h': 'י', 'j': 'ח', 'k': 'ל', 'l': 'ך', ';': 'ף', "'": ',',
    'z': 'ז', 'x': 'ס', 'c': 'ב', 'v': 'ה', 'b': 'נ', 'n': 'מ', 'm': 'צ', ',': 'ת', '.': 'ץ', '/': '.',
    ' ': ' ', '\n': '\n', '\t': '\t',
}

# Hebrew standard keyboard layout -> US QWERTY.
HE_TO_EN = {v: k for k, v in EN_TO_HE.items() if v not in {' ', '\n', '\t'}}
HE_TO_EN.update({' ': ' ', '\n': '\n', '\t': '\t'})


def convert_layout(text: str, forced_direction: str | None = None) -> str:
    """Convert each key using one keyboard-layout direction for the whole segment."""
    d = forced_direction or direction(text)
    if not d:
        return text
    out = []
    if d == 'en_to_he':
        for ch in text:
            low = ch.lower()
            out.append(EN_TO_HE.get(low, ch))
    else:
        for ch in text:
            repl = HE_TO_EN.get(ch, ch)
            out.append(repl)
    return ''.join(out)


def direction(text: str) -> str | None:
    latin = sum(('a' <= c.lower() <= 'z') for c in text)
    hebrew = sum('\u0590' <= c <= '\u05ff' for c in text)
    if latin >= max(3, hebrew * 2):
        return 'en_to_he'
    if hebrew >= max(3, latin * 2):
        return 'he_to_en'
    return None
