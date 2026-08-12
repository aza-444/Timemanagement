"""
Utility: parse user-entered amounts like:
  4mln, 4 mln, 4.5m, 4M    → 4_000_000
  18k, 18 k, 18 K, 18ming  → 18_000
  50_000, 50 000, 50,000    → 50_000
  1.5mln                    → 1_500_000

Quick-add: "18k avtobus uchun 5 kunlik tarif" → (18000, "avtobus uchun 5 kunlik tarif")
"""
import re

SUFFIXES = ('mln', 'mlrd', 'ming', 'm', 'k')  # order matters: 'ming' before 'm'

_NUM_PAT = re.compile(r'^(\d+(?:[.,]\d+)?)$')
_AMT_PAT = re.compile(r'^(\d+(?:[.,]\d+)?)(mln|mlrd|ming|m|k)$', re.IGNORECASE)


def _apply_suffix(num: float, suffix: str | None) -> float:
    if not suffix:
        return num
    s = suffix.lower()
    if s in ('mln', 'm'):
        return num * 1_000_000
    if s == 'mlrd':
        return num * 1_000_000_000
    if s in ('ming', 'k'):
        return num * 1_000
    return num


def _parse_token(tok: str) -> float | None:
    """Parse a single token like '18k', '4.5mln', '50000'."""
    tok = tok.strip().replace('_', '').replace(' ', '')
    if not tok:
        return None
    # comma → try as thousands separator
    if ',' in tok and '.' not in tok:
        tok = tok.replace(',', '')
    elif ',' in tok:
        return None  # mixed usage

    m = _AMT_PAT.match(tok)
    if m:
        try:
            num = float(m.group(1).replace(',', '.'))
        except ValueError:
            return None
        result = _apply_suffix(num, m.group(2))
        return result if result > 0 else None

    m2 = _NUM_PAT.match(tok)
    if m2:
        try:
            num = float(tok.replace(',', '.'))
        except ValueError:
            return None
        return num if num > 0 else None

    return None


def parse_amount(text: str) -> float | None:
    """
    Parses a single amount expression (possibly with space between number and suffix).
    Examples: '18k', '18 k', '4 mln', '50000', '50,000'
    Returns float or None if invalid.
    """
    text = text.strip()

    # Try single token first
    result = _parse_token(text.replace(' ', ''))
    if result is not None:
        return result

    # Try "NUMBER SUFFIX" separated by space (e.g. "18 k", "4 mln")
    parts = text.split()
    if len(parts) == 2:
        num_part, suf_part = parts
        if suf_part.lower() in SUFFIXES and _NUM_PAT.match(num_part.replace(',', '')):
            combined = num_part + suf_part
            return _parse_token(combined)

    return None


def parse_quick_add(text: str) -> tuple[float, str] | None:
    """
    Parse free-form text like "18k avtobus uchun" or "50000 tushlik".
    Tries to extract amount from the beginning (1 or 2 tokens), rest = description.
    Returns (amount, description) or None if not a quick-add.
    """
    text = text.strip()
    if not text:
        return None

    tokens = text.split()
    if not tokens:
        return None

    # Try first two tokens as "NUMBER SUFFIX" (e.g. "18 k", "4 mln") — check this FIRST
    if len(tokens) >= 2 and tokens[1].lower() in SUFFIXES:
        amt = _parse_token(tokens[0] + tokens[1])
        if amt is not None:
            desc = ' '.join(tokens[2:]).strip()
            return (amt, desc)

    # Try first token alone: "18k avtobus uchun"
    amt = _parse_token(tokens[0])
    if amt is not None:
        desc = ' '.join(tokens[1:]).strip()
        return (amt, desc)

    return None


from datetime import date, timedelta

MONTHS_MAP = {
    'yanvar': 1, 'january': 1, 'январ': 1, 'января': 1,
    'fevral': 2, 'february': 2, 'феврал': 2, 'февраля': 2,
    'mart': 3, 'march': 3, 'март': 3, 'марта': 3,
    'aprel': 4, 'april': 4, 'апрел': 4, 'апреля': 4,
    'may': 5, 'май': 5, 'мая': 5,
    'iyun': 6, 'june': 6, 'июн': 6, 'июня': 6,
    'iyul': 7, 'july': 7, 'июл': 7, 'июля': 7,
    'avgust': 8, 'august': 8, 'август': 8, 'августа': 8,
    'sentabr': 9, 'sentyabr': 9, 'september': 9, 'сентябр': 9, 'сентября': 9,
    'oktabr': 10, 'oktyabr': 10, 'october': 10, 'октябр': 10, 'октября': 10,
    'noyabr': 11, 'november': 11, 'ноябр': 11, 'ноября': 11,
    'dekabr': 12, 'december': 12, 'декабр': 12, 'декабря': 12
}


def extract_date_from_text(text: str) -> tuple[str, date | None]:
    """
    Searches for date patterns inside free-form text.
    Removes the date portion from text and returns (cleaned_text, parsed_date).
    Supports:
      - 'kecha', 'bugun', 'o\'tgan kuni'
      - 'YYYY-MM-DD', 'DD.MM.YYYY', 'DD-MM-YYYY', 'DD/MM/YYYY'
      - '10-avgust', '10 avgust', '10-avgustda', '10.08', '10-08'
    """
    today = date.today()
    found_date = None
    cleaned = text

    rel_patterns = [
        (r'\b(o[^\w\s]?tgan\s+kuni|otgan\s+kuni)\b', today - timedelta(days=2)),
        (r'\b(kecha)\b', today - timedelta(days=1)),
        (r'\b(bugun)\b', today),
    ]
    for pat, dt in rel_patterns:
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            found_date = dt
            cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE)
            break

    if not found_date:
        m = re.search(r'\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b', cleaned)
        if m:
            y, m_num, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                found_date = date(y, m_num, d)
                cleaned = cleaned[:m.start()] + cleaned[m.end():]
            except ValueError:
                pass

    if not found_date:
        m = re.search(r'\b(0?[1-9]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2])[-/.](20\d{2})\b', cleaned)
        if m:
            d, m_num, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                found_date = date(y, m_num, d)
                cleaned = cleaned[:m.start()] + cleaned[m.end():]
            except ValueError:
                pass

    if not found_date:
        month_names_pat = '|'.join(sorted(MONTHS_MAP.keys(), key=len, reverse=True))
        pat = r'\b(0?[1-9]|[12]\d|3[01])[-.\s]*(?:da)?[-.\s]*(' + month_names_pat + r')(?:da|dagi)?(?:[-.\s]*(20\d{2}))?\b'
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            d = int(m.group(1))
            m_str = m.group(2).lower()
            m_num = MONTHS_MAP.get(m_str)
            y = int(m.group(3)) if m.group(3) else today.year
            if m_num:
                try:
                    found_date = date(y, m_num, d)
                    cleaned = cleaned[:m.start()] + cleaned[m.end():]
                except ValueError:
                    pass

    if not found_date:
        m = re.search(r'\b(0?[1-9]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2])\b', cleaned)
        if m:
            d, m_num = int(m.group(1)), int(m.group(2))
            y = today.year
            try:
                found_date = date(y, m_num, d)
                cleaned = cleaned[:m.start()] + cleaned[m.end():]
            except ValueError:
                pass

    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned, found_date


def parse_flexible_date(text: str) -> date | None:
    """
    Parses a date string entered by user in any format.
    """
    text = text.strip()
    if not text:
        return None
    _, dt = extract_date_from_text(text)
    if dt:
        return dt
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


INCOME_KEYWORDS = [
    'oldim', 'olindi', 'maosh', 'oylik', 'bonus', 'avans',
    'qarzning qaytarilishi', 'qarz qaytdi', 'qaytarib berishdi',
    'tushdi', 'kirim', 'ish haqi', 'oluvdim', 'topib olindi'
]

EXPENSE_ITEM_KEYWORDS = [
    'shim', 'atir', 'taksi', 'ovqat', 'suv', 'puli', 'uchun', 'oziq', 'obed',
    'ujin', 'non', 'gosht', 'go\'sht', 'kiyim', 'paypoq', 'telefon', 'benzin',
    'zaryadnik', 'sigaret', 'choy', 'kofe'
]


def parse_quick_add_with_type(text: str) -> tuple[float, str, str, date | None] | None:
    """
    Like parse_quick_add but also detects transaction type and custom date.
    Returns (amount, description, 'income'|'expense', date|None) or None.

    Examples:
      "5mln avans tushdi 10-avgust" → (5000000, "avans tushdi", "income", date(2026, 8, 10))
      "18k avtobus kecha"          → (18000, "avtobus", "expense", date(2026, 8, 10))
    """
    text = text.strip()
    if not text:
        return None

    # First extract date if present anywhere in text
    text_clean, exp_date = extract_date_from_text(text)

    tx_type = None
    if text_clean.startswith("+"):
        tx_type = "income"
        text_clean = text_clean[1:].strip()

    result = parse_quick_add(text_clean)
    if result is None:
        return None
    amount, description = result

    if tx_type is None:
        tx_type = "expense"
        if description:
            desc_lower = description.lower()
            if any(k in desc_lower for k in INCOME_KEYWORDS):
                # Check if it's an item purchase like 'shim va atir oldim'
                if desc_lower.endswith('oldim') and any(item in desc_lower for item in EXPENSE_ITEM_KEYWORDS):
                    tx_type = "expense"
                else:
                    tx_type = "income"

    return (amount, description, tx_type, exp_date)


AMOUNT_HINT = (
    "<i>Misollar: <code>50000</code>, <code>18k</code> (18 000), "
    "<code>18 k</code>, <code>2mln</code> (2 000 000), <code>4.5ming</code> (4 500)</i>"
)

INCOME_HINT = (
    "<i>Misollar: <code>+500k maosh</code>, <code>+2mln bonus</code>, <code>+50000 qarz qaytdi</code></i>"
)

