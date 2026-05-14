import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules.database import (
    init_db, get_complaints, get_complaint_by_id,
    update_complaint, get_chatbot_config, save_chatbot_config, get_stats
)
from modules import llm as llm_module

st.set_page_config(
    page_title="San Carlo — Gestione Reclami",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()

# ── Session State ────────────────────────────────────────────────────────────
if "selected_complaint" not in st.session_state:
    st.session_state.selected_complaint = None
if "show_config" not in st.session_state:
    st.session_state.show_config = False
if "toast" not in st.session_state:
    st.session_state.toast = None
if "draft_response" not in st.session_state:
    st.session_state.draft_response = {}

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, .stDeployButton { display: none !important; }
[data-testid="stSidebar"] { display: none !important; }
.block-container { padding: 1rem 2rem 2rem 2rem !important; max-width: 100% !important; }

/* Header */
.admin-header {
    display: flex; align-items: center; padding: 16px 0 20px 0;
    border-bottom: 3px solid #D42B2B; margin-bottom: 24px;
}
.admin-logo {
    background: #D42B2B; color: #FFD700; font-weight: 900;
    font-size: 16px; padding: 6px 12px; border-radius: 4px;
    font-family: Arial Black, Arial, sans-serif; line-height: 1.1;
    text-align: center; margin-right: 16px;
}
.admin-title { font-size: 22px; font-weight: bold; color: #222; flex: 1; }
.admin-subtitle { font-size: 13px; color: #888; }

/* KPI cards */
.kpi-card {
    background: white; border-radius: 12px; padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07); border-top: 4px solid #D42B2B;
    text-align: center;
}
.kpi-value { font-size: 36px; font-weight: 900; color: #D42B2B; font-family: Arial Black; }
.kpi-label { font-size: 13px; color: #666; margin-top: 4px; }
.kpi-delta { font-size: 12px; margin-top: 4px; }
.kpi-card.blue { border-top-color: #2980b9; }
.kpi-card.blue .kpi-value { color: #2980b9; }
.kpi-card.green { border-top-color: #27ae60; }
.kpi-card.green .kpi-value { color: #27ae60; }
.kpi-card.orange { border-top-color: #e67e22; }
.kpi-card.orange .kpi-value { color: #e67e22; }
.kpi-card.purple { border-top-color: #8e44ad; }
.kpi-card.purple .kpi-value { color: #8e44ad; }

/* Status badges */
.badge {
    display: inline-block; padding: 3px 10px; border-radius: 12px;
    font-size: 12px; font-weight: bold;
}
.badge-aperto { background: #fdecea; color: #c0392b; }
.badge-lavorazione { background: #fef3e2; color: #e67e22; }
.badge-attesa { background: #e8f4fd; color: #2980b9; }
.badge-chiuso { background: #eafaf1; color: #27ae60; }
.badge-automatico { background: #f4ecf7; color: #8e44ad; }

/* Priority */
.prio-alta { color: #c0392b; font-weight: bold; }
.prio-media { color: #e67e22; font-weight: bold; }
.prio-bassa { color: #27ae60; }

/* Detail panel */
.detail-panel {
    background: white; border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 24px;
}
.detail-section-title {
    font-size: 14px; font-weight: bold; color: #D42B2B;
    text-transform: uppercase; letter-spacing: 0.5px;
    margin-bottom: 12px; padding-bottom: 6px;
    border-bottom: 1px solid #f0f0f0;
}
.info-row { display: flex; gap: 8px; margin-bottom: 8px; font-size: 14px; }
.info-label { color: #888; min-width: 140px; }
.info-value { color: #222; font-weight: 500; }

/* Timeline */
.timeline-item {
    display: flex; gap: 12px; margin-bottom: 12px; align-items: flex-start;
}
.timeline-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: #D42B2B; margin-top: 5px; flex-shrink: 0;
}
.timeline-content { font-size: 13px; }
.timeline-date { color: #999; font-size: 12px; }

/* Photo placeholder */
.photo-placeholder {
    background: #f5f5f5; border: 2px dashed #ddd; border-radius: 8px;
    padding: 20px; text-align: center; color: #aaa; font-size: 13px;
}

/* Config panel */
.config-panel {
    background: white; border-radius: 12px; padding: 24px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.config-title { font-size: 18px; font-weight: bold; color: #222; margin-bottom: 16px; }

/* Toast */
.toast-success {
    position: fixed; top: 20px; right: 20px; z-index: 9999;
    background: #27ae60; color: white; padding: 14px 24px;
    border-radius: 8px; font-weight: bold; font-size: 14px;
    box-shadow: 0 4px 20px rgba(39,174,96,0.4);
    animation: fadeInOut 3s forwards;
}
@keyframes fadeInOut {
    0%{opacity:0;transform:translateY(-10px)}
    10%{opacity:1;transform:translateY(0)}
    80%{opacity:1}
    100%{opacity:0}
}

/* Streamlit table styling */
[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Toast notification ───────────────────────────────────────────────────────
if st.session_state.toast:
    st.markdown(f'<div class="toast-success">✓ {st.session_state.toast}</div>', unsafe_allow_html=True)
    st.session_state.toast = None

# ── Header ───────────────────────────────────────────────────────────────────
col_logo, col_title, col_gear = st.columns([1, 8, 1])
with col_logo:
    st.markdown('<div class="admin-logo"><span>SAN</span><br><span>CARLO</span></div>', unsafe_allow_html=True)
with col_title:
    st.markdown('<div class="admin-title">Gestione Reclami San Carlo</div><div class="admin-subtitle">Dashboard operativa interna — Customer Care</div>', unsafe_allow_html=True)
with col_gear:
    if st.button("⚙️ Config", key="open_config"):
        st.session_state.show_config = not st.session_state.show_config
        st.session_state.selected_complaint = None

# ── Config Panel ─────────────────────────────────────────────────────────────
if st.session_state.show_config:
    config = get_chatbot_config()
    st.markdown('<div class="config-panel">', unsafe_allow_html=True)
    st.markdown("### ⚙️ Configurazione CarloBot")
    st.markdown("---")

    # API Key section
    st.markdown("**🔑 Anthropic API Key**")
    current_key = config.get("anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    key_status = "✅ Configurata" if llm_module.is_configured(config) else "⚠️ Non configurata — CarloBot usa modalità offline"
    st.markdown(f'<small style="color:#666;">{key_status}</small>', unsafe_allow_html=True)
    new_api_key = st.text_input(
        "Anthropic API Key",
        value=current_key,
        type="password",
        placeholder="sk-ant-...",
        label_visibility="collapsed",
        key="cfg_api_key",
        help="La chiave viene salvata in data/chatbot_config.json (solo uso locale demo)",
    )
    model_options = [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6",
        "claude-opus-4-7",
    ]
    current_model = config.get("model", "claude-haiku-4-5-20251001")
    if current_model not in model_options:
        model_options.insert(0, current_model)
    new_model = st.selectbox("Modello Claude", model_options,
                             index=model_options.index(current_model), key="cfg_model")
    st.markdown("---")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.markdown("**📚 Common Knowledge Chatbot**")
        new_knowledge = st.text_area(
            "Conoscenze base del chatbot",
            value=config.get("common_knowledge", ""),
            height=220, label_visibility="collapsed", key="cfg_knowledge"
        )
    with col_c2:
        st.markdown("**📋 Regole di Classificazione Reclami**")
        new_rules = st.text_area(
            "Regole classificazione",
            value=config.get("classification_rules", ""),
            height=220, label_visibility="collapsed", key="cfg_rules"
        )
    col_s1, col_s2, _ = st.columns([1, 1, 4])
    with col_s1:
        if st.button("💾 Salva configurazione", type="primary"):
            save_chatbot_config({
                "common_knowledge": new_knowledge,
                "classification_rules": new_rules,
                "anthropic_api_key": new_api_key.strip(),
                "model": new_model,
            })
            # Also set env var for current process
            if new_api_key.strip():
                os.environ["ANTHROPIC_API_KEY"] = new_api_key.strip()
            st.session_state.toast = "Configurazione salvata con successo"
            st.session_state.show_config = False
            st.rerun()
    with col_s2:
        if st.button("✕ Annulla"):
            st.session_state.show_config = False
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("---")

# ── Main Tabs ────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📋 Gestione Reclami", "📊 Analisi Reclami"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — GESTIONE RECLAMI
# ════════════════════════════════════════════════════════════════════════════
with tab1:

    if st.session_state.selected_complaint:
        # ── DETAIL VIEW ──────────────────────────────────────────────────────
        complaint = get_complaint_by_id(st.session_state.selected_complaint)
        if not complaint:
            st.error("Reclamo non trovato.")
            st.session_state.selected_complaint = None
            st.rerun()

        cid = complaint["id"]
        if st.button("← Torna alla lista", key="back_list"):
            st.session_state.selected_complaint = None
            st.rerun()

        st.markdown(f"### Reclamo #{cid} — {complaint['customer_name']}")

        col_d1, col_d2 = st.columns([3, 2])

        with col_d1:
            st.markdown('<div class="detail-panel">', unsafe_allow_html=True)
            st.markdown('<div class="detail-section-title">Dati Reclamo</div>', unsafe_allow_html=True)

            status_color = {
                "Aperto": "badge-aperto", "In lavorazione": "badge-lavorazione",
                "In attesa cliente": "badge-attesa", "Chiuso": "badge-chiuso",
                "Chiuso automaticamente": "badge-automatico"
            }.get(complaint["status"], "badge-aperto")

            prio_color = {"Alta": "prio-alta", "Media": "prio-media", "Bassa": "prio-bassa"}.get(
                complaint.get("priority", ""), "")

            st.markdown(f"""
            <div class="info-row"><span class="info-label">ID Reclamo</span><span class="info-value">#{cid}</span></div>
            <div class="info-row"><span class="info-label">Data apertura</span><span class="info-value">{complaint['created_at'][:16]}</span></div>
            <div class="info-row"><span class="info-label">Cliente</span><span class="info-value">{complaint['customer_name']}</span></div>
            <div class="info-row"><span class="info-label">Email</span><span class="info-value">{complaint['customer_email']}</span></div>
            <div class="info-row"><span class="info-label">Prodotto</span><span class="info-value">{complaint['product']}</span></div>
            <div class="info-row"><span class="info-label">Categoria</span><span class="info-value">{complaint['problem_category']}</span></div>
            <div class="info-row"><span class="info-label">Codice lotto</span><span class="info-value">{complaint.get('lot_code','—')}</span></div>
            <div class="info-row"><span class="info-label">Scadenza</span><span class="info-value">{complaint.get('expiry_date','—')}</span></div>
            <div class="info-row"><span class="info-label">Punto vendita</span><span class="info-value">{complaint.get('purchase_location','—') or '—'}</span></div>
            <div class="info-row"><span class="info-label">Canale</span><span class="info-value">{complaint['channel']}</span></div>
            <div class="info-row"><span class="info-label">Classificazione</span><span class="info-value">{complaint.get('classification','—')}</span></div>
            <div class="info-row"><span class="info-label">Risposta automatica</span><span class="info-value">{'✅ Sì' if complaint.get('auto_response') else '❌ No'}</span></div>
            <div class="info-row"><span class="info-label">Stato</span><span class="info-value"><span class="badge {status_color}">{complaint['status']}</span></span></div>
            <div class="info-row"><span class="info-label">Priorità</span><span class="info-value"><span class="{prio_color}">{complaint.get('priority','—')}</span></span></div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown('<div class="detail-section-title">Descrizione cliente</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="background:#f9f9f9;padding:14px;border-radius:8px;font-size:14px;line-height:1.6;">{complaint["description"]}</div>', unsafe_allow_html=True)

            st.markdown("---")
            st.markdown('<div class="detail-section-title">Allegati</div>', unsafe_allow_html=True)
            if complaint.get("has_photo"):
                st.markdown('<div class="photo-placeholder">📸 Foto confezione allegata<br><small>Clicca per visualizzare</small></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="photo-placeholder">📎 Nessuna foto allegata</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

        with col_d2:
            # Timeline
            st.markdown('<div class="detail-panel" style="margin-bottom:16px;">', unsafe_allow_html=True)
            st.markdown('<div class="detail-section-title">Timeline</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <strong>Reclamo aperto</strong><br>
                <span class="timeline-date">{complaint['created_at'][:16]}</span>
              </div>
            </div>
            <div class="timeline-item">
              <div class="timeline-dot" style="background:#2980b9;"></div>
              <div class="timeline-content">
                <strong>Classificazione: {complaint.get('classification','—')}</strong><br>
                <span class="timeline-date">Automatica</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
            if complaint.get("auto_response"):
                st.markdown("""
                <div class="timeline-item">
                  <div class="timeline-dot" style="background:#8e44ad;"></div>
                  <div class="timeline-content"><strong>Risposta automatica inviata</strong></div>
                </div>
                """, unsafe_allow_html=True)
            if complaint.get("closed_at"):
                st.markdown(f"""
                <div class="timeline-item">
                  <div class="timeline-dot" style="background:#27ae60;"></div>
                  <div class="timeline-content">
                    <strong>Reclamo chiuso</strong><br>
                    <span class="timeline-date">{complaint['closed_at'][:16]}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # AI Response editor
            st.markdown('<div class="detail-panel">', unsafe_allow_html=True)
            st.markdown('<div class="detail-section-title">Risposta AI proposta</div>', unsafe_allow_html=True)

            draft_key = f"draft_{cid}"
            if draft_key not in st.session_state.draft_response:
                st.session_state.draft_response[draft_key] = complaint.get("ai_response", "")

            edited = st.text_area(
                "Modifica la risposta prima di inviarla",
                value=st.session_state.draft_response[draft_key],
                height=200, key=f"response_edit_{cid}"
            )
            st.session_state.draft_response[draft_key] = edited

            st.markdown('<div style="font-size:12px;color:#888;margin-bottom:8px;">💡 Puoi modificare il testo prima di inviarlo al cliente</div>', unsafe_allow_html=True)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("📨 Invia risposta", key=f"send_{cid}", use_container_width=True):
                    update_complaint(cid, {"ai_response": edited})
                    st.session_state.toast = f"Risposta inviata a {complaint['customer_email']}"
                    st.rerun()
            with col_btn2:
                if st.button("✅ Invia e chiudi", key=f"send_close_{cid}", use_container_width=True, type="primary"):
                    update_complaint(cid, {
                        "ai_response": edited,
                        "status": "Chiuso",
                        "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    st.session_state.toast = f"Risposta inviata e reclamo #{cid} chiuso"
                    st.session_state.selected_complaint = None
                    st.rerun()

            col_btn3, col_btn4 = st.columns(2)
            with col_btn3:
                if st.button("💾 Salva bozza", key=f"draft_{cid}_btn", use_container_width=True):
                    update_complaint(cid, {"ai_response": edited})
                    st.session_state.toast = "Bozza salvata"
                    st.rerun()
            with col_btn4:
                new_status = st.selectbox(
                    "Cambia stato",
                    ["Aperto", "In lavorazione", "In attesa cliente", "Chiuso"],
                    index=["Aperto", "In lavorazione", "In attesa cliente", "Chiuso"].index(
                        complaint["status"] if complaint["status"] in
                        ["Aperto", "In lavorazione", "In attesa cliente", "Chiuso"] else "Aperto"
                    ),
                    key=f"status_sel_{cid}"
                )
                if st.button("Aggiorna stato", key=f"upd_status_{cid}"):
                    update_complaint(cid, {"status": new_status})
                    st.session_state.toast = f"Stato aggiornato: {new_status}"
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

    else:
        # ── LIST VIEW ─────────────────────────────────────────────────────────
        # KPI row
        all_data = get_stats()
        df_all = pd.DataFrame(all_data) if all_data else pd.DataFrame()

        col_k1, col_k2, col_k3, col_k4, col_k5, col_k6 = st.columns(6)
        if not df_all.empty:
            total = len(df_all)
            open_c = len(df_all[df_all["status"] == "Aperto"])
            auto_c = len(df_all[df_all["status"] == "Chiuso automaticamente"])
            pending = len(df_all[df_all["status"].isin(["Aperto", "In lavorazione"])])
            closed = df_all[df_all["closed_at"].notna()]
            if not closed.empty:
                closed = closed.copy()
                closed["days"] = (
                    pd.to_datetime(closed["closed_at"]) - pd.to_datetime(closed["created_at"])
                ).dt.days
                avg_days = round(closed["days"].mean(), 1)
            else:
                avg_days = "—"
            top_cat = df_all["problem_category"].mode()[0] if not df_all.empty else "—"
        else:
            total = open_c = auto_c = pending = 0
            avg_days = "—"
            top_cat = "—"

        with col_k1:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value">{total}</div><div class="kpi-label">Reclami totali</div></div>', unsafe_allow_html=True)
        with col_k2:
            st.markdown(f'<div class="kpi-card blue"><div class="kpi-value">{open_c}</div><div class="kpi-label">Aperti</div></div>', unsafe_allow_html=True)
        with col_k3:
            st.markdown(f'<div class="kpi-card purple"><div class="kpi-value">{auto_c}</div><div class="kpi-label">Chiusi automaticamente</div></div>', unsafe_allow_html=True)
        with col_k4:
            st.markdown(f'<div class="kpi-card orange"><div class="kpi-value">{pending}</div><div class="kpi-label">Da gestire</div></div>', unsafe_allow_html=True)
        with col_k5:
            st.markdown(f'<div class="kpi-card green"><div class="kpi-value">{avg_days}</div><div class="kpi-label">Giorni medi chiusura</div></div>', unsafe_allow_html=True)
        with col_k6:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="font-size:18px;">{top_cat}</div><div class="kpi-label">Categoria più frequente</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Filters
        col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 3])
        with col_f1:
            f_status = st.selectbox("Stato", ["Tutti", "Aperto", "In lavorazione", "In attesa cliente", "Chiuso", "Chiuso automaticamente"], key="f_status")
        with col_f2:
            cats = ["Tutte"] + sorted(df_all["problem_category"].unique().tolist()) if not df_all.empty else ["Tutte"]
            f_cat = st.selectbox("Categoria", cats, key="f_cat")
        with col_f3:
            f_channel = st.selectbox("Canale", ["Tutti", "chatbot", "email", "telefono", "social"], key="f_channel")
        with col_f4:
            f_search = st.text_input("🔍 Ricerca (nome, prodotto, descrizione)", key="f_search", placeholder="Cerca...")

        filters = {
            "status": f_status, "category": f_cat,
            "channel": f_channel, "search": f_search
        }
        complaints = get_complaints(filters)

        if not complaints:
            st.info("Nessun reclamo trovato con i filtri selezionati.")
        else:
            st.markdown(f"**{len(complaints)} reclami trovati**")

            # Table
            for c in complaints[:50]:  # show first 50 for perf
                status_emoji = {
                    "Aperto": "🔴", "In lavorazione": "🟡",
                    "In attesa cliente": "🔵", "Chiuso": "🟢",
                    "Chiuso automaticamente": "🟣"
                }.get(c["status"], "⚪")
                prio_emoji = {"Alta": "🔺", "Media": "🔸", "Bassa": "🔹"}.get(c.get("priority", ""), "")

                col_id, col_dt, col_cli, col_prod, col_cat, col_st, col_prio, col_ch, col_act = st.columns([1, 2, 2, 2, 2, 2, 1, 1, 1])
                with col_id:
                    st.markdown(f"**#{c['id']}**")
                with col_dt:
                    st.markdown(f"<small>{c['created_at'][:10]}</small>", unsafe_allow_html=True)
                with col_cli:
                    st.markdown(f"<small>{c['customer_name']}</small>", unsafe_allow_html=True)
                with col_prod:
                    st.markdown(f"<small>{c['product']}</small>", unsafe_allow_html=True)
                with col_cat:
                    st.markdown(f"<small>{c['problem_category']}</small>", unsafe_allow_html=True)
                with col_st:
                    st.markdown(f"<small>{status_emoji} {c['status']}</small>", unsafe_allow_html=True)
                with col_prio:
                    st.markdown(f"<small>{prio_emoji}</small>", unsafe_allow_html=True)
                with col_ch:
                    st.markdown(f"<small>{c['channel']}</small>", unsafe_allow_html=True)
                with col_act:
                    col_open, col_close = st.columns(2)
                    with col_open:
                        if st.button("📂", key=f"open_{c['id']}", help="Apri"):
                            st.session_state.selected_complaint = c["id"]
                            st.rerun()
                    with col_close:
                        if c["status"] not in ("Chiuso", "Chiuso automaticamente"):
                            if st.button("✓", key=f"close_{c['id']}", help="Chiudi"):
                                update_complaint(c["id"], {
                                    "status": "Chiuso",
                                    "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                })
                                st.session_state.toast = f"Reclamo #{c['id']} chiuso"
                                st.rerun()

                st.markdown('<hr style="margin:4px 0;border:none;border-top:1px solid #f0f0f0;">', unsafe_allow_html=True)

            if len(complaints) > 50:
                st.info(f"Mostrati 50 di {len(complaints)} reclami. Usa i filtri per restringere la ricerca.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — ANALISI
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    all_data = get_stats()
    if not all_data:
        st.warning("Nessun dato disponibile. Eseguire init_data.py per generare dati mock.")
    else:
        df = pd.DataFrame(all_data)
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["month"] = df["created_at"].dt.to_period("M").astype(str)
        df["closed_at"] = pd.to_datetime(df["closed_at"], errors="coerce")

        # ── Filters ──────────────────────────────────────────────────────────
        st.markdown("### Filtri")
        col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns(5)
        with col_a1:
            min_d = df["created_at"].min().date()
            max_d = df["created_at"].max().date()
            date_from = st.date_input("Da", value=min_d, key="an_from")
        with col_a2:
            date_to = st.date_input("A", value=max_d, key="an_to")
        with col_a3:
            prods = ["Tutti"] + sorted(df["product"].unique().tolist())
            sel_prod = st.selectbox("Prodotto", prods, key="an_prod")
        with col_a4:
            cats2 = ["Tutte"] + sorted(df["problem_category"].unique().tolist())
            sel_cat = st.selectbox("Categoria", cats2, key="an_cat")
        with col_a5:
            sel_ch = st.selectbox("Canale", ["Tutti", "chatbot", "email", "telefono", "social"], key="an_ch")

        # Apply filters
        dff = df.copy()
        dff = dff[(dff["created_at"].dt.date >= date_from) & (dff["created_at"].dt.date <= date_to)]
        if sel_prod != "Tutti":
            dff = dff[dff["product"] == sel_prod]
        if sel_cat != "Tutte":
            dff = dff[dff["problem_category"] == sel_cat]
        if sel_ch != "Tutti":
            dff = dff[dff["channel"] == sel_ch]

        if dff.empty:
            st.warning("Nessun dato nel periodo selezionato.")
        else:
            RED = "#D42B2B"
            PALETTE = [RED, "#FFD700", "#2980b9", "#27ae60", "#8e44ad", "#e67e22", "#1abc9c", "#e74c3c", "#95a5a6", "#f39c12"]

            # KPIs row
            col_k1, col_k2, col_k3, col_k4, col_k5, col_k6 = st.columns(6)
            total = len(dff)
            open_c = len(dff[dff["status"] == "Aperto"])
            auto_c = len(dff[dff["status"] == "Chiuso automaticamente"])
            pending = len(dff[dff["status"].isin(["Aperto", "In lavorazione"])])
            closed_df = dff[dff["closed_at"].notna()].copy()
            avg_days = round((closed_df["closed_at"] - closed_df["created_at"]).dt.days.mean(), 1) if not closed_df.empty else "—"
            top_cat = dff["problem_category"].mode()[0]

            with col_k1:
                st.markdown(f'<div class="kpi-card"><div class="kpi-value">{total}</div><div class="kpi-label">Totale reclami</div></div>', unsafe_allow_html=True)
            with col_k2:
                st.markdown(f'<div class="kpi-card blue"><div class="kpi-value">{open_c}</div><div class="kpi-label">Aperti</div></div>', unsafe_allow_html=True)
            with col_k3:
                st.markdown(f'<div class="kpi-card purple"><div class="kpi-value">{auto_c}</div><div class="kpi-label">Chiusi automaticamente</div></div>', unsafe_allow_html=True)
            with col_k4:
                st.markdown(f'<div class="kpi-card orange"><div class="kpi-value">{pending}</div><div class="kpi-label">Da gestire</div></div>', unsafe_allow_html=True)
            with col_k5:
                st.markdown(f'<div class="kpi-card green"><div class="kpi-value">{avg_days}</div><div class="kpi-label">Giorni medi chiusura</div></div>', unsafe_allow_html=True)
            with col_k6:
                st.markdown(f'<div class="kpi-card"><div class="kpi-value" style="font-size:16px;">{top_cat}</div><div class="kpi-label">Categoria top</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Charts row 1 ──────────────────────────────────────────────────
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                monthly = dff.groupby("month").size().reset_index(name="count")
                fig1 = px.bar(monthly, x="month", y="count", title="Reclami per mese",
                              color_discrete_sequence=[RED])
                fig1.update_layout(xaxis_title="", yaxis_title="N. reclami",
                                   plot_bgcolor="white", paper_bgcolor="white",
                                   title_font_size=16, margin=dict(t=40, b=10))
                fig1.update_xaxes(tickangle=45)
                st.plotly_chart(fig1, use_container_width=True)

            with col_g2:
                cat_counts = dff["problem_category"].value_counts().reset_index()
                cat_counts.columns = ["categoria", "count"]
                fig2 = px.pie(cat_counts, names="categoria", values="count",
                              title="Reclami per categoria", color_discrete_sequence=PALETTE,
                              hole=0.35)
                fig2.update_layout(title_font_size=16, margin=dict(t=40, b=10))
                st.plotly_chart(fig2, use_container_width=True)

            # ── Charts row 2 ──────────────────────────────────────────────────
            col_g3, col_g4 = st.columns(2)
            with col_g3:
                prod_counts = dff["product"].value_counts().reset_index()
                prod_counts.columns = ["prodotto", "count"]
                fig3 = px.bar(prod_counts, x="count", y="prodotto", orientation="h",
                              title="Reclami per prodotto", color_discrete_sequence=[RED])
                fig3.update_layout(yaxis=dict(autorange="reversed"),
                                   plot_bgcolor="white", paper_bgcolor="white",
                                   title_font_size=16, margin=dict(t=40, b=10),
                                   xaxis_title="N. reclami", yaxis_title="")
                st.plotly_chart(fig3, use_container_width=True)

            with col_g4:
                ch_counts = dff["channel"].value_counts().reset_index()
                ch_counts.columns = ["canale", "count"]
                fig4 = px.pie(ch_counts, names="canale", values="count",
                              title="Distribuzione canali", color_discrete_sequence=PALETTE,
                              hole=0.35)
                fig4.update_layout(title_font_size=16, margin=dict(t=40, b=10))
                st.plotly_chart(fig4, use_container_width=True)

            # ── Charts row 3 ──────────────────────────────────────────────────
            col_g5, col_g6 = st.columns(2)
            with col_g5:
                auto_vs_manual = dff["classification"].value_counts().reset_index()
                auto_vs_manual.columns = ["tipo", "count"]
                auto_vs_manual["tipo"] = auto_vs_manual["tipo"].map(
                    {"semplice": "Risposta automatica", "complesso": "Gestito dal team"}
                )
                fig5 = px.pie(auto_vs_manual, names="tipo", values="count",
                              title="Automatico vs Team qualità",
                              color_discrete_sequence=["#8e44ad", RED], hole=0.35)
                fig5.update_layout(title_font_size=16, margin=dict(t=40, b=10))
                st.plotly_chart(fig5, use_container_width=True)

            with col_g6:
                if not closed_df.empty:
                    closed_df2 = closed_df.copy()
                    closed_df2["days_to_close"] = (closed_df2["closed_at"] - closed_df2["created_at"]).dt.days
                    avg_by_cat = closed_df2.groupby("problem_category")["days_to_close"].mean().round(1).reset_index()
                    avg_by_cat.columns = ["categoria", "giorni_medi"]
                    avg_by_cat = avg_by_cat.sort_values("giorni_medi", ascending=True)
                    fig6 = px.bar(avg_by_cat, x="giorni_medi", y="categoria", orientation="h",
                                  title="Tempo medio chiusura per categoria (giorni)",
                                  color_discrete_sequence=[RED])
                    fig6.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                       title_font_size=14, margin=dict(t=40, b=10),
                                       xaxis_title="Giorni medi", yaxis_title="")
                    st.plotly_chart(fig6, use_container_width=True)
                else:
                    st.info("Nessun reclamo chiuso nel periodo selezionato.")

            # ── Top 5 prodotti ────────────────────────────────────────────────
            st.markdown("### 🏆 Top 5 prodotti con più reclami")
            top5 = dff["product"].value_counts().head(5).reset_index()
            top5.columns = ["Prodotto", "N. Reclami"]
            top5.index = range(1, len(top5) + 1)
            st.dataframe(top5, use_container_width=True)
