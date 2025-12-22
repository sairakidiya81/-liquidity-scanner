#!/usr/bin/env python3
"""
Liquidity Grab Scanner Dashboard - Cloud Version
Works with live yfinance data (no cache required)
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import os
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Liquidity Scanner", 
    layout="wide", 
    initial_sidebar_state="expanded",
    page_icon="📊"
)

# Settings
PERIOD = "6mo"
SWING_LEFT = 2
SWING_RIGHT = 2

# Simple Clean CSS
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .main-header {
        background: linear-gradient(90deg, #1e3a5f, #2d5a87);
        padding: 20px 30px;
        border-radius: 10px;
        margin-bottom: 20px;
        border-left: 4px solid #00d4ff;
    }
    .main-header h1 { color: #ffffff; font-size: 1.8em; margin: 0; font-weight: 600; }
    .main-header p { color: #a0c4e8; margin: 5px 0 0 0; font-size: 0.95em; }
    [data-testid="stSidebar"] { background-color: #161b22; }
    .metric-card {
        background: #1e2530;
        padding: 15px 20px;
        border-radius: 8px;
        border-left: 3px solid #00d4ff;
        margin: 5px 0;
    }
    .metric-card h3 { color: #8b949e; font-size: 0.85em; margin: 0; font-weight: 400; }
    .metric-card .value { color: #ffffff; font-size: 1.8em; font-weight: 600; margin: 5px 0 0 0; }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>📊 Liquidity Grab Scanner</h1>
    <p>Multi-Index • Multi-Sector • Daily Analysis</p>
</div>
""", unsafe_allow_html=True)

# ========== HELPER FUNCTIONS ==========
@st.cache_data(ttl=3600)  # Cache for 1 hour
def download_data(ticker):
    """Download data from yfinance"""
    try:
        df = yf.download(ticker, period=PERIOD, interval="1d", progress=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return pd.DataFrame()

def find_swing_low(df, idx, left=2, right=2):
    """Check if index is a swing low"""
    if idx < left or idx >= len(df) - right:
        return False
    current_low = df['Low'].iloc[idx]
    for i in range(1, left + 1):
        if df['Low'].iloc[idx - i] <= current_low:
            return False
    for i in range(1, right + 1):
        if df['Low'].iloc[idx + i] <= current_low:
            return False
    return True

def detect_liquidity_grab(df):
    """Detect liquidity grab patterns"""
    if len(df) < 20:
        return df
    
    df = df.copy()
    df['swing_low'] = None
    df['liq_grab'] = False
    df['grab_depth'] = 0.0
    
    # Find swing lows
    swing_lows = []
    for i in range(SWING_LEFT, len(df) - SWING_RIGHT):
        if find_swing_low(df, i, SWING_LEFT, SWING_RIGHT):
            swing_lows.append((i, df['Low'].iloc[i]))
            df.iloc[i, df.columns.get_loc('swing_low')] = df['Low'].iloc[i]
    
    # Detect liquidity grabs
    for idx in range(len(df)):
        if idx < SWING_LEFT + SWING_RIGHT:
            continue
            
        current_low = df['Low'].iloc[idx]
        current_close = df['Close'].iloc[idx]
        
        for swing_idx, swing_low in swing_lows:
            if swing_idx >= idx:
                continue
            if swing_idx < idx - 50:
                continue
                
            # Liquidity grab: wick below swing, close above swing
            if current_low < swing_low and current_close > swing_low:
                depth = (swing_low - current_low) / swing_low * 100
                if depth > 0.05:
                    df.iloc[idx, df.columns.get_loc('liq_grab')] = True
                    df.iloc[idx, df.columns.get_loc('grab_depth')] = depth
                    break
    
    return df

def get_alerts(ticker, df):
    """Get alerts from dataframe"""
    alerts = []
    if 'liq_grab' not in df.columns:
        return alerts
    
    grabs = df[df['liq_grab'] == True]
    
    for idx, row in grabs.iterrows():
        date_str = idx.strftime('%d-%b-%Y') if hasattr(idx, 'strftime') else str(idx)
        depth = row.get('grab_depth', 0)
        price = row.get('Close', 0)
        alert = f"[1D] {ticker} @ {date_str} | Rs.{price:.2f} (Depth: {depth:.2f}%)"
        alerts.append((idx, alert))
    
    return alerts

# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown("### ⚙️ Scan Settings")
    st.success("🌐 Live Data Mode")
    st.markdown("---")
    
    scan_type = st.radio("📁 Select Scan Type", ["INDEX", "SECTOR"], horizontal=True)
    
    selected_files = []
    
    if scan_type == "INDEX":
        index_path = "INDEX CSV"
        if os.path.exists(index_path):
            all_files = sorted([f for f in os.listdir(index_path) if f.endswith('.csv')])
            selected_ui = st.multiselect("Select Indices", all_files, default=["nifty50.csv"] if "nifty50.csv" in all_files else all_files[:1])
            selected_files = [os.path.join(index_path, f) for f in selected_ui]
        else:
            st.warning("INDEX CSV folder not found")
            
    else:  # SECTOR
        sector_path = "SECTORS CSV"
        if os.path.exists(sector_path):
            all_files = sorted([f for f in os.listdir(sector_path) if f.endswith('.csv')])
            selected_ui = st.multiselect("Select Sectors", all_files, default=all_files[:2] if len(all_files) >= 2 else all_files)
            selected_files = [os.path.join(sector_path, f) for f in selected_ui]
        else:
            st.warning("SECTORS CSV folder not found")
    
    st.markdown("---")
    days_filter = st.slider("Show signals from last N days", 1, 30, 10)
    st.markdown("---")
    scan_clicked = st.button("🚀 Start Scan", use_container_width=True, type="primary")

# ========== MAIN CONTENT ==========
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""<div class="metric-card"><h3>Data Mode</h3><div class="value">🌐 Live</div></div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""<div class="metric-card"><h3>Period</h3><div class="value">{PERIOD}</div></div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""<div class="metric-card"><h3>Selected Files</h3><div class="value">{len(selected_files)}</div></div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div class="metric-card"><h3>Last Update</h3><div class="value">{datetime.now().strftime('%d-%b')}</div></div>""", unsafe_allow_html=True)

st.markdown("---")

# ========== SCAN ==========
if scan_clicked:
    if not selected_files:
        st.error("⚠️ Please select at least one file!")
    else:
        progress = st.progress(0)
        status = st.empty()
        
        all_alerts = {}
        total = len(selected_files)
        cutoff_date = datetime.now() - timedelta(days=days_filter)
        
        for idx, csv_file in enumerate(selected_files):
            file_name = os.path.basename(csv_file).replace('.csv', '').upper()
            status.info(f"🔄 Scanning: {file_name} ({idx+1}/{total})")
            
            try:
                tickers_df = pd.read_csv(csv_file, header=None)
                tickers = tickers_df.iloc[:, 0].astype(str).str.strip().tolist()
                
                file_alerts = {}
                ticker_progress = st.empty()
                
                for t_idx, ticker in enumerate(tickers):
                    ticker_progress.text(f"   Downloading: {ticker} ({t_idx+1}/{len(tickers)})")
                    
                    df = download_data(ticker)
                    if df.empty:
                        continue
                    
                    df = detect_liquidity_grab(df)
                    alerts = get_alerts(ticker, df)
                    
                    # Filter by date
                    recent_alerts = [(dt, alert) for dt, alert in alerts if dt >= cutoff_date]
                    
                    if recent_alerts:
                        file_alerts[ticker] = [a[1] for a in recent_alerts]
                
                ticker_progress.empty()
                
                if file_alerts:
                    all_alerts[file_name] = file_alerts
                    
            except Exception as e:
                st.warning(f"Error in {file_name}: {str(e)[:40]}")
            
            progress.progress((idx + 1) / total)
        
        progress.empty()
        status.empty()
        
        # ========== RESULTS ==========
        st.markdown("## 📋 Scan Results")
        
        if not all_alerts:
            st.info(f"ℹ️ No signals found in last {days_filter} days.")
        else:
            total_signals = sum(sum(len(a) for a in f.values()) for f in all_alerts.values())
            total_stocks = sum(len(f) for f in all_alerts.values())
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 Total Signals", total_signals)
            col2.metric("📈 Stocks with Signals", total_stocks)
            col3.metric("📁 Files with Signals", len(all_alerts))
            
            st.markdown("---")
            
            for file_name in sorted(all_alerts.keys()):
                file_data = all_alerts[file_name]
                signal_count = sum(len(a) for a in file_data.values())
                
                with st.expander(f"📁 {file_name} — {signal_count} signals", expanded=True):
                    rows = []
                    for ticker, alerts_list in sorted(file_data.items()):
                        for alert in alerts_list:
                            rows.append({"Stock": ticker, "Signal": alert})
                    
                    if rows:
                        df_display = pd.DataFrame(rows)
                        st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Export
            st.markdown("---")
            st.markdown("### 💾 Export")
            
            col1, col2, col3 = st.columns(3)
            
            export_rows = []
            for fn, fd in all_alerts.items():
                for t, al in fd.items():
                    for a in al:
                        export_rows.append({"File": fn, "Stock": t, "Signal": a})
            
            df_export = pd.DataFrame(export_rows)
            
            with col1:
                csv_data = df_export.to_csv(index=False)
                st.download_button("📥 CSV", csv_data, "signals.csv", "text/csv")
            
            with col2:
                import json
                json_data = json.dumps(all_alerts, indent=2)
                st.download_button("📥 JSON", json_data, "signals.json", "application/json")
            
            with col3:
                txt = "\n".join([f"{r['File']} | {r['Stock']} | {r['Signal']}" for r in export_rows])
                st.download_button("📥 TXT", txt, "signals.txt", "text/plain")

# Footer
st.markdown("---")
with st.expander("ℹ️ Help"):
    st.markdown("""
    **Liquidity Grab:** Price wicks below swing low, then closes above it (bullish reversal signal)
    
    **Usage:** Select INDEX/SECTOR → Choose files → Click Start Scan → View results
    """)

st.markdown("""<div style="text-align: center; color: #6e7681; padding: 20px; font-size: 0.85em;">
    Liquidity Scanner v2.0 • Live Data Mode
</div>""", unsafe_allow_html=True)
