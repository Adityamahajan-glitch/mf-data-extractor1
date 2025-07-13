import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator

# --- Dark Mode Toggle ---
dark_mode = st.toggle("🌙 Dark Mode")

st.markdown(
    f"""
    <style>
    body {{
        background-color: {'#0e1117' if dark_mode else 'white'};
        color: {'white' if dark_mode else 'black'};
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# --- Simple Login ---
def login():
    st.sidebar.title("🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if username == "aditya" and password == "1234":
        return True
    else:
        st.sidebar.warning("👀 Enter valid credentials.")
        return False

if not login():
    st.stop()

# --- Date helpers ---
def convert_date_to_utc_datetime(date_string):
    from pytz import utc
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

@st.cache_data(ttl="1h")
def fetch_amfi_data(start_date_str, end_date_str):
    nav_list = []
    for start, end in split_date_range(start_date_str, end_date_str):
        url = f"https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?&frmdt={start.strftime('%d-%b-%Y')}&todt={end.strftime('%d-%b-%Y')}"
        try:
            response = requests.get(url, timeout=10)
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
        except Exception as e:
            st.error(f"Error fetching data: {e}")
    return pd.DataFrame(nav_list)

# --- UI ---
st.title("📊 MF Data Extractor (AMFI)")

start = st.date_input("Fetch From", datetime(2025, 4, 1))
end = st.date_input("Fetch To", datetime(2025, 6, 30))

if st.button("📥 Fetch Data"):
    with st.spinner("Fetching data..."):
        df_nav = fetch_amfi_data(start.strftime('%d-%b-%Y'), end.strftime('%d-%b-%Y'))
    if df_nav.empty:
        st.error("❌ No data fetched")
    else:
        df_nav['Date'] = pd.to_datetime(df_nav['Date']).dt.tz_localize(None)
        st.success(f"✅ {len(df_nav)} records fetched.")

        amc = st.selectbox("Select AMC", sorted(df_nav['AMC'].dropna().unique()))
        scheme = st.selectbox("Select Scheme", sorted(df_nav[df_nav['AMC'] == amc]['Name'].unique()))
        selected_df = df_nav[df_nav['Name'] == scheme]

        start_plot = st.date_input("Plot From", selected_df['Date'].min().date())
        end_plot = st.date_input("Plot To", selected_df['Date'].max().date())

        sma_1 = st.number_input("SMA 1", min_value=1, value=50)
        sma_2 = st.number_input("SMA 2", min_value=1, value=100)
        sma_3 = st.number_input("SMA 3", min_value=1, value=200)

        if st.button("📊 Plot Chart"):
            df = selected_df[(selected_df['Date'] >= pd.to_datetime(start_plot)) & (selected_df['Date'] <= pd.to_datetime(end_plot))]
            df['RSI_14'] = RSIIndicator(close=df['NAV'], window=14).rsi()
            macd = MACD(close=df['NAV'], window_slow=26, window_fast=12, window_sign=9)
            df['MACD'] = macd.macd()
            df['MACD_Signal'] = macd.macd_signal()
            df[f"SMA_{sma_1}"] = SMAIndicator(close=df['NAV'], window=sma_1).sma_indicator()
            df[f"SMA_{sma_2}"] = SMAIndicator(close=df['NAV'], window=sma_2).sma_indicator()
            df[f"SMA_{sma_3}"] = SMAIndicator(close=df['NAV'], window=sma_3).sma_indicator()

            st.line_chart(df.set_index('Date')[['NAV', f"SMA_{sma_1}", f"SMA_{sma_2}", f"SMA_{sma_3}"]])
            st.line_chart(df.set_index('Date')[['RSI_14']])
            st.line_chart(df.set_index('Date')[['MACD', 'MACD_Signal']])
