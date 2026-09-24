import streamlit as st
from pathlib import Path

STRATEGY_OPTIONS = {
    "organic_discussion": "Organische Diskussion",
    "agenda_voting": "Agenda & Voting",
    "document_review": "Dokumenten-Review",
}


def get_dynamic_agents() -> list[str]:
    """Scrapt den data/authors Ordner nach verfügbaren Personas."""
    authors_dir = Path("data/authors")
    if not authors_dir.exists():
        return ["dale_carnegie", "daniel_kahneman"]  # Fallback

    agents = []
    # Alle Ordner durchsuchen, die eine persona.yaml haben
    for d in authors_dir.iterdir():
        if d.is_dir() and (d / "persona.yaml").exists():
            agents.append(d.name)

    return sorted(agents)


def render_sidebar():
    st.sidebar.header("🏛️ Council of Heroes")
    st.sidebar.caption("Einstellungen & Steuerung")

    if st.session_state.is_streaming:
        st.sidebar.markdown("🟢 **Status:** *Rat berät sich... (Aktiv)*")
    else:
        st.sidebar.markdown("⚪ **Status:** *Bereit*")

    st.sidebar.divider()

    strategy = st.sidebar.selectbox(
        "Strategie",
        options=list(STRATEGY_OPTIONS.keys()),
        format_func=lambda x: STRATEGY_OPTIONS[x],
        disabled=st.session_state.is_streaming,
    )

    auto_mod = st.sidebar.checkbox("Moderator entscheidet", value=True, disabled=st.session_state.is_streaming)

    # Lade die Agenten dynamisch aus dem Dateisystem
    available_agents = get_dynamic_agents()

    # Sicherstellen, dass der Default-Wert existiert
    default_selection = []
    for default_agent in ["dale_carnegie", "daniel_kahneman"]:
        if default_agent in available_agents:
            default_selection.append(default_agent)

    manual_agents = []
    if not auto_mod:
        manual_agents = st.sidebar.multiselect(
            "Custom Council zusammenstellen",
            options=available_agents,
            default=default_selection if default_selection else None,
            disabled=st.session_state.is_streaming,
            # Macht aus "dale_carnegie_late" schön formatiert "Dale Carnegie Late" in der UI
            format_func=lambda x: x.replace("_", " ").title()
        )

    st.sidebar.divider()
    if st.sidebar.button("Chat leeren", disabled=st.session_state.is_streaming):
        st.session_state.messages = []
        st.rerun()

    return strategy, auto_mod, manual_agents


def format_votes(votes_list: list) -> str:
    vote_lines = []
    for v in votes_list:
        if not isinstance(v, dict):
            continue
        item = v.get("agenda_item")
        if item:
            vote_lines.append(f"📌 **{item}**")
        vote_val = v.get("vote")
        if vote_val is not None:
            decision = "✅ JA" if vote_val else "❌ NEIN"
            reason = v.get("reason") or "..."
            vote_lines.append(f"👉 **{decision}** ({reason})\n")
    return "\n".join(vote_lines)


def render_message(msg: dict):
    m_type = msg.get("type")

    if m_type == "user":
        with st.chat_message("user"):
            st.markdown(msg.get("content", ""))

    elif m_type == "hero":
        agent_name = msg.get("agent", "Held")
        with st.chat_message("assistant", avatar="🏛️"):
            # Nutzt auch hier das Formatieren für saubere Namen im Chat
            display_name = agent_name.replace("_", " ").title()
            st.markdown(f"### :{'blue'}[{display_name}]")

            # Monolog im einklappbaren Expander kapseln
            monologue = msg.get("inner_monologue", "").strip()
            if monologue:
                with st.expander("💭 Gedankengang / Monolog", expanded=False):
                    st.markdown(f"*{monologue}*")

            spoken = msg.get("spoken_text", "").strip()
            if spoken:
                st.markdown(spoken)

    elif m_type == "info":
        st.caption(f"ℹ️ {msg.get('content', '')}")

    elif m_type == "error":
        st.error(f"⚠️ {msg.get('content', '')}", icon="🚨")