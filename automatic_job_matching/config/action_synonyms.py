"""Manual curated action word synonyms (Indonesian only).
Translation is handled by separate translation service.
"""

ACTION_SYNONYMS = {
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

def get_synonyms(word: str) -> list[str]:
    """Get synonyms for a given action word."""
    return ACTION_SYNONYMS.get(word.lower(), [])

def has_synonyms(word: str) -> bool:
    """Check if word has synonyms defined."""
    return word.lower() in ACTION_SYNONYMS

def get_all_action_words() -> set[str]:
    """Get all action words that have synonym mappings."""
    return set(ACTION_SYNONYMS.keys())