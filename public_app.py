import base64
import logging
from pathlib import Path

import streamlit as st

from modules.database import init_db, get_chatbot_config
from modules.chatbot import init_state, process_message
from modules import llm as llm_module

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

st.set_page_config(
    page_title="San Carlo - Il gusto che ci piace",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()

# ── Background image (base64 so Streamlit can embed it in CSS) ───────────────
_bg_path = Path(__file__).parent / "assets" / "sancarlo_bg.jpg"
_bg_b64 = base64.b64encode(_bg_path.read_bytes()).decode() if _bg_path.exists() else ""
_bg_css = f"url('data:image/jpeg;base64,{_bg_b64}')" if _bg_b64 else "linear-gradient(135deg,#D42B2B,#fff)"

# ── Session state ────────────────────────────────────────────────────────────
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False
if "chat_state" not in st.session_state:
    st.session_state.chat_state = init_state()
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "bot",
            "text": (
                "Ciao, sono **CarloBot**, l'assistente virtuale San Carlo! 🔴\n\n"
                "Posso aiutarti con informazioni sui prodotti, ingredienti e segnalazioni. "
                "Come posso esserti utile?"
            ),
        }
    ]
if "suggestions" not in st.session_state:
    st.session_state.suggestions = [
        "Voglio sottoporre un reclamo",
        "Dove trovo il lotto sulla confezione?",
        "Avete prodotti senza glutine?",
    ]
if "show_upload" not in st.session_state:
    st.session_state.show_upload = False
if "photo_uploaded" not in st.session_state:
    st.session_state.photo_uploaded = False

# ── Global CSS ───────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
/* ── Hide Streamlit chrome ── */
#MainMenu, header, footer, .stDeployButton {{ display: none !important; }}
[data-testid="stSidebar"] {{ display: none !important; }}
.block-container {{ padding: 0 !important; max-width: 100% !important; }}

/* ── Full-page background ── */
[data-testid="stAppViewContainer"] {{
    background-image: {_bg_css};
    background-size: cover;
    background-position: center top;
    background-repeat: no-repeat;
    background-attachment: fixed;
    min-height: 100vh;
}}

/* ── FAB button ── */
div[data-testid="stButton"] > button {{
    position: fixed !important;
    bottom: 28px !important;
    right: 28px !important;
    z-index: 9999 !important;
    width: 64px !important;
    height: 64px !important;
    border-radius: 50% !important;
    background: #D42B2B !important;
    color: white !important;
    font-size: 28px !important;
    border: none !important;
    box-shadow: 0 4px 24px rgba(212,43,43,0.55) !important;
    padding: 0 !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
    line-height: 1 !important;
}}
div[data-testid="stButton"] > button:hover {{
    transform: scale(1.1) !important;
    box-shadow: 0 6px 32px rgba(212,43,43,0.7) !important;
    background: #b02020 !important;
}}

/* ── Chat panel header (pure HTML) ── */
.chat-header-bar {{
    background: #D42B2B;
    border-radius: 18px 18px 0 0;
    padding: 14px 18px;
    display: flex;
    align-items: center;
    gap: 12px;
    color: white;
    position: fixed;
    bottom: 548px;
    right: 28px;
    width: 420px;
    z-index: 9998;
    box-shadow: 0 -2px 20px rgba(0,0,0,0.12);
}}
.chat-title {{ font-weight: bold; font-size: 16px; flex: 1; }}
.chat-subtitle {{ font-size: 12px; opacity: 0.85; }}

/* ── Chat messages area ── */
.chat-messages {{
    position: fixed;
    bottom: 200px;
    right: 28px;
    width: 420px;
    max-height: 340px;
    overflow-y: auto;
    background: #f7f7f7;
    border-left: 1px solid #eee;
    border-right: 1px solid #eee;
    padding: 14px 16px;
    z-index: 9997;
    box-sizing: border-box;
}}

/* ── Suggestion buttons row ── */
.sug-row {{
    position: fixed;
    bottom: 160px;
    right: 28px;
    width: 420px;
    background: #f7f7f7;
    border-left: 1px solid #eee;
    border-right: 1px solid #eee;
    padding: 8px 12px;
    z-index: 9997;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    box-sizing: border-box;
}}

/* ── Chat input container ── */
div[data-testid="stChatInputContainer"] {{
    position: fixed !important;
    bottom: 108px !important;
    right: 28px !important;
    width: 420px !important;
    z-index: 10000 !important;
    border-radius: 0 0 18px 18px !important;
    border: 1px solid #eee !important;
    border-top: none !important;
    background: white !important;
    box-shadow: 0 8px 40px rgba(0,0,0,0.18) !important;
}}

/* ── Streamlit suggestion buttons ── */
div[data-testid="stHorizontalBlock"] button {{
    position: static !important;
    width: auto !important;
    height: auto !important;
    border-radius: 20px !important;
    background: white !important;
    color: #D42B2B !important;
    border: 1.5px solid #D42B2B !important;
    font-size: 12px !important;
    padding: 4px 12px !important;
    box-shadow: none !important;
    font-weight: normal !important;
}}
div[data-testid="stHorizontalBlock"] button:hover {{
    background: #D42B2B !important;
    color: white !important;
    transform: none !important;
}}

