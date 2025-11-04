"""Unit normalization and pattern-based inference utilities."""
import re


def normalize_unit(unit: str | None) -> str | None:
    """Normalize unit strings for comparison.
    
    Args:
        unit: Raw unit string (e.g., "M²", "m3", "Ls", "M^3")
        
    Returns:
        Normalized unit string or None if empty/invalid
        
    Examples:
        >>> normalize_unit("M²")
        'm2'
        >>> normalize_unit("M^3")
        'm3'
        >>> normalize_unit("Ls")
        'ls'
    """
    if not unit:
        return None
    
    # Lowercase and strip whitespace
    s = unit.strip().lower()
    if not s:
        return None
    
    # Replace special characters with standard forms
    s = s.replace(" ", "").replace("^", "").replace("²", "2").replace("³", "3")
    s = s.replace("㎡", "m2").replace("㎥", "m3")
    
    # Normalize common unit variations
    s = s.replace("meter", "m").replace("meters", "m")
    s = s.replace("buah", "bh")
    
    # Handle m1 as just m (linear)
    if s == "m1":
        s = "m"
    
    # Handle special quotes/apostrophes (m' is linear meter in some notations)
    s = s.replace("'", "").replace("'", "")
    
    # Remove remaining punctuation
    s = re.sub(r"[^0-9a-z/]+", "", s)
    
    return s if s else None


def infer_unit_from_description(description: str) -> str | None:
    """Infer unit type from item description with strict patterns.
    
    Now checks for explicit unit mentions in the description first,
    then falls back to pattern-based inference.
    
    Args:
        description: Item description (normalized or raw)
        
    Returns:
        Inferred unit string or None
        
    Examples:
        >>> infer_unit_from_description("Pemasangan 1 m2 Dinding Keramik")
        'm2'
        >>> infer_unit_from_description("Pemasangan 1 m' Plint Keramik")
        'm'
        >>> infer_unit_from_description("galian tanah")
        'm3'
    """
    desc_lower = description.lower()
    
    # STEP 1: Look for explicit unit mentions in the description
    # Check for m2 variations
    if re.search(r'\b(m2|m²|meter2|persegi)\b', desc_lower):
        return 'm2'
    
    # Check for m3 variations
    if re.search(r'\b(m3|m³|meter3|kubik)\b', desc_lower):
        return 'm3'
    
    # Check for linear meter (m' or m1 or just "m" followed by space or punctuation)
    # The pattern "1 m'" is common for linear measurements
    if re.search(r"(m'|m1\b|\b1\s*m\s+(?!2|3|²|³))", desc_lower):
        return 'm'
    
    # Check for lump sum
    if re.search(r'\b(ls|lumpsum|paket)\b', desc_lower):
        return 'ls'
    
    # Check for pieces
    if re.search(r'\b(bh|buah|unit|set)\b', desc_lower):
        return 'bh'
    
    # Check for kg
    if re.search(r'\b(kg|kilogram)\b', desc_lower):
        return 'kg'
    
    # STEP 2: Pattern-based inference (fallback)
    # Lump sum indicators (highest priority)
    ls_patterns = [
        'mobilisasi', 'demobilisasi', 'penyiapan', 'persiapan',
        'papan proyek', 'papan nama', 'direksi keet', 'barak',
        'administrasi', 'dokumentasi', 'laporan', 'rapat',
        'sertifikat', 'ijin', 'perijinan'
    ]
    if any(pattern in desc_lower for pattern in ls_patterns):
        return 'ls'
    
    # Volume (m3) indicators
    m3_patterns = [
        'galian', 'urugan', 'timbunan', 'pemadatan', 'pengurugan',
        'beton cor', 'pengecoran', 'volume',
        'tanah', 'pasir urug', 'sirtu', 'agregat',
        'pembongkaran beton'
    ]
    if any(pattern in desc_lower for pattern in m3_patterns):
        return 'm3'
    
    # Area (m2) indicators - but check it's not plint/lis (linear)
    m2_patterns = [
        'lantai', 'dinding', 'plafon', 'ceiling',
        'keramik', 'granit', 'marmer', 'parket', 'vinyl',
        'cat', 'pengecatan', 'plester', 'acian', 'aci',
        'lapangan', 'perataan', 'permukaan',
        'waterproofing', 'membran', 'geotextile', 'aspal',
        'paving', 'conblock', 'grass block'
    ]
    # Special case: "plint" or "lis" is linear (m), not area
    if 'plint' in desc_lower or 'lis' in desc_lower:
        return 'm'
    
    if any(pattern in desc_lower for pattern in m2_patterns):
        return 'm2'
    
    # Length (m) indicators
    m_patterns = [
        'pipa', 'kabel', 'pagar', 'railing', 'handrail',
        'list', 'profil', 'besi beton', 'tulangan',
        'drainase', 'saluran', 'gorong', 'talang',
        'kawat', 'tali', 'selang'
    ]
    if any(pattern in desc_lower for pattern in m_patterns):
        return 'm'
    
    # Piece/unit (bh/buah) indicators
    bh_patterns = [
        'pintu', 'jendela', 'lampu', 'saklar', 'stop kontak',
        'kunci', 'handle', 'engsel',
        'pompa', 'tangki', 'reservoir', 'septictank',
        'closet', 'wastafel', 'kran', 'shower',
        'ac ', 'air conditioner', 'exhaust fan'
    ]
    if any(pattern in desc_lower for pattern in bh_patterns):
        return 'bh'
    
    return None


def units_are_compatible(inferred_unit: str | None, user_unit: str | None) -> bool:
    """Check if two units are compatible (strict match).
    
    Args:
        inferred_unit: Unit inferred from candidate description
        user_unit: Unit provided by user
        
    Returns:
        True if units match exactly or are aliases of each other
        
    Examples:
        >>> units_are_compatible('m2', 'm2')
        True
        >>> units_are_compatible('m', 'm2')
        False
        >>> units_are_compatible('m', 'm1')
        True
        >>> units_are_compatible('bh', 'buah')
        True
    """
    if not user_unit:
        return True  # No filter if user doesn't provide unit
    
    if not inferred_unit:
        return False  # Candidate has no inferable unit
    
    normalized_user = normalize_unit(user_unit)
    normalized_inferred = normalize_unit(inferred_unit)
    
    if not normalized_user or not normalized_inferred:
        return False
    
    # Direct match
    if normalized_user == normalized_inferred:
        return True
    
    # Check alias groups (same unit, different notation)
    alias_groups = [
        {'m', 'm1', 'meter'},              # Linear meter aliases
        {'m2', 'meter2', 'persegi'},       # Area aliases
        {'m3', 'meter3', 'kubik'},         # Volume aliases
        {'bh', 'buah', 'unit', 'set'},     # Piece aliases
        {'ls', 'lumpsum', 'paket'},        # Lump sum aliases
        {'kg', 'kilogram'},                # Weight aliases
    ]
    
    for group in alias_groups:
        if normalized_user in group and normalized_inferred in group:
            return True
    
    return False


def calculate_unit_compatibility_score(candidate_description: str, user_unit: str) -> float:
    """Calculate compatibility score (for backward compatibility).
    
    This is now a simple 0 or 1 check since we filter strictly.
    
    Args:
        candidate_description: Description from AHS database
        user_unit: Unit from user's uploaded file
        
    Returns:
        0.0 if incompatible, 0.08 if compatible
    """
    if not user_unit:
        return 0.0
    
    inferred = infer_unit_from_description(candidate_description)
    return 0.08 if units_are_compatible(inferred, user_unit) else 0.0