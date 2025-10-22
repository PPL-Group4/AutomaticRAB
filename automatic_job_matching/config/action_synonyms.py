"""Manual curated action word synonyms (Indonesian only).
Translation is handled by separate translation service.
"""

_BASE_ACTION_SYNONYMS = {
    # Installation/setup
    'pekerjaan': ['pemasangan', 'pembongkaran', 'perbaikan', 'pembuatan', 'pengecatan', 'pembangunan', 'pengerjaan', 'pemeliharaan'],
    'pemasangan': ['pekerjaan', 'pembuatan', 'pengerjaan', 'instalasi'],
    'pasang': ['pemasangan', 'memasang'],
    
    # Demolition
    'pembongkaran': ['pekerjaan', 'bongkar', 'membongkar'],
    'bongkar': ['pembongkaran', 'membongkar'],
    
    # Construction
    'pembuatan': ['pekerjaan', 'pemasangan', 'pembangunan', 'pengerjaan', 'buat', 'membuat'],
    'pembangunan': ['pekerjaan', 'pembuatan', 'pengerjaan', 'bangun', 'membangun'],
    'buat': ['pembuatan', 'membuat'],
    'bangun': ['pembangunan', 'membangun'],
    
    # Repair
    'perbaikan': ['pekerjaan', 'pemasangan', 'pemeliharaan', 'perbaiki', 'memperbaiki'],
    'pemeliharaan': ['pekerjaan', 'perbaikan'],
    
    # Painting
    'pengecatan': ['pekerjaan', 'pemasangan', 'cat', 'mengecat'],
    
    # Excavation
    'galian': ['penggalian', 'pekerjaan', 'gali', 'menggali'],
    'penggalian': ['galian', 'pekerjaan'],
    
    # Fill
    'urugan': ['pengurugan', 'pekerjaan', 'urug', 'mengurug'],
    'pengurugan': ['urugan', 'pekerjaan'],
}

_BASE_CONSTRUCTION_SYNONYMS = { # noun synonyms related to construction materials and methods
    # Structural terms
    "borepile": ["strauss", "pile", "bored"],
    "strauss": ["borepile", "pile"],
    "pile": ["borepile", "strauss", "bored"],
    "bored": ["borepile", "pile"],
    
    "pengecoran": ["cor", "pekerjaan"],
    "cor": ["pengecoran", "beton"],
    "bekisting": ["cetakan", "formwork"],
    "cetakan": ["bekisting", "formwork"],
    "formwork": ["bekisting", "cetakan"],
    "bubungan": ["bubung"],
    "bubung": ["bubungan"],
    "plafond": ["plafon"],
    "proteksi": ["penangkal"],

    # Plumbing
    "pipa": ["plumbing", "instalasi"],
    "plumbing": ["pipa", "instalasi"],
    "kloset": ["toilet", "wc"],
    "toilet": ["kloset", "wc"],
    "wc": ["kloset", "toilet"],
    "wastafel": ["sink", "wasbak"],
    "sink": ["wastafel", "wasbak"],
    "wasbak": ["wastafel", "sink"],
    
    # Electrical
    "tombol": ["saklar", "switch"],
    "stop": ["kontak", "colokan", "outlet"],
    "kontak": ["stop", "colokan", "outlet"],
    "colokan": ["stop", "kontak", "outlet"],
    "outlet": ["stop", "kontak", "colokan"],
    
    # Painting
    "cat": ["pengecatan"],
    "pelitur": ["vernis"],
    "vernis": ["pelitur"],

    # Flooring
    "keramik": ["ceramic", "ubin"],
    "ceramic": ["keramik", "ubin"],
    "ubin": ["keramik", "ceramic"],
    "expose": ["beton", "semen"],
}

# Compound materials that should be treated as units (not expanded to individual words)
COMPOUND_MATERIALS = {
    # Hebel = Bata Ringan (lightweight brick/AAC block)
    'hebel': ['bata ringan'],
    'bata ringan': ['hebel'],
}

def _make_bidirectional(base_dict: dict[str, list[str]]) -> dict[str, list[str]]:
    """Return a new dict with bidirectional synonym mapping."""
    result: dict[str, set[str]] = {}
    for word, syns in base_dict.items():
        for s in syns:
            result.setdefault(word, set()).update(syns)
            result.setdefault(s, set()).add(word)
    return {k: sorted(v) for k, v in result.items()}


# --- Build the final dictionaries ---

ACTION_SYNONYMS = _make_bidirectional(_BASE_ACTION_SYNONYMS)
CONSTRUCTION_SYNONYMS = _make_bidirectional(_BASE_CONSTRUCTION_SYNONYMS)
ALL_SYNONYMS = {**ACTION_SYNONYMS, **CONSTRUCTION_SYNONYMS}

def get_synonyms(word: str) -> list[str]:
    """Get synonyms for a given action word."""
    return ALL_SYNONYMS.get(word.lower(), [])

def has_synonyms(word: str) -> bool:
    """Check if word has synonyms defined."""
    return word.lower() in ALL_SYNONYMS

def get_all_action_words() -> set[str]:
    """Get all action words that have synonym mappings."""
    return set(ALL_SYNONYMS.keys())

def get_compound_materials() -> dict[str, list[str]]:
    """Get compound materials that should be treated as units."""
    return COMPOUND_MATERIALS

def is_compound_material(word: str) -> bool:
    """Check if word is a compound material."""
    return word.lower() in COMPOUND_MATERIALS