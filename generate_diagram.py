import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(1, 1, figsize=(22, 14))
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#0d1117")
ax.set_xlim(0, 22)
ax.set_ylim(0, 14)
ax.axis("off")

C = {
    "bg":       "#0d1117",
    "box":      "#161b22",
    "phase1":   "#1a3a5c",
    "phase2":   "#1a4a2e",
    "phase3":   "#4a1a3a",
    "commit":   "#2a2a1a",
    "faiss":    "#1f6feb",
    "kg":       "#388bfd",
    "llm":      "#3fb950",
    "verifier": "#d29922",
    "ws":       "#bc8cff",
    "user":     "#58a6ff",
    "pass_c":   "#3fb950",
    "fail_c":   "#f85149",
    "text_s":   "#c9d1d9",
    "text_m":   "#8b949e",
    "border1":  "#1f6feb",
    "border2":  "#3fb950",
    "border3":  "#d29922",
    "border4":  "#bc8cff",
}


def box(ax, x, y, w, h, fc, ec="#30363d", lw=1.5, radius=0.3, alpha=0.9):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.0,rounding_size={radius}",
        facecolor=fc, edgecolor=ec, linewidth=lw, alpha=alpha, zorder=3,
    )
    ax.add_patch(p)


def txt(ax, x, y, s, size=10, color="#ffffff", weight="bold", ha="center", va="center"):
    ax.text(x, y, s, fontsize=size, color=color, fontweight=weight,
            ha=ha, va=va, zorder=5, fontfamily="DejaVu Sans")


def arr(ax, x1, y1, x2, y2, color="#8b949e", lw=2.0, rad=0.0):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="->", color=color, lw=lw,
            connectionstyle=f"arc3,rad={rad}",
            shrinkA=4, shrinkB=4,
        ),
        zorder=4,
    )


def phase_bg(ax, x, y, w, h, fc, ec, label):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.0,rounding_size=0.4",
        facecolor=fc, edgecolor=ec, linewidth=2.0, alpha=0.22, zorder=1,
    )
    ax.add_patch(p)
    ax.text(x + 0.3, y + h - 0.25, label, fontsize=8.5, color=ec,
            fontweight="bold", va="top", ha="left", zorder=2,
            fontfamily="DejaVu Sans")


# ── Title ─────────────────────────────────────────────────────────────────────
txt(ax, 11, 13.55, "Neuro-Symbolic RAG — Interactive Narrative Framework",
    size=18, color="#ffffff")
txt(ax, 11, 13.1, "Architecture Overview", size=11, color="#8b949e", weight="normal")

# ── User Input ────────────────────────────────────────────────────────────────
box(ax, 8.2, 11.5, 5.6, 1.2, C["box"], ec=C["user"], lw=2.5)
txt(ax, 11, 12.28, "USER INPUT", size=12, color=C["user"])
txt(ax, 11, 11.88, '"What happens next in the story?"',
    size=9, color=C["text_m"], weight="normal")

arr(ax, 11, 11.5, 11, 10.82, color=C["user"], lw=2.5)

# ── Phase 1 ───────────────────────────────────────────────────────────────────
phase_bg(ax, 0.4, 8.65, 21.2, 2.05, C["phase1"], C["border1"],
         "PHASE 1  —  HYBRID RETRIEVAL")

# FAISS
box(ax, 0.7, 8.9, 5.9, 1.5, "#0c2044", ec=C["faiss"], lw=2.0)
txt(ax, 3.65, 9.85, "FAISS  Semantic Memory", size=10, color=C["faiss"])
txt(ax, 3.65, 9.52, "all-MiniLM-L6-v2  |  Top-K dense search",
    size=8, color=C["text_m"], weight="normal")
txt(ax, 3.65, 9.18, "Retrieves relevant past story segments",
    size=7.5, color=C["text_m"], weight="normal")

# KG
box(ax, 7.95, 8.9, 6.1, 1.5, "#0c1e3a", ec=C["kg"], lw=2.0)
txt(ax, 11.0, 9.85, "Knowledge Graph  (Multi-hop)", size=10, color=C["kg"])
txt(ax, 11.0, 9.52, "NetworkX MultiDiGraph  |  BFS depth=2",
    size=8, color=C["text_m"], weight="normal")
txt(ax, 11.0, 9.18, "Character-centric  ·  Event-centric  ·  2-hop facts",
    size=7.5, color=C["text_m"], weight="normal")

# World State
box(ax, 15.35, 8.9, 5.9, 1.5, "#1a0c2e", ec=C["ws"], lw=2.0)
txt(ax, 18.3, 9.85, "World State Context", size=10, color=C["ws"])
txt(ax, 18.3, 9.52, "WorldStateManager  |  Live snapshot",
    size=8, color=C["text_m"], weight="normal")
txt(ax, 18.3, 9.18, "Characters · Items · Locations · Hard Rules",
    size=7.5, color=C["text_m"], weight="normal")

# arrows user -> retrieval
arr(ax, 8.2, 11.5, 3.65, 10.4, color=C["user"], lw=1.5)
arr(ax, 11.0, 11.5, 11.0, 10.4, color=C["user"], lw=1.5)
arr(ax, 13.8, 11.5, 18.3, 10.4, color=C["user"], lw=1.5)

# arrows retrieval -> LLM
arr(ax, 3.65, 8.9, 8.5, 7.98, color=C["faiss"], lw=1.8)
arr(ax, 11.0, 8.9, 11.0, 7.98, color=C["kg"],   lw=1.8)
arr(ax, 18.3, 8.9, 13.5, 7.98, color=C["ws"],   lw=1.8)

# ── Phase 2 ───────────────────────────────────────────────────────────────────
phase_bg(ax, 0.4, 6.55, 21.2, 1.95, C["phase2"], C["border2"],
         "PHASE 2  —  CONSTRAINED LLM GENERATION")

box(ax, 5.2, 6.75, 11.6, 1.55, "#0c2a18", ec=C["llm"], lw=2.5)
txt(ax, 11.0, 7.75, "LLM  Story  Generation", size=13, color=C["llm"])
txt(ax, 11.0, 7.38, "Ollama (llama3.2)   |   Groq (llama-3.1-8b-instant)   |   OpenAI (gpt-4o-mini)",
    size=8.5, color=C["text_m"], weight="normal")
txt(ax, 11.0, 7.05, "Prompt = Semantic Context + KG Facts + World State + Hard Constraints",
    size=8, color="#d29922", weight="normal")

arr(ax, 11, 6.75, 11, 6.22, color=C["llm"], lw=2.5)

# ── Phase 3 ───────────────────────────────────────────────────────────────────
phase_bg(ax, 0.4, 3.1, 21.2, 3.2, C["phase3"], C["border3"],
         "PHASE 3  —  NEURO-SYMBOLIC VERIFICATION  &  SELF-CORRECTION")

# Fact extraction box
box(ax, 6.8, 5.35, 8.4, 0.82, "#1e1a0a", ec=C["verifier"], lw=1.8)
txt(ax, 11.0, 5.76, "Fact Extraction   (subject, relation, object)", size=10, color=C["verifier"])
txt(ax, 11.0, 5.5, "LLM extracts structured facts from the generated story beat",
    size=7.5, color=C["text_m"], weight="normal")

arr(ax, 11, 5.35, 11, 4.78, color=C["verifier"], lw=2.0)

# Verifier master box
box(ax, 1.1, 3.42, 19.8, 1.28, "#2a1a0a", ec=C["verifier"], lw=2.5)
txt(ax, 11.0, 4.42, "Consistency Verifier", size=11, color=C["verifier"])