/* ── Close / upload buttons ── */
div[data-testid="stColumns"] button {{
    position: static !important;
    width: auto !important;
    height: auto !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    padding: 4px 10px !important;
    box-shadow: none !important;
}}
</style>
""", unsafe_allow_html=True)

# ── FAB toggle button ─────────────────────────────────────────────────────────
label = "✕" if st.session_state.chat_open else "💬"
if st.button(label, key="fab_toggle"):
    st.session_state.chat_open = not st.session_state.chat_open
    st.rerun()

# ── Chat panel ────────────────────────────────────────────────────────────────
if st.session_state.chat_open:

    # Header bar (pure HTML, fixed position via CSS)
    st.markdown("""
    <div class="chat-header-bar">
      <div style="font-size:24px;">🤖</div>
      <div style="flex:1;">
        <div class="chat-title">CarloBot</div>
        <div class="chat-subtitle">● Online · Assistente Virtuale San Carlo</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Messages
    chat_html = '<div class="chat-messages">'
    for msg in st.session_state.messages:
        if msg["role"] == "bot":
            # Simple bold markdown conversion for display
            text = msg["text"].replace("**", "〈b〉", 1)
            while "〈b〉" in text:
                text = text.replace("〈b〉", "<b>", 1).replace("〈b〉", "</b>", 1)
            text = text.replace("\n", "<br>")
            chat_html += f"""
            <div style="display:flex;gap:8px;margin-bottom:12px;align-items:flex-end;">
              <div style="width:32px;height:32px;border-radius:50%;background:#D42B2B;color:white;
                          display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;">🤖</div>
              <div style="background:white;border-radius:16px 16px 16px 4px;padding:10px 14px;
                          font-size:13px;max-width:85%;box-shadow:0 1px 4px rgba(0,0,0,0.08);line-height:1.5;">
                {text}
              </div>
            </div>"""
        else:
            chat_html += f"""
            <div style="display:flex;gap:8px;margin-bottom:12px;justify-content:flex-end;">
              <div style="background:#D42B2B;color:white;border-radius:16px 16px 4px 16px;
                          padding:10px 14px;font-size:13px;max-width:85%;line-height:1.5;">
                {msg['text']}
              </div>
            </div>"""
    chat_html += "</div>"
    st.markdown(chat_html, unsafe_allow_html=True)

    # Suggestion buttons
    if st.session_state.suggestions:
        sug_cols = st.columns(len(st.session_state.suggestions))
        for i, sug in enumerate(st.session_state.suggestions):
            with sug_cols[i]:
                if st.button(sug, key=f"sug_{i}_{sug[:12]}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "text": sug})
                    reply, new_state, new_sugs = process_message(
                        sug, st.session_state.chat_state, st.session_state.messages
                    )
                    st.session_state.chat_state = new_state
                    st.session_state.messages.append({"role": "bot", "text": reply})
                    st.session_state.suggestions = new_sugs
                    if new_state.get("phase") == "collecting":
                        st.session_state.show_upload = True
                    st.rerun()

    # Photo upload (simulated)
    if st.session_state.show_upload and not st.session_state.photo_uploaded:
        up_col1, up_col2 = st.columns([3, 1])
        with up_col1:
            st.markdown('<div style="font-size:12px;color:#888;padding:4px 0;">📎 Allega foto confezione (opzionale)</div>', unsafe_allow_html=True)
        with up_col2:
            if st.button("📷 Carica", key="upload_photo"):
                st.session_state.photo_uploaded = True
                st.session_state.messages.append({
                    "role": "bot",
                    "text": "📎 Foto ricevuta, grazie! Puoi continuare con le informazioni mancanti."
                })
                st.session_state.chat_state["collected"]["has_photo"] = True
                st.rerun()

    if st.session_state.photo_uploaded:
        st.markdown('<div style="font-size:12px;color:#27ae60;padding:2px 8px;">✓ Foto allegata</div>', unsafe_allow_html=True)

    # Offline warning
    _cfg = get_chatbot_config()
    if not llm_module.is_configured(_cfg):
        st.markdown(
            '<div style="background:#fff8e1;border-left:3px solid #FFD700;'
            'padding:6px 12px;font-size:11px;color:#666;">'
            '⚠️ Modalità offline — configura la API Key nel pannello Admin per abilitare l\'AI.</div>',
            unsafe_allow_html=True,
        )

    # Text input
    user_input = st.chat_input("Scrivi un messaggio...", key="chat_input_field")
    if user_input:
        st.session_state.messages.append({"role": "user", "text": user_input})
        reply, new_state, new_sugs = process_message(
            user_input, st.session_state.chat_state, st.session_state.messages
        )
        st.session_state.chat_state = new_state
        st.session_state.messages.append({"role": "bot", "text": reply})
        st.session_state.suggestions = new_sugs
        if new_state.get("phase") == "collecting":
            st.session_state.show_upload = True
        st.rerun()
