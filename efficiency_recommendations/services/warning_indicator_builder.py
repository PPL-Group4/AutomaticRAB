from typing import Dict

def build_indicator(total_items: int, warning_count: int) -> Dict:
    """
    Build visual indicator data for the notifications banner/badge.
    Levels:
      - NONE: no warnings
      - WARN: 0 < ratio < 0.5
      - CRITICAL: ratio >= 0.5
    Colors/icons disesuaikan dengan test.
    """
    if total_items <= 0:
        ratio = 0.0
    else:
        ratio = warning_count / total_items

    ratio = round(float(ratio), 3)

    if warning_count == 0:
        return {
            "level": "NONE",
            "label": "No warnings",
            "badge_color": "#D1D5DB",
            "icon": "check-circle",
            "ratio": ratio,
        }

    if ratio >= 0.5:
        level = "CRITICAL"
        color = "#DC2626"
        icon = "x-octagon"
    else:
        level = "WARN"
        color = "#F59E0B"
        icon = "alert-triangle"

    label = f"{warning_count} warning" + ("s" if warning_count != 1 else "")

    return {
        "level": level,
        "label": label,
        "badge_color": color,
        "icon": icon,
        "ratio": ratio,
    }