"""Shared seaborn styling for the analysis notebooks.

Colors are a validated categorical palette (CVD-safe in this slot order; the
first three slots are safe together on scatter plots). Assign slots in order,
never cycled, and keep a given entity on the same slot across charts.
"""

from __future__ import annotations

import matplotlib as mpl
import seaborn as sns
from matplotlib.ticker import FuncFormatter

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
PRIMARY = SERIES[0]
HIGHLIGHT = SERIES[1]
NEUTRAL = "#c3c2b7"

# Diverging blue <-> red with a gray midpoint (for signed values like returns and correlations).
DIVERGING_CMAP = mpl.colors.LinearSegmentedColormap.from_list(
    "blue_gray_red", ["#e34948", "#f0efec", "#2a78d6"]
)


def apply_style() -> None:
    """Seaborn whitegrid theme with thin marks, recessive grid/axes and the shared palette."""
    sns.set_theme(
        style="whitegrid",
        palette=SERIES,
        font=["Segoe UI", "DejaVu Sans", "sans-serif"],
        font_scale=0.95,
        rc={
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "figure.dpi": 110,
            "text.color": INK,
            "axes.labelcolor": INK_SECONDARY,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlecolor": INK,
            "axes.edgecolor": BASELINE,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
            "xtick.labelcolor": INK_SECONDARY,
            "ytick.labelcolor": INK_SECONDARY,
            "lines.linewidth": 2,
            "patch.edgecolor": SURFACE,
            "legend.frameon": False,
        },
    )


percent_formatter = FuncFormatter(lambda v, _: f"{v:,.0f}%")


def label_bars(ax, fmt: str = "{:,.0f}", padding: int = 3) -> None:
    """Direct-label every bar container on ``ax`` in secondary ink."""
    for container in ax.containers:
        ax.bar_label(container, fmt=fmt, padding=padding, color=INK_SECONDARY, fontsize=9)
