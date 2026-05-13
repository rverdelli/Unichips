import streamlit as st
from modules.database import init_db
from modules.chatbot import init_state, process_message

st.set_page_config(
    page_title="San Carlo - Il gusto che ci piace",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()

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

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ---- Global reset ---- */
#MainMenu, header, footer, .stDeployButton { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stAppViewContainer"] { background: #fff; }
[data-testid="stSidebar"] { display: none !important; }

/* ---- San Carlo site wrapper ---- */
.sc-site { font-family: Arial, Helvetica, sans-serif; background: #fff; }

/* ---- Header ---- */
.sc-header {
    display: flex; align-items: center;
    padding: 12px 40px; background: #fff;
    border-bottom: 2px solid #e0e0e0;
}
.sc-logo { font-size: 0; }
.sc-logo-box {
    background: #D42B2B; color: #FFD700; font-weight: 900;
    font-size: 22px; padding: 8px 14px; border-radius: 4px;
    line-height: 1.1; text-align: center; letter-spacing: -0.5px;
    font-family: Arial Black, Arial, sans-serif;
}
.sc-logo-box span { display: block; }
.sc-social {
    margin-left: auto; display: flex; gap: 10px; align-items: center;
}
.sc-social-label { font-size: 13px; color: #555; margin-right: 4px; }
.sc-social a {
    display: inline-block; width: 28px; height: 28px; border-radius: 50%;
    text-align: center; line-height: 28px; font-size: 14px; text-decoration: none;
}
.sc-fb { background: #1877F2; color: #fff; }
.sc-tw { background: #1DA1F2; color: #fff; }
.sc-yt { background: #FF0000; color: #fff; }
.sc-ig { background: #E4405F; color: #fff; }
.sc-intl {
    margin-left: 20px; font-size: 12px; color: #888; border: 1px solid #ddd;
    padding: 4px 8px; border-radius: 3px;
}

/* ---- Nav menu ---- */
.sc-nav {
    background: #D42B2B; display: flex; align-items: stretch;
    padding: 0 40px;
}
.sc-nav a {
    color: #fff; text-decoration: none; font-size: 13px; font-weight: bold;
    padding: 12px 16px; text-transform: uppercase; letter-spacing: 0.3px;
    white-space: nowrap; transition: background 0.2s;
}
.sc-nav a:hover { background: #b02020; }

/* ---- Red divider ---- */
.sc-divider { height: 3px; background: #D42B2B; margin: 0; }

/* ---- Hero ---- */
.sc-hero {
    background: linear-gradient(135deg, #fff9f9 0%, #fff 60%, #fffaf0 100%);
    padding: 50px 40px; text-align: center;
    border-bottom: 1px solid #f0f0f0;
}
.sc-hero-title {
    font-size: 36px; font-weight: 900; color: #D42B2B;
    font-family: Arial Black, Arial, sans-serif; margin-bottom: 8px;
}
.sc-hero-sub { font-size: 17px; color: #555; margin-bottom: 40px; }
.sc-products {
    display: flex; justify-content: center; gap: 24px; flex-wrap: wrap;
}
.sc-product-card {
    background: #fff; border: 1px solid #eee; border-radius: 12px;
    padding: 20px 16px; width: 160px; text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06); transition: transform 0.2s, box-shadow 0.2s;
    cursor: default;
}
.sc-product-card:hover { transform: translateY(-4px); box-shadow: 0 6px 24px rgba(212,43,43,0.12); }
.sc-product-icon { font-size: 48px; margin-bottom: 8px; }
.sc-product-name { font-size: 13px; font-weight: bold; color: #333; }
.sc-product-sub { font-size: 11px; color: #888; margin-top: 4px; }
.sc-product-badge {
    display: inline-block; background: #D42B2B; color: #fff;
    font-size: 10px; font-weight: bold; padding: 2px 7px; border-radius: 10px;
    margin-top: 6px; text-transform: uppercase;
}

/* ---- Section ---- */
.sc-section {
    padding: 50px 40px; background: #fafafa; border-bottom: 1px solid #eee;
}
.sc-section-title {
    font-size: 26px; font-weight: 900; color: #D42B2B;
    font-family: Arial Black, Arial, sans-serif; margin-bottom: 24px;
    text-align: center;
}
.sc-quality-cards { display: flex; gap: 24px; justify-content: center; flex-wrap: wrap; }
.sc-quality-card {
    background: #fff; border-radius: 12px; padding: 28px 24px; width: 220px;
    text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.07);
}
.sc-quality-icon { font-size: 40px; margin-bottom: 12px; }
.sc-quality-label { font-size: 14px; font-weight: bold; color: #333; }
.sc-quality-desc { font-size: 12px; color: #777; margin-top: 6px; }

/* ---- Footer ---- */
.sc-footer {
    background: #222; color: #aaa; padding: 30px 40px;
    font-size: 12px; text-align: center;
}
.sc-footer a { color: #D42B2B; text-decoration: none; }

/* ── Floating chat button ── */
.chat-fab {
    position: fixed; bottom: 28px; right: 28px; z-index: 9999;
    width: 64px; height: 64px; border-radius: 50%;
    background: #D42B2B; color: #fff; border: none;
    font-size: 28px; cursor: pointer;
    box-shadow: 0 4px 20px rgba(212,43,43,0.5);
    display: flex; align-items: center; justify-content: center;
    transition: transform 0.2s, box-shadow 0.2s;
}
.chat-fab:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(212,43,43,0.6); }
.chat-badge {
    position: absolute; top: -4px; right: -4px;
    background: #FFD700; color: #333; font-size: 11px; font-weight: bold;
    width: 20px; height: 20px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
}

/* ── Chat panel ── */
.chat-panel-wrapper {
    position: fixed; bottom: 105px; right: 28px; z-index: 9998;
    width: 420px;
    animation: slideUp 0.25s ease;
}
@keyframes slideUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
}
.chat-panel {
    background: #fff; border-radius: 18px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.18);
    overflow: hidden; display: flex; flex-direction: column;
    max-height: 600px;
}
.chat-header {
    background: #D42B2B; color: #fff;
    padding: 16px 20px; display: flex; align-items: center; gap: 12px;
}
.chat-avatar {
    width: 40px; height: 40px; border-radius: 50%;
    background: #fff; display: flex; align-items: center;
    justify-content: center; font-size: 22px;
}
.chat-header-info { flex: 1; }
.chat-header-name { font-weight: bold; font-size: 16px; }
.chat-header-status { font-size: 12px; opacity: 0.85; }
.chat-header-close {
    background: rgba(255,255,255,0.2); border: none; color: #fff;
    border-radius: 50%; width: 30px; height: 30px; cursor: pointer;
    font-size: 16px; display: flex; align-items: center; justify-content: center;
}
.chat-body {
    flex: 1; overflow-y: auto; padding: 16px; background: #f7f7f7;
    display: flex; flex-direction: column; gap: 12px;
    max-height: 380px;
}
.msg-bot, .msg-user { display: flex; gap: 8px; }
.msg-user { flex-direction: row-reverse; }
.msg-bubble {
    max-width: 85%; padding: 10px 14px; border-radius: 16px;
    font-size: 14px; line-height: 1.5;
}
.msg-bot .msg-bubble {
    background: #fff; color: #222;
    border-bottom-left-radius: 4px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.msg-user .msg-bubble {
    background: #D42B2B; color: #fff;
    border-bottom-right-radius: 4px;
}
.msg-bot-icon {
    width: 32px; height: 32px; border-radius: 50%;
    background: #D42B2B; color: #fff; font-size: 16px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; align-self: flex-end;
}
.chat-suggestions {
    padding: 8px 16px; display: flex; flex-wrap: wrap; gap: 8px;
    background: #f7f7f7;
}
.sug-btn {
    background: #fff; border: 1.5px solid #D42B2B; color: #D42B2B;
    border-radius: 20px; padding: 6px 14px; font-size: 13px;
    cursor: pointer; transition: all 0.15s; font-family: inherit;
}
.sug-btn:hover { background: #D42B2B; color: #fff; }
.chat-input-area {
    padding: 12px 16px; background: #fff;
    border-top: 1px solid #eee; display: flex; gap: 8px; align-items: center;
}
.upload-hint {
    padding: 6px 16px; background: #fff8f8; border-top: 1px solid #f5dede;
    font-size: 12px; color: #888; display: flex; align-items: center; gap: 8px;
}
.upload-ok { color: #27ae60; font-weight: bold; }

/* Streamlit widget styling inside chat */
div[data-testid="stChatInput"] > div { border-radius: 24px !important; }
</style>
""", unsafe_allow_html=True)

# ── San Carlo Site HTML ──────────────────────────────────────────────────────
st.markdown("""
<div class="sc-site">

<!-- HEADER -->
<div class="sc-header">
  <div class="sc-logo">
    <div class="sc-logo-box">
      <span>SAN</span>
      <span>CARLO</span>
    </div>
  </div>
  <div class="sc-social">
    <span class="sc-social-label">Seguici:</span>
    <a class="sc-fb" href="#" onclick="return false;">f</a>
    <a class="sc-tw" href="#" onclick="return false;">t</a>
    <a class="sc-yt" href="#" onclick="return false;">▶</a>
    <a class="sc-ig" href="#" onclick="return false;">◎</a>
    <span class="sc-intl">🌐 International website</span>
  </div>
</div>

<!-- NAV -->
<div class="sc-nav">
  <a href="#" onclick="return false;">l'azienda</a>
  <a href="#" onclick="return false;">prodotti</a>
  <a href="#" onclick="return false;">nutrizionalità</a>
  <a href="#" onclick="return false;">processo produttivo</a>
  <a href="#" onclick="return false;">concorsi</a>
  <a href="#" onclick="return false;">comunicazione e sponsorizzazioni</a>
  <a href="#" onclick="return false;">servizio al trade</a>
</div>

<!-- HERO -->
<div class="sc-hero">
  <div class="sc-hero-title">Il gusto che ci piace</div>
  <div class="sc-hero-sub">Scopri tutte le nostre linee di prodotti, dal 1936 con la stessa passione</div>
  <div class="sc-products">
    <div class="sc-product-card">
      <div class="sc-product-icon">🥔</div>
      <div class="sc-product-name">Più Gusto</div>
      <div class="sc-product-sub">Vivace al pomodoro</div>
      <div class="sc-product-badge">Novità</div>
    </div>
    <div class="sc-product-card">
      <div class="sc-product-icon">🌿</div>
      <div class="sc-product-name">Più Gusto</div>
      <div class="sc-product-sub">Lime e Pepe Rosa</div>
    </div>
    <div class="sc-product-card">
      <div class="sc-product-icon">🍄</div>
      <div class="sc-product-name">Più Gusto</div>
      <div class="sc-product-sub">Tartufo</div>
      <div class="sc-product-badge">Premium</div>
    </div>
    <div class="sc-product-card">
      <div class="sc-product-icon">🥩</div>
      <div class="sc-product-name">Più Gusto</div>
      <div class="sc-product-sub">Porchetta</div>
    </div>
    <div class="sc-product-card">
      <div class="sc-product-icon">🌽</div>
      <div class="sc-product-name">Veggy Good</div>
      <div class="sc-product-sub">Senza glutine</div>
      <div class="sc-product-badge">Veggy</div>
    </div>
    <div class="sc-product-card">
      <div class="sc-product-icon">🍿</div>
      <div class="sc-product-name">Pop Corn</div>
      <div class="sc-product-sub">San Carlo</div>
    </div>
  </div>
</div>

<div class="sc-divider"></div>

<!-- QUALITA' SECTION -->
<div class="sc-section">
  <div class="sc-section-title">La nostra qualità</div>
  <div class="sc-quality-cards">
    <div class="sc-quality-card">
      <div class="sc-quality-icon">🌾</div>
      <div class="sc-quality-label">Materie prime selezionate</div>
      <div class="sc-quality-desc">Patate italiane di alta qualità, selezionate con cura</div>
    </div>
    <div class="sc-quality-card">
      <div class="sc-quality-icon">🏭</div>
      <div class="sc-quality-label">Processo produttivo</div>
      <div class="sc-quality-desc">Controlli qualità costanti in ogni fase della produzione</div>
    </div>
    <div class="sc-quality-card">
      <div class="sc-quality-icon">🔬</div>
      <div class="sc-quality-label">Laboratorio interno</div>
      <div class="sc-quality-desc">Analisi continue per garantire sicurezza e qualità</div>
    </div>
    <div class="sc-quality-card">
      <div class="sc-quality-icon">♻️</div>
      <div class="sc-quality-label">Sostenibilità</div>
      <div class="sc-quality-desc">Impegno continuo per ridurre l'impatto ambientale</div>
    </div>
  </div>
</div>

<!-- FOOTER -->
<div class="sc-footer">
  <p>© 2024 San Carlo Gruppo Alimentare S.p.A. — Via Caboto 19, Milano</p>
  <p><a href="#" onclick="return false;">Privacy Policy</a> · <a href="#" onclick="return false;">Cookie Policy</a> · <a href="#" onclick="return false;">Note Legali</a></p>
</div>

</div>
""", unsafe_allow_html=True)

# ── Chat Toggle Button ───────────────────────────────────────────────────────
col_spacer, col_btn = st.columns([10, 1])
with col_btn:
    if st.button("💬", key="fab_open", help="Apri CarloBot"):
        st.session_state.chat_open = not st.session_state.chat_open
        st.rerun()

# Style the FAB button
st.markdown("""
<style>
div[data-testid="stButton"] button[kind="secondary"] {
    position: fixed; bottom: 28px; right: 28px; z-index: 9999;
    width: 64px !important; height: 64px !important;
    border-radius: 50% !important; background: #D42B2B !important;
    color: white !important; font-size: 26px !important;
    border: none !important; box-shadow: 0 4px 20px rgba(212,43,43,0.45) !important;
    padding: 0 !important;
    transition: transform 0.2s !important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
    transform: scale(1.08) !important;
    background: #b02020 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Chat Panel ───────────────────────────────────────────────────────────────
if st.session_state.chat_open:
    with st.container():
        st.markdown("""
        <style>
        .chat-container-outer {
            position: fixed; bottom: 105px; right: 28px; z-index: 9998;
            width: 420px;
        }
        .chat-header-bar {
            background: #D42B2B; border-radius: 18px 18px 0 0;
            padding: 14px 18px; display: flex; align-items: center; gap: 12px;
            color: white;
        }
        .chat-title { font-weight: bold; font-size: 16px; flex: 1; }
        .chat-subtitle { font-size: 12px; opacity: 0.85; }
        </style>
        <div class="chat-container-outer">
          <div class="chat-header-bar">
            <div style="font-size:24px;">🤖</div>
            <div style="flex:1;">
              <div class="chat-title">CarloBot</div>
              <div class="chat-subtitle">● Online · Assistente Virtuale San Carlo</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # We render the actual chat using Streamlit native in a styled container
    st.markdown('<div style="position:fixed;bottom:105px;right:28px;width:420px;z-index:9997;">', unsafe_allow_html=True)

    with st.container():
        # Messages display
        chat_html = '<div style="background:#f7f7f7;padding:14px 16px;max-height:340px;overflow-y:auto;border-left:1px solid #eee;border-right:1px solid #eee;">'
        for msg in st.session_state.messages:
            if msg["role"] == "bot":
                chat_html += f"""
                <div style="display:flex;gap:8px;margin-bottom:12px;align-items:flex-end;">
                  <div style="width:32px;height:32px;border-radius:50%;background:#D42B2B;color:white;
                              display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;">🤖</div>
                  <div style="background:white;border-radius:16px 16px 16px 4px;padding:10px 14px;
                              font-size:13px;max-width:85%;box-shadow:0 1px 4px rgba(0,0,0,0.08);line-height:1.5;">
                    {msg['text'].replace(chr(10), '<br>').replace('**', '<b>').replace('**', '</b>')}
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

        # Suggestions
        if st.session_state.suggestions:
            sug_cols = st.columns(len(st.session_state.suggestions))
            for i, sug in enumerate(st.session_state.suggestions):
                with sug_cols[i]:
                    if st.button(sug, key=f"sug_{i}_{sug[:10]}", use_container_width=True):
                        # Process suggestion click
                        st.session_state.messages.append({"role": "user", "text": sug})
                        reply, new_state, new_sugs = process_message(sug, st.session_state.chat_state)
                        st.session_state.chat_state = new_state
                        st.session_state.messages.append({"role": "bot", "text": reply})
                        st.session_state.suggestions = new_sugs

                        # Show upload button if collecting
                        if new_state.get("phase") == "collecting":
                            st.session_state.show_upload = True
                        st.rerun()

        # Photo upload simulation
        if st.session_state.show_upload and not st.session_state.photo_uploaded:
            col_up1, col_up2 = st.columns([3, 1])
            with col_up1:
                st.markdown('<div style="font-size:12px;color:#888;padding:4px 0;">📎 Allega foto confezione (opzionale)</div>', unsafe_allow_html=True)
            with col_up2:
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

        # Close button + input
        close_col, _ = st.columns([1, 4])
        with close_col:
            if st.button("✕ Chiudi", key="close_chat"):
                st.session_state.chat_open = False
                st.rerun()

        # Text input
        user_input = st.chat_input("Scrivi un messaggio...", key="chat_input_field")
        if user_input:
            st.session_state.messages.append({"role": "user", "text": user_input})
            reply, new_state, new_sugs = process_message(user_input, st.session_state.chat_state)
            st.session_state.chat_state = new_state
            st.session_state.messages.append({"role": "bot", "text": reply})
            st.session_state.suggestions = new_sugs
            if new_state.get("phase") == "collecting":
                st.session_state.show_upload = True
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ── Fixed panel CSS wrapper ──────────────────────────────────────────────────
st.markdown("""
<style>
/* Push all Streamlit content out of sight except our chat */
section.main > div.block-container {
    padding-top: 0 !important;
}
/* Make the chat_input box appear at fixed bottom-right inside our panel */
div[data-testid="stChatInputContainer"] {
    position: fixed !important;
    bottom: 108px !important;
    right: 28px !important;
    width: 420px !important;
    z-index: 10000 !important;
    border-radius: 0 0 18px 18px !important;
    border: 1px solid #eee !important;
    background: white !important;
    box-shadow: 0 8px 40px rgba(0,0,0,0.18) !important;
}
</style>
""", unsafe_allow_html=True)
