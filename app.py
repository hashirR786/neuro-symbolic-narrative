"""
Streamlit dashboard for the Neuro-Symbolic RAG Interactive Narrative system.

Layout
──────
  Left  (2/3) — Story chat interface
  Right (1/3) — Knowledge Graph + world-state panel

Right panel tabs
────────────────
  Graph       — interactive KG visualization with view/filter controls
  World State — character + item dossiers
  Metrics     — CS / KGCS / TCS / CCS / ICS / HR / RF live gauges
  Violations  — contradiction log with rule + involved entities
"""

import os
import streamlit as st

# ── Push Streamlit Cloud secrets into os.environ so LLMManager can read them ──
# This is a no-op in local development (secrets dict is empty there).
for _k, _v in st.secrets.items():
    if isinstance(_v, str):
        os.environ.setdefault(_k, _v)

st.set_page_config(
    page_title="Neuro-Symbolic Narrative",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.story_engine import StoryEngine
from src.schema import ViolationReport
from src.visualization import GraphView, build_figure, _PYVIS_AVAILABLE

# ──────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ──────────────────────────────────────────────────────────────────────────────

if "engine" not in st.session_state:
    st.session_state.engine = StoryEngine(use_neurosymbolic=True)
if "history" not in st.session_state:
    st.session_state.history = [
        {
            "role": "assistant",
            "content": (
                "Welcome to the **Neuro-Symbolic RAG Interactive Narrative**.\n\n"
                "Begin your story by introducing a character and a setting. "
                "The system will track every established fact in a live Knowledge Graph "
                "and automatically detect and correct narrative inconsistencies."
            ),
        }
    ]
if "violation_log" not in st.session_state:
    st.session_state.violation_log = []

engine: StoryEngine = st.session_state.engine

# ──────────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────────

st.title("📖 Neuro-Symbolic RAG — Interactive Narrative")
st.caption(
    "Hybrid FAISS + Knowledge Graph retrieval · Symbolic verification · "
    "Self-correction · Live world-state tracking"
)

# ──────────────────────────────────────────────────────────────────────────────
# Two-column layout
# ──────────────────────────────────────────────────────────────────────────────

col_story, col_panel = st.columns([2, 1], gap="medium")

# ══════════════════════════════════════════════════════════════════════════════
# LEFT — Story
# ══════════════════════════════════════════════════════════════════════════════

with col_story:
    st.subheader("Story")

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("What happens next?")

    if user_input:
        st.session_state.history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.spinner("Generating · Extracting · Verifying…"):
            result = engine.generate_step(user_input)

        response = result["text"]
        corrections = result["corrections_made"]
        violations = [ViolationReport(**v) for v in result.get("violations", [])]

        if corrections > 0:
            response += (
                f"\n\n> ⚠️ **System**: Prevented {corrections} inconsistency error(s) "
                f"through automated verify-rewrite loops."
            )

        st.session_state.history.append({"role": "assistant", "content": response})
        if violations:
            st.session_state.violation_log.extend(result["violations"])

        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — Panel
# ══════════════════════════════════════════════════════════════════════════════

with col_panel:

    # ── Quick stats row ───────────────────────────────────────────────────────
    stats = engine.get_session_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Characters", stats["characters"])
    m2.metric("Items", stats["items"])
    m3.metric("Locations", stats["locations"])
    m4.metric("Steps", stats["total_steps"])

    tab_graph, tab_world, tab_metrics, tab_violations = st.tabs(
        ["🔵 Graph", "🌍 World State", "📊 Metrics", "⚠️ Violations"]
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 1 — Graph
    # ─────────────────────────────────────────────────────────────────────────

    with tab_graph:
        if engine.kg.graph.number_of_nodes() == 0:
            st.info("The Knowledge Graph is empty. Start the story to populate it.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                view_mode = st.selectbox(
                    "View",
                    options=["state", "character", "location", "inventory", "event", "full"],
                    index=0,
                    help=(
                        "state=latest snapshot · character=relationships · "
                        "location=positions · inventory=items · event=events · full=all"
                    ),
                )
            with c2:
                top_n = st.selectbox(
                    "Top N nodes",
                    options=[20, 50, 100, 0],
                    index=0,
                    format_func=lambda x: "All" if x == 0 else str(x),
                )

            highlight_violations = st.checkbox("Highlight violations", value=True)
            viols = engine.last_violations if highlight_violations else []

            render_mode = st.radio(
                "Renderer", ["Matplotlib", "PyVis (interactive)"],
                horizontal=True, index=0,
            )

            if render_mode == "PyVis (interactive)" and _PYVIS_AVAILABLE:
                from src.visualization import build_pyvis_html
                import streamlit.components.v1 as components
                html = build_pyvis_html(
                    engine.kg, engine.world_state,
                    mode=view_mode, top_n=top_n, violations=viols,
                )
                components.html(html, height=520, scrolling=False)
            else:
                if render_mode == "PyVis (interactive)" and not _PYVIS_AVAILABLE:
                    st.warning("pyvis not installed — falling back to Matplotlib. "
                               "Install with: `pip install pyvis`")
                fig = build_figure(
                    engine.kg, engine.world_state,
                    mode=view_mode, top_n=top_n, violations=viols,
                    figsize=(7, 6),
                )
                st.pyplot(fig, use_container_width=True)

            # Entity search
            st.markdown("---")
            search_query = st.text_input("🔍 Entity search", placeholder="Character or item name…")
            if search_query:
                found = [
                    n for n in engine.kg.graph.nodes()
                    if search_query.lower() in str(n).lower()
                ]
                if found:
                    sel = st.selectbox("Select entity", found)
                    if sel:
                        st.markdown(f"**KG Facts for '{sel}':**")
                        facts = engine.kg.get_character_context(sel)
                        with st.container(height=200):
                            for f in facts[:30]:
                                st.code(f, language="text")
                        if engine.world_state and sel in engine.world_state.characters:
                            st.markdown(engine.world_state.get_character_context(sel))
                else:
                    st.warning(f"No entity matching '{search_query}' found in the graph.")

            # Graph statistics
            with st.expander("Graph statistics"):
                g_stats = engine.kg.get_graph_stats()
                for k, v in g_stats.items():
                    st.write(f"**{k}**: {v}")

                # Community detection
                view = GraphView(engine.kg, engine.world_state, mode=view_mode, top_n=top_n)
                comms = view.get_communities()
                n_comms = len(set(comms.values()))
                st.write(f"**Communities detected**: {n_comms}")

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 2 — World State
    # ─────────────────────────────────────────────────────────────────────────

    with tab_world:
        ws = engine.world_state

        if not ws.characters and not ws.items:
            st.info("World state is empty. Start the story to populate it.")
        else:
            # Characters
            if ws.characters:
                st.markdown("### Characters")
                for name, char in ws.characters.items():
                    status_icon = "💀" if not char.is_alive else "🧑"
                    with st.expander(f"{status_icon} {name}", expanded=False):
                        c1, c2 = st.columns(2)
                        c1.write(f"**Alive**: {'Yes' if char.is_alive else 'No'}")
                        c1.write(f"**Location**: {char.location or '—'}")
                        c1.write(f"**Health**: {char.health}")
                        c1.write(f"**Faction**: {char.faction or '—'}")
                        c2.write(f"**Mood**: {char.emotional_state or '—'}")
                        c2.write(f"**Goals**: {', '.join(char.goals) or '—'}")
                        c2.write(f"**Inventory**: {', '.join(char.inventory) or '—'}")
                        if char.relationships:
                            st.write("**Relationships**:")
                            for other, rel in char.relationships.items():
                                st.write(f"  - {other}: *{rel}*")

            # Items
            if ws.items:
                st.markdown("### Items")
                for item_name, item in ws.items.items():
                    owner = item.owner or "unowned"
                    loc = item.location or "?"
                    st.write(f"🗡️ **{item_name}** — owned by *{owner}*, at *{loc}*")

            # Locations
            if ws.locations:
                st.markdown("### Known Locations")
                st.write(" · ".join(ws.locations))

            # Timeline
            if ws.timeline:
                st.markdown("### Timeline")
                with st.container(height=150):
                    for entry in reversed(ws.timeline[-20:]):
                        st.write(f"Step {entry['step']}: {entry['facts_applied']} facts applied")

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 3 — Metrics
    # ─────────────────────────────────────────────────────────────────────────

    with tab_metrics:
        st.markdown("### Consistency Metrics")

        if stats["total_steps"] == 0:
            st.info("No story steps yet — start the story to see live metrics.")
        else:
            # ── Live KGCS (lightweight) ──────────────────────────────────
            kg_stats = engine.kg.get_graph_stats()
            kgcs = min(100.0, round(
                100 * kg_stats["state_edges"] /
                max(kg_stats["historical_edges"], 1), 1
            ))

            # ── Row 1: CS, KGCS, TCS, CCS ────────────────────────────────
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CS", f"{stats['CS']}", help="Consistency Score — steps passing all checks (0–100)")
            c2.metric("KGCS", f"{kgcs}", help="KG Consistency Score — contradiction-free graph edges (0–100)")
            c3.metric("TCS", f"{stats['TCS']}", help="Temporal Consistency — no timeline violations (0–100)")
            c4.metric("CCS", f"{stats['CCS']}", help="Character Consistency — state & relationship checks (0–100)")

            # ── Row 2: ICS, HR, RF ────────────────────────────────────────
            c5, c6, c7, _ = st.columns(4)
            c5.metric("ICS", f"{stats['ICS']}", help="Inventory Consistency — ownership & transfer checks (0–100)")
            c6.metric("HR",  f"{stats['HR']}",  help="Hallucination Rate — unknown entities per step (0–1, lower is better)")
            c7.metric("RF",  f"{stats['RF']}",  help="Rewrite Frequency — avg corrections per step (lower is better)")

            # ── Compact progress bars for the 5 scored metrics ────────────
            st.markdown("---")
            for label, val, color in [
                ("CS",   stats["CS"],  "#3fb950"),
                ("KGCS", kgcs,         "#388bfd"),
                ("TCS",  stats["TCS"], "#FF9800"),
                ("CCS",  stats["CCS"], "#bc8cff"),
                ("ICS",  stats["ICS"], "#58a6ff"),
            ]:
                col_l, col_bar = st.columns([1, 4])
                col_l.caption(label)
                col_bar.progress(int(val) / 100)

            # ── Graph health ──────────────────────────────────────────────
            with st.expander("Graph health", expanded=False):
                gh1, gh2 = st.columns(2)
                gh1.caption(f"Historical nodes: **{kg_stats['historical_nodes']}**")
                gh1.caption(f"Historical edges: **{kg_stats['historical_edges']}**")
                gh1.caption(f"Archived edges:   **{kg_stats['archived_edges']}**")
                gh2.caption(f"State nodes: **{kg_stats['state_nodes']}**")
                gh2.caption(f"State edges: **{kg_stats['state_edges']}**")
                gh2.caption(f"Dead characters: **{stats['dead_characters']}**")

            st.caption(
                "TCS / CCS / ICS / HR are per-layer breakdowns of CS. "
                "Run `python -m tests.test_consistency --benchmark` for full offline reports."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 4 — Violations
    # ─────────────────────────────────────────────────────────────────────────

    with tab_violations:
        st.markdown("### Contradiction Log")

        all_violations = st.session_state.violation_log
        if not all_violations:
            st.success("No violations detected so far.")
        else:
            st.write(f"**Total violations**: {len(all_violations)}")
            with st.container(height=500):
                for i, v in enumerate(reversed(all_violations)):
                    severity = v.get("severity", "error")
                    icon = "🔴" if severity == "error" else "🟡"
                    rule = v.get("rule", "unknown")
                    desc = v.get("description", "")
                    entities = v.get("entities_involved", [])
                    step = v.get("step_id", "?")

                    with st.expander(f"{icon} [{rule}] Step {step} — {desc[:60]}…", expanded=False):
                        st.write(f"**Rule**: `{rule}`")
                        st.write(f"**Severity**: {severity}")
                        st.write(f"**Description**: {desc}")
                        if entities:
                            st.write(f"**Entities involved**: {', '.join(entities)}")

            if st.button("Clear violation log"):
                st.session_state.violation_log = []
                st.rerun()

    # ─────────────────────────────────────────────────────────────────────────
    # KG facts (raw view)
    # ─────────────────────────────────────────────────────────────────────────

    with st.expander("📋 Raw KG facts (latest 30)", expanded=False):
        facts = engine.kg.get_recent_facts_strings(30)
        if facts:
            with st.container(height=250):
                for fact in reversed(facts):
                    st.code(fact, language="text")
        else:
            st.write("No facts yet.")
