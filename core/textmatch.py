"""Сопоставление фраз гостя с синонимами по смыслу слов, а не по точному написанию.

Слова приводим к начальной форме (pymorphy3: «собакой» → «собака», «псом» → «пёс»),
синоним совпадает, если все его значимые слова есть во фразе по порядку и рядом.
Нет pymorphy3 — откатываемся на грубую основу (обрезаем окончание).
"""
import re
from functools import lru_cache

try:
    import pymorphy3
    _morph = pymorphy3.MorphAnalyzer()
except ImportError:  # без библиотеки — грубая основа
    _morph = None

STOP = {"и", "в", "во", "на", "с", "со", "у", "к", "ко", "по", "о", "об", "от", "до", "за", "из", "для", "а", "ли",
        "не", "ни", "же", "бы", "что", "чтобы", "как", "это", "то", "там", "тут", "мы", "вы", "я", "он", "она",
        "есть", "быть", "можно", "ваш", "наш", "мой", "свой", "какой", "ли"}


def words(text: str) -> list[str]:
    return re.findall(r"[a-zа-я0-9]+", text.lower().replace("ё", "е").replace("/", ""))


@lru_cache(maxsize=20000)
def norm(word: str) -> str:
    """Начальная форма слова (или грубая основа без pymorphy3)."""
    if _morph:
        return _morph.parse(word)[0].normal_form.replace("ё", "е")
    return word if len(word) <= 4 else word[:max(4, len(word) - 2)]


def lemmas(text: str) -> list[str]:
    return [norm(w) for w in words(text)]


def _same(a: str, b: str) -> bool:
    # разные части речи одного корня: «парковка» / «парковаться», «детский» / «дети» — совпадение по началу
    if a == b:
        return True
    n = min(len(a), len(b))
    return n >= 5 and a[:n - 1] == b[:n - 1]


def find(syn: str, phrase: list[str]) -> set[int] | None:
    """Позиции фразы (леммы), где по порядку стоят значимые слова синонима; окно — длина синонима + 2."""
    need = [norm(w) for w in words(syn) if w not in STOP] or [norm(w) for w in words(syn)]
    for start in range(len(phrase)):
        pos, i = [], start
        for w in need:
            while i < len(phrase) and i - start <= len(need) + 2:
                if _same(phrase[i], w):
                    pos.append(i)
                    i += 1
                    break
                i += 1
            else:
                break
        if len(pos) == len(need):
            return set(pos)
    return None


def best(phrase_text: str, items: list[dict], key: str = "synonyms") -> list[tuple[str, int]]:
    """Какие элементы каталога упомянуты во фразе: [(id, сколько слов совпало)], длинный синоним
    побеждает короткий внутри себя («круглосуточная аптека» не даёт ещё и просто «аптеку»)."""
    phrase = lemmas(phrase_text)
    found = []
    for it in items:
        for syn in it.get(key, []):
            pos = find(syn, phrase)
            if pos:
                found.append((len(pos), pos, it["id"]))
    taken, out = [], []
    for n, pos, iid in sorted(found, key=lambda x: -x[0]):
        if any(iid == o for o, _ in out) or any(pos < p for p in taken):
            continue
        taken.append(pos)
        out.append((iid, n))
    return out
