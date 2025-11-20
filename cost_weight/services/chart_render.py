from __future__ import annotations
import io
from typing import List, Dict
from matplotlib import pyplot as plt

plt.switch_backend("Agg")

PALETTE = ['#3b82f6','#f97316','#10b981','#6366f1','#ef4444','#14b8a6']

def render_chart_bytes(
    items: List[Dict[str, float]],
    title: str = "Cost Weight Chart",
    decimal_places: int = 1,
    fmt: str = "png",
) -> bytes:
    """
    items: [{"label": str, "value": float}, ...] where value = percentage (0..100)
    fmt: "png" | "pdf" 
    """
    labels = [it["label"] for it in items]
    data   = [float(it["value"]) for it in items]
    colors = PALETTE[:len(labels)]

    fig = plt.figure(figsize=(6.5, 6.5), dpi=180) 
    ax = fig.add_subplot(111)
    ax.set_title(title, pad=18)

    autopct_fmt = f"%.{decimal_places}f%%" 
    wedges, _, autotexts = ax.pie(
        data,
        labels=labels,
        autopct=autopct_fmt,
        startangle=90,
        counterclock=False,
        colors=colors,
        wedgeprops={"linewidth": 0.5, "edgecolor": "white"},
        textprops={"color": "#111827"},  # slate-900-ish
    )
    ax.axis('equal')  

    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
        t.set_size(10.5)

    ax.legend(
        wedges, labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.05),
        ncol=min(3, len(labels))
    )

    buf = io.BytesIO()
    fmt = fmt.lower()
    if fmt not in {"png", "pdf", "svg"}:
        fmt = "png"
    plt.tight_layout()
    fig.savefig(buf, format=fmt, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()