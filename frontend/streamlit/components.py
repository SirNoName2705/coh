import streamlit as st

STRATEGY_OPTIONS = {
    "organic_discussion": "Organische Diskussion",
    "agenda_voting": "Agenda & Voting",
}

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

    manual_agents = []
    if not auto_mod:
        manual_agents = st.sidebar.multiselect(
            "Custom Council zusammenstellen",
            ["dale_carnegie", "daniel_kahneman", "jack_nasher", "robert_b_cialdini", "roman_braun", "thorsten_havener", "michael_ehlers"],
            default=["dale_carnegie", "daniel_kahneman"],
            disabled=st.session_state.is_streaming
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


import streamlit as st


def render_message(msg: dict):
    m_type = msg.get("type")

    if m_type == "user":
        with st.chat_message("user"):
            st.markdown(msg.get("content", ""))

    elif m_type == "hero":
        agent_name = msg.get("agent", "Held")
        with st.chat_message("assistant", avatar="🏛️"):
            st.markdown(f"### :{'blue'}[{agent_name}]")

            # Monolog im einklappbaren Expander kapseln
            monologue = msg.get("inner_monologue", "").strip()
            if monologue:
                with st.expander("💭 Gedankengang / Monolog", expanded=False):
                    st.markdown(f"*{monologue}*")

            spoken = msg.get("spoken_text", "").strip()
            if spoken:
                st.markdown(spoken)

    elif m_type == "info":
        # Subtiler Hinweis statt auffälliger Zwischenruf
        st.caption(f"ℹ️ {msg.get('content', '')}")

    elif m_type == "error":
        st.error(f"⚠️ {msg.get('content', '')}", icon="🚨")

# def render_message(msg: dict):
#     m_type = msg.get("type")
#
#     if m_type == "user":
#         with st.chat_message("user"):
#             st.markdown(msg.get("content", ""))
#     elif m_type == "hero":
#         agent_name = msg.get("agent", "Held")
#         with st.chat_message("assistant", avatar="🏛️"):
#             st.markdown(f"**:{'blue'}[{agent_name}]**")
#             monologue = msg.get("inner_monologue", "").strip()
#             if monologue:
#                 st.info(f"💭 *{monologue}*")
#             spoken = msg.get("spoken_text", "").strip()
#             if spoken:
#                 st.markdown(spoken)
#     elif m_type == "info":
#         st.caption(f"--- {msg.get('content', '')} ---")
#     elif m_type == "error":
#         st.error(f"⚠️ {msg.get('content', '')}")