import streamlit as st
from components import render_sidebar, render_message, format_votes
from api_client import stream_chat

st.set_page_config(page_title="Council of Heroes", page_icon="🏛️", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "is_streaming" not in st.session_state:
    st.session_state.is_streaming = False

# Sidebar laden und Parameter holen
strategy, auto_mod, manual_agents = render_sidebar()

st.title("Council of Heroes")

for msg in st.session_state.messages:
    render_message(msg)

prompt = st.chat_input("Sprich zum Rat...", disabled=st.session_state.is_streaming)

if prompt:
    st.session_state.messages.append({"type": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Der Bug ist hier gefixt: manual_agents wird jetzt korrekt übergeben!
    payload = {
        "query": prompt,
        "stream": True,
        "strategy": strategy,
        "auto_select_agents": auto_mod,
        "manual_agents": manual_agents,
    }

    st.session_state.is_streaming = True

    try:
        current_hero = None
        current_hero_placeholder = None

        for data in stream_chat(payload):
            status = data.get("status")

            if status == "starting_agent":
                agent_name = data.get("agent", "Experte")
                current_hero = {"type": "hero", "agent": agent_name, "inner_monologue": "", "spoken_text": ""}
                st.session_state.messages.append(current_hero)
                with st.chat_message("assistant", avatar="🏛️"):
                    current_hero_placeholder = st.empty()
                    current_hero_placeholder.markdown(f"**:{'blue'}[{agent_name}]**\n\n*denkt nach...*")

            elif status == "info":
                info_text = data.get("message", "")
                st.session_state.messages.append({"type": "info", "content": info_text})
                st.caption(f"--- {info_text} ---")
                current_hero = None
                current_hero_placeholder = None

            elif status == "error":
                err_text = data.get("message", "Unbekannter Fehler")
                st.session_state.messages.append({"type": "error", "content": f"Systemfehler: {err_text}"})
                st.error(f"⚠️ Systemfehler: {err_text}")
                current_hero = None
                current_hero_placeholder = None

            elif status == "agent_done":
                # Cursor beim Beenden des Agenten-Turns entfernen
                if current_hero and current_hero_placeholder:
                    display_md = f"**:{'blue'}[{current_hero['agent']}]**\n\n"
                    if current_hero["inner_monologue"]:
                        display_md += f"> 💭 *{current_hero['inner_monologue']}*\n\n"
                    if current_hero["spoken_text"]:
                        display_md += f"{current_hero['spoken_text']}\n"
                    current_hero_placeholder.markdown(display_md)
                current_hero = None
                current_hero_placeholder = None

            else:
                if current_hero and current_hero_placeholder:
                    if data.get("inner_monologue"):
                        current_hero["inner_monologue"] = data["inner_monologue"]

                    # NEU: Das "Enthalten" (Abstain) Feature abfangen
                    if data.get("abstain"):
                        current_hero["spoken_text"] = "*[Enthält sich der Stimme, da kein neuer Input]*"
                    elif data.get("spoken_text"):
                        current_hero["spoken_text"] = data["spoken_text"]

                    if "votes" in data and isinstance(data["votes"], list):
                        current_hero["spoken_text"] = format_votes(data["votes"])

                    # UI live aktualisieren
                    display_md = f"**:{'blue'}[{current_hero['agent']}]**\n\n"
                    if current_hero["inner_monologue"]:
                        display_md += f"> 💭 *{current_hero['inner_monologue']}*\n\n"
                    if current_hero["spoken_text"]:
                        display_md += f"{current_hero['spoken_text']}\n"

                    current_hero_placeholder.markdown(display_md + " ▌")

    except Exception as e:
        err_msg = {"type": "error", "content": f"Verbindung zum Rat unterbrochen: {e}"}
        st.session_state.messages.append(err_msg)
        st.error(f"⚠️ {err_msg['content']}")

    finally:
        st.session_state.is_streaming = False
        # st.rerun()