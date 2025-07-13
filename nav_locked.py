import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from pytz import utc
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# === Dark Mode ===
dark_mode = st.toggle("🌙 Dark Mode", value=True)
if dark_mode:
    st.markdown("""
        <style>
            body {
                background-color: #0e1117;
                color: white;
            }
        </style>
    """, unsafe_allow_html=True)
# === Login ===
def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == "aditya" and password == "1234":
            st.success("✅ Logged in successfully")
            return True
        else:
            st.error("❌ Invalid credentials")
    if st.button("Forgot Password?"):
        st.info("🔐 Contact admin or reset via backend")
    return False
if not login():
    st.stop()
# === Helper Functions ===
def convert_date_to_utc_datetime(date_string):
    return datetime.strptime(date_string, "%d-%b-%Y").replace(tzinfo=utc)
def split_date_range(start_date_str, end_date_str, max_duration=90):
    start_date = datetime.strptime(start_date_str, "%d-%b-%Y")
    end_date = datetime.strptime(end_date_str, "%d-%b-%Y")
    ranges = []
    current = start_date
    while current <= end_date:
        chunk_end = min(current + timedelta(days=max_duration - 1), end_date)
        ranges.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return ranges
def fetch_amfi_data(start_date_str, end_date_str):
    nav_list = []
    ranges = split_date_range(start_date_str, end_date_str)
    progress = st.progress(0)
    for i, (start, end) in enumerate(ranges):
        url = f"https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?&frmdt={start.strftime('%d-%b-%Y')}&todt={end.strftime('%d-%b-%Y')}"
        response = requests.get(url)
        lines = response.text.split('\r\n')
        Structure = Category = Sub_Category = amc = ""
        j = 1
        for line in lines[1:]:
            split = line.split(";")
            if j == len(lines) - 1:
                break
            if split[0] == "":
                if lines[j] == lines[j + 1]:
                    sch_cat = lines[j - 1].split("(")
                    sch_cat[-1] = sch_cat[-1][:-2].strip()
                    sch_cat = [s.strip() for s in sch_cat]
                    if "-" in sch_cat[1]:
                        sub = sch_cat[1].split("-")
                        sch_cat.pop(-1)
                        sch_cat += [s.strip() for s in sub]
                    else:
                        sch_cat += ["", sch_cat.pop(-1)]
                    Structure, Category, Sub_Category = sch_cat[:3]
                elif "Mutual Fund" in lines[j + 1]:
                    amc = lines[j + 1]
            elif len(split) > 1:
                try:
                    code = int(split[0].strip())
                    name = split[1].strip()
                    dg = "Growth" if "growth" in name.lower() else "IDCW" if "idcw" in name.lower() or "dividend" in name.lower() else ""
                    inv_src = "Direct" if "direct" in name.lower() else "Regular" if "regular" in name.lower() else ""
                    nav = float(split[4].strip()) if split[4].strip() else None
                    date = convert_date_to_utc_datetime(split[7].strip())
                    nav_list.append({
                        "Structure": Structure,
                        "Category": Category,
                        "Sub_Category": Sub_Category,
                        "AMC": amc,
                        "Code": code,
                        "Name": name,
                        "Source": inv_src,
                        "Option": dg,
                        "Date": date,
                        "NAV": nav
                    })
                except:
                    pass
            j += 1
        progress.progress((i + 1) / len(ranges))
    return pd.DataFrame(nav_list)
# === UI ===
st.title("📊 MF Data Extractor Dashboard")
fetch_col1, fetch_col2 = st.columns(2)
fetch_from_date = fetch_col1.date_input("Fetch From", datetime(2025, 4, 1))
fetch_to_date = fetch_col2.date_input("Fetch To", datetime(2025, 6, 30))
if st.button("📥 Fetch Data"):
    if fetch_from_date and fetch_to_date:
        start_str = fetch_from_date.strftime('%d-%b-%Y')
        end_str = fetch_to_date.strftime('%d-%b-%Y')
        st.write(f"Fetching data from **{start_str}** to **{end_str}**")
        df_nav = fetch_amfi_data(start_str, end_str)
        st.session_state.df_nav = df_nav
    else:
        st.warning("⚠️ Please select both from and to dates.")
if 'df_nav' in st.session_state:
    df_nav = st.session_state.df_nav
    selected_amc = st.selectbox("AMC", sorted(df_nav['AMC'].dropna().unique()))
    selected_scheme = st.selectbox("Scheme", sorted(df_nav[df_nav['AMC'] == selected_amc]['Name'].unique()))
    filtered_df = df_nav[df_nav['Name'] == selected_scheme]
    if not filtered_df.empty:
        from_date = st.date_input("From Date", filtered_df['Date'].min().to_pydatetime())
        to_date = st.date_input("To Date", filtered_df['Date'].max().to_pydatetime())
        sma1 = st.number_input("SMA 1", value=50)
        sma2 = st.number_input("SMA 2", value=100)
        sma3 = st.number_input("SMA 3", value=200)
        if st.button("📊 Plot Chart"):
            df = filtered_df[(filtered_df['Date'] >= pd.to_datetime(from_date)) & (filtered_df['Date'] <= pd.to_datetime(to_date))]
            df['RSI_14'] = RSIIndicator(close=df['NAV'], window=14).rsi()
            macd = MACD(close=df['NAV'], window_slow=26, window_fast=12, window_sign=9)
            df['MACD'] = macd.macd()
            df['MACD_Signal'] = macd.macd_signal()
            sma_cols = []
            for period in [sma1, sma2, sma3]:
                if period > 1:
                    col = f"SMA_{period}"
                    df[col] = SMAIndicator(close=df['NAV'], window=period).sma_indicator()
                    sma_cols.append(col)
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                                subplot_titles=["NAV + SMAs", "RSI (14)", "MACD"])
            fig.add_trace(go.Scatter(x=df['Date'], y=df['NAV'], name="NAV", line=dict(color="cyan")), row=1, col=1)
            for col in sma_cols:
                fig.add_trace(go.Scatter(x=df['Date'], y=df[col], name=col, line=dict(dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI_14'], name="RSI", line=dict(color="violet")), row=2, col=1)
            fig.add_shape(type='line', x0=df['Date'].min(), x1=df['Date'].max(), y0=70, y1=70, line=dict(dash="dot", color="red"), row=2, col=1)
            fig.add_shape(type='line', x0=df['Date'].min(), x1=df['Date'].max(), y0=30, y1=30, line=dict(dash="dot", color="green"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name="MACD", line=dict(color="aqua")), row=3, col=1)
            fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD_Signal'], name="Signal", line=dict(dash='dot', color="white")), row=3, col=1)
            fig.update_layout(title=f"{selected_scheme} NAV Chart", template="plotly_dark" if dark_mode else "plotly_white", height=900)
            st.plotly_chart(fig, use_container_width=True)