# 4 rule chips
chips = [
    ("Character Rules",  "Dead actor  ·  Illegal resurrection\nRelationship contradiction",  "#f85149"),
    ("Item Rules",       "Duplicate ownership  ·  Transfer\nUse without possession",          "#ff9f43"),
    ("Temporal Rules",   "Action after death\nLocation mismatch without travel",              "#feca57"),
    ("World Rules",      "Configurable hard\nnarrative constraints",                          "#48dbfb"),
]
for i, (title, sub, col) in enumerate(chips):
    cx = 1.4 + i * 4.95
    box(ax, cx, 3.5, 4.55, 0.62, "#161b22", ec=col, lw=1.5, radius=0.2)
    txt(ax, cx + 2.275, 3.92, title, size=8.5, color=col)
    txt(ax, cx + 2.275, 3.64, sub,   size=6.8, color=C["text_m"], weight="normal")

# PASS label + arrow right
txt(ax, 19.1, 3.8, "PASS", size=11, color=C["pass_c"], weight="bold")
arr(ax, 17.5, 4.05, 19.5, 3.05, color=C["pass_c"], lw=2.5)

# FAIL label + arrow looping back to LLM
txt(ax, 1.55, 5.55, "FAIL", size=11, color=C["fail_c"], weight="bold")
txt(ax, 1.55, 5.25, "(rewrite)", size=8.5, color=C["fail_c"], weight="normal")
txt(ax, 1.55, 4.97, "up to 3×", size=8, color=C["text_m"], weight="normal")
arr(ax, 3.5, 4.05, 4.5, 6.55, color=C["fail_c"], lw=2.5, rad=-0.35)

# ── Commit layer ──────────────────────────────────────────────────────────────
phase_bg(ax, 0.4, 0.3, 21.2, 2.75, C["commit"], C["border4"],
         "COMMIT TO KNOWLEDGE BASES")

commit_cols = [
    (1.0,  "FAISS Index",         "retriever.add_text()",      C["faiss"]),
    (6.2,  "Historical KG",       "kg.add_facts()",            C["kg"]),
    (11.4, "Current State Graph", "kg._update_state_graph()",  "#58a6ff"),
    (16.6, "World State",         "ws.update_from_facts()",    C["ws"]),
]
for cx, title, sub, col in commit_cols:
    box(ax, cx, 0.48, 4.5, 1.65, "#161b22", ec=col, lw=1.8, radius=0.25)
    txt(ax, cx + 2.25, 1.55, title, size=9.5, color=col)
    txt(ax, cx + 2.25, 1.22, sub,   size=8,   color=C["text_m"], weight="normal")
    ax.text(cx + 2.25, 0.78, "●", fontsize=18, color=col,
            ha="center", va="center", alpha=0.55, zorder=5)

# arrows from PASS down into commit boxes
arr(ax, 19.5, 3.05, 18.85, 2.13, color=C["pass_c"], lw=2.0)
for target_x in [3.25, 8.45, 13.65, 18.85]:
    arr(ax, 18.85, 2.13, target_x, 2.13, color=C["pass_c"], lw=1.6)

# ── Legend ────────────────────────────────────────────────────────────────────
legend = [
    (C["faiss"],  "FAISS Dense Retrieval"),
    (C["kg"],     "Knowledge Graph"),
    (C["ws"],     "World State Manager"),
    (C["llm"],    "LLM Generation"),
    (C["pass_c"], "Verified  →  commit"),
    (C["fail_c"], "Contradiction  →  rewrite"),
]
for i, (col, label) in enumerate(legend):
    lx = 0.6 + i * 3.6
    ax.plot([lx, lx + 0.4], [0.18, 0.18], color=col, lw=3,
            solid_capstyle="round", zorder=6)
    ax.text(lx + 0.55, 0.18, label, fontsize=7.5, color=C["text_m"],
            va="center", zorder=6, fontfamily="DejaVu Sans")

plt.tight_layout(pad=0.2)
plt.savefig("architecture_diagram.png", dpi=200, bbox_inches="tight",
            facecolor=C["bg"], edgecolor="none")
print("Saved: architecture_diagram.png")
