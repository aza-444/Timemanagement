import io
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from database.models import Expense, Category


def clean_label(text: str) -> str:
    """Strips emoji characters to avoid font missing warnings in matplotlib."""
    return re.sub(r'[^\w\s\-\.\/\,\%\:\(\)]', '', text).strip()


def format_amount(value: float) -> str:
    """Returns compact formatted string: 1 500 000 so'm"""
    if value >= 1_000_000:
        return f"{value/1_000_000:.2f}M".rstrip('0').rstrip('.') + " mln"
    elif value >= 1_000:
        return f"{value/1_000:.1f}K".rstrip('0').rstrip('.')
    return f"{value:,.0f}".replace(',', ' ')


def generate_expense_charts(
    expenses_data: List[Tuple[Expense, Optional[Category]]],
    period_title: str = "Xarajatlar Tahlili"
) -> Optional[io.BytesIO]:
    """
    Generates a premium dual-plot image:
      Left  — Donut Pie Chart with legend (no label overlaps)
      Right — Gradient Bar Chart with data labels on top
    """
    if not expenses_data:
        return None

    records = []
    for exp, cat in expenses_data:
        raw_cat = cat.name if cat else "Noma'lum"
        records.append({
            "amount": exp.amount,
            "category_raw": raw_cat,
            "category": clean_label(raw_cat) or raw_cat,
            "date": exp.expense_date,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return None

    # ── Color palette ───────────────────────────────────────────────────
    PALETTE = [
        '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
        '#8b5cf6', '#ec4899', '#06b6d4', '#64748b',
        '#f97316', '#14b8a6', '#a855f7', '#84cc16',
    ]
    BG = '#f8fafc'

    # ── Figure setup ────────────────────────────────────────────────────
    fig = plt.figure(figsize=(16, 7), dpi=150, facecolor=BG)
    fig.patch.set_facecolor(BG)

    ax1 = fig.add_subplot(1, 2, 1, facecolor=BG)
    ax2 = fig.add_subplot(1, 2, 2, facecolor=BG)

    clean_title = clean_label(period_title) or period_title
    fig.suptitle(clean_title, fontsize=17, fontweight='bold', color='#0f172a', y=1.01)

    # ════════════════════════════════════════════════════════════════════
    # LEFT: Donut Pie Chart
    # ════════════════════════════════════════════════════════════════════
    cat_summary = df.groupby("category")["amount"].sum().reset_index()
    cat_summary = cat_summary.sort_values(by="amount", ascending=False)
    total = cat_summary["amount"].sum()
    n_cats = len(cat_summary)
    colors = PALETTE[:n_cats]

    wedges, _, autotexts = ax1.pie(
        cat_summary["amount"],
        autopct=lambda pct: f'{pct:.1f}%' if pct >= 3 else '',
        startangle=140,
        colors=colors,
        wedgeprops=dict(width=0.42, edgecolor='white', linewidth=2),
        pctdistance=0.78,
    )
    for at in autotexts:
        at.set_fontsize(8)
        at.set_fontweight('bold')
        at.set_color('white')

    # Center text
    ax1.text(0, 0.08, "Jami", ha='center', va='center',
             fontsize=10, color='#64748b')
    ax1.text(0, -0.12, format_amount(total), ha='center', va='center',
             fontsize=12, fontweight='bold', color='#0f172a')

    ax1.set_title("Kategoriyalar Bo'yicha Taqsimot",
                  fontsize=12, fontweight='bold', color='#1e293b', pad=10)

    # Legend below pie (no label collision)
    legend_labels = [
        f"{clean_label(row['category']) or row['category']}  —  {format_amount(row['amount'])} ({row['amount']/total*100:.1f}%)"
        for _, row in cat_summary.iterrows()
    ]
    legend_handles = [mpatches.Patch(color=c) for c in colors]
    ax1.legend(
        legend_handles, legend_labels,
        loc='lower center',
        bbox_to_anchor=(0.5, -0.30),
        ncol=2 if n_cats > 4 else 1,
        fontsize=8,
        frameon=False,
        labelcolor='#334155',
    )

    # ════════════════════════════════════════════════════════════════════
    # RIGHT: Bar Chart (daily dynamics)
    # ════════════════════════════════════════════════════════════════════
    date_summary = df.groupby("date")["amount"].sum().reset_index()
    date_summary = date_summary.sort_values(by="date")
    n_bars = len(date_summary)
    date_labels = [str(d) for d in date_summary["date"]]

    # Gradient colors from light-blue to deep-blue
    bar_colors = [
        plt.cm.Blues(0.35 + 0.55 * i / max(n_bars - 1, 1))
        for i in range(n_bars)
    ]

    bars = ax2.bar(
        range(n_bars),
        date_summary["amount"],
        color=bar_colors,
        edgecolor='#1d4ed8',
        linewidth=0.6,
        width=0.6,
        zorder=3,
    )

    # Data labels on top of bars
    max_val = date_summary["amount"].max() if n_bars else 1
    for i, bar in enumerate(bars):
        h = bar.get_height()
        rotation = 70 if n_bars > 10 else 0
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            h + max_val * 0.01,
            format_amount(h),
            ha='center', va='bottom',
            fontsize=7 if n_bars > 8 else 8,
            fontweight='bold',
            color='#1e3a8a',
            rotation=rotation,
        )

    # Styling
    ax2.set_xticks(range(n_bars))
    ax2.set_xticklabels(date_labels, rotation=40, ha='right', fontsize=7 if n_bars > 10 else 8)
    ax2.set_title("Kunlik Xarajatlar Dinamikasi",
                  fontsize=12, fontweight='bold', color='#1e293b', pad=10)
    ax2.set_xlabel("Sana", fontsize=9, color='#475569')
    ax2.set_ylabel("Summa", fontsize=9, color='#475569')
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: format_amount(x)
    ))
    ax2.tick_params(axis='y', labelsize=8, colors='#475569')
    ax2.tick_params(axis='x', colors='#475569')
    ax2.spines[['top', 'right']].set_visible(False)
    ax2.spines[['left', 'bottom']].set_color('#cbd5e1')
    ax2.set_facecolor(BG)
    ax2.yaxis.grid(True, linestyle='--', alpha=0.5, color='#e2e8f0', zorder=0)
    ax2.set_axisbelow(True)

    plt.tight_layout(rect=[0, 0, 1, 0.98])

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf
