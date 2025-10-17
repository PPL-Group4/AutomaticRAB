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
    # Structural materials
    "hebel": ["bata ringan", "bata putih"],
    "bata": ["hebel", "bata ringan"],
    "ringan": ["hebel", "bata putih"],
    
    # Structural terms
    "borepile": ["strauss", "strauss pile", "bored pile", "borepile"],
    "pengecoran": ["cor", "pekerjaan cor"],
    "bekisting": ["cetakan", "formwork"],

    # Plumbing
    "pipa": ["plumbing", "instalasi pipa"],
    "kloset": ["toilet", "wc"],
    "wastafel": ["sink", "wasbak"],
    
    # Electrical
    "saklar": ["switch", "tombol"],
    "stop kontak": ["colokan", "outlet"],
    
    # Painting
    "cat": ["pengecatan"],
    "pelitur": ["vernis"],

    # Flooring
    "keramik": ["ceramic", "ubin"],
    "expose": ["beton expose", "semen expose"],
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