import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import xml.etree.ElementTree as ET
import requests

# Set page configuration
st.set_page_config(page_title="Portfolio & Market Intelligence", layout="wide")

# --- DISCLAIMER ---
st.title("📈 Market Tracker & Portfolio Intelligence")
st.caption(
    "⚠️ **Disclaimer:** All signals, analysis, and recommendations are based on technical "
    "indicators for educational purposes only. They do not constitute financial advice. "
    "Consult a SEBI-registered advisor before making investment decisions."
)

# --- TECHNICAL ANALYSIS FUNCTIONS ---
def calculate_indicators(df):
    """Calculate 20-SMA, 50-SMA, and 14-day RSI safely."""
    df = df.copy()
    
    # Ensure Close is a 1D Series
    if isinstance(df['Close'], pd.DataFrame):
        close_series = df['Close'].iloc[:, 0]
    else:
        close_series = df['Close']
        
    df['SMA_20'] = close_series.rolling(window=20).mean()
    df['SMA_50'] = close_series.rolling(window=50).mean()

    # Relative Strength Index (RSI)
    delta = close_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    # Prevent division by zero
    loss = loss.replace(0, 0.00001)
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def generate_signal(df):
    """Generate Buy/Sell/Hold recommendation safely."""
    if len(df) < 50:
        return "INSUFFICIENT DATA", "Need at least 50 days of trading data."

    latest = df.iloc[-1]
    rsi = float(latest['RSI']) if pd.notna(latest['RSI']) else 50.0
    sma20 = float(latest['SMA_20']) if pd.notna(latest['SMA_20']) else 0.0
    sma50 = float(latest['SMA_50']) if pd.notna(latest['SMA_50']) else 0.0

    # Signal logic
    if rsi < 35 and sma20 > sma50:
        return "STRONG BUY", f"Oversold (RSI: {rsi:.1f}) in an uptrend."
    elif rsi < 40:
        return "BUY (ACCUMULATE)", f"Pullback opportunity (RSI: {rsi:.1f})."
    elif rsi > 75 and sma20 < sma50:
        return "STRONG SELL", f"Overbought (RSI: {rsi:.1f}) in a downtrend."
    elif rsi > 70:
        return "TAKE PROFIT / SELL", f"Overbought territory (RSI: {rsi:.1f})."
    elif sma20 > sma50:
        return "HOLD / BULLISH", f"Positive trend (SMA20 > SMA50)."
    else:
        return "HOLD / NEUTRAL", f"Consolidating (RSI: {rsi:.1f})."

# --- SAFE NEWS FETCHING FUNCTION ---
def fetch_rss_news(query, limit=5):
    """Fetch latest news safely without breaking if the feed is blocked."""
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code != 200:
            return [{"title": "News temporarily unavailable", "link": "#", "date": ""}]
        
        root = ET.fromstring(response.content)
        articles = []
        for item in root.findall(".//item")[:limit]:
            title = item.find("title").text if item.find("title") is not None else "No Title"
            link = item.find("link").text if item.find("link") is not None else "#"
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            articles.append({"title": title, "link": link, "date": pub_date})
        return articles
    except Exception:
        return [{"title": "Could not fetch current updates. Please refresh later.", "link": "#", "date": ""}]

# --- SESSION STATE PORTFOLIO SETUP ---
if "portfolio" not in st.session_state:
    st.session_state.portfolio = [
        {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "qty": 10, "avg_cost": 2850.0},
        {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "qty": 5, "avg_cost": 3900.0},
        {"symbol": "NIFTYBEES.NS", "name": "Nippon Nifty 50 ETF", "qty": 50, "avg_cost": 260.0},
        {"symbol": "GC=F", "name": "Gold Commodity (USD)", "qty": 2, "avg_cost": 2500.0},
    ]

# --- SIDEBAR: PORTFOLIO MANAGEMENT ---
st.sidebar.header("📁 Add to Portfolio")
with st.sidebar.form("add_stock_form"):
    sym_input = st.text_input("Ticker Symbol (e.g. INFY.NS, GOLDBEES.NS, GC=F)", "HDFCBANK.NS")
    name_input = st.text_input("Asset Name", "HDFC Bank")
    qty_input = st.number_input("Quantity", min_value=1.0, value=10.0, step=1.0)
    cost_input = st.number_input("Average Buy Price", min_value=0.1, value=1600.0, step=1.0)
    submitted = st.form_submit_button("Add Asset")
    if submitted:
        st.session_state.portfolio.append(
            {"symbol": sym_input.upper().strip(), "name": name_input, "qty": qty_input, "avg_cost": cost_input}
        )
        st.sidebar.success(f"Added {name_input}!")

# --- APP TABS ---
tab1, tab2, tab3 = st.tabs(["📊 Portfolio & Signals", "🛢️ Commodities Watch", "📰 Banking & Fed News"])

# ==========================================
# TAB 1: PORTFOLIO TRACKER & SIGNALS
# ==========================================
with tab1:
    st.subheader("Your Holdings & Technical Recommendations")

    portfolio_data = []
    total_invested = 0.0
    total_current = 0.0

    for item in st.session_state.portfolio:
        sym = item["symbol"]
        qty = item["qty"]
        avg = item["avg_cost"]

        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="6mo")
            if not hist.empty and len(hist) > 0:
                current_price = float(hist["Close"].dropna().iloc[-1])
                hist = calculate_indicators(hist)
                signal, reason = generate_signal(hist)
            else:
                current_price = avg
                signal, reason = "N/A", "Ticker not returning data"
        except Exception:
            current_price = avg
            signal, reason = "ERROR", "Failed to fetch price"

        invested_val = qty * avg
        current_val = qty * current_price
        pnl = current_val - invested_val
        pnl_pct = (pnl / invested_val) * 100 if invested_val > 0 else 0

        total_invested += invested_val
        total_current += current_val

        portfolio_data.append({
            "Symbol": sym,
            "Name": item["name"],
            "Qty": qty,
            "Avg Cost": round(avg, 2),
            "Current Price": round(current_price, 2),
            "Invested Value": round(invested_val, 2),
            "Current Value": round(current_val, 2),
            "P&L": round(pnl, 2),
            "Return (%)": f"{pnl_pct:.2f}%",
            "Signal": signal,
            "Reason": reason
        })

    # Summary Metrics
    total_pnl = total_current - total_invested
    total_roi = (total_pnl / total_invested) * 100 if total_invested > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Invested", f"₹ {total_invested:,.2f}")
    col2.metric("Portfolio Value", f"₹ {total_current:,.2f}")
    col3.metric("Total P&L", f"₹ {total_pnl:,.2f}", f"{total_roi:.2f}%")
    col4.metric("Assets Tracked", len(portfolio_data))

    df_display = pd.DataFrame(portfolio_data)
    
    # Safe signal styling compatible with all Pandas versions
    def highlight_signals(val):
        if "BUY" in str(val):
            return "color: #28a745; font-weight: bold;"
        elif "SELL" in str(val):
            return "color: #dc3545; font-weight: bold;"
        return "color: #ffc107;"

    try:
        # For Pandas 2.1+
        styled_df = df_display.style.map(highlight_signals, subset=["Signal"])
    except AttributeError:
        # Fallback for older Pandas
        styled_df = df_display.style.applymap(highlight_signals, subset=["Signal"])

    st.dataframe(styled_df, use_container_width=True)

    # Interactive Chart
    st.markdown("---")
    st.subheader("Deep Dive Chart")
    selected_sym = st.selectbox("Select symbol to chart:", [i["symbol"] for i in st.session_state.portfolio])

    try:
        stock_hist = yf.Ticker(selected_sym).history(period="1y")
        if not stock_hist.empty and len(stock_hist) > 10:
            stock_hist = calculate_indicators(stock_hist)

            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=stock_hist.index,
                open=stock_hist['Open'],
                high=stock_hist['High'],
                low=stock_hist['Low'],
                close=stock_hist['Close'],
                name="Price"
            ))
            fig.add_trace(go.Scatter(x=stock_hist.index, y=stock_hist['SMA_20'], line=dict(color='orange', width=1.5), name="SMA 20"))
            fig.add_trace(go.Scatter(x=stock_hist.index, y=stock_hist['SMA_50'], line=dict(color='blue', width=1.5), name="SMA 50"))
            fig.update_layout(title=f"{selected_sym} Technical Chart", xaxis_rangeslider_visible=False, height=500)
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not load chart for {selected_sym}: {e}")

# ==========================================
# TAB 2: COMMODITIES WATCH
# ==========================================
with tab2:
    st.subheader("Key Commodities Tracker")
    commodities = {
        "Gold": "GC=F",
        "Silver": "SI=F",
        "Crude Oil": "CL=F",
        "Brent Crude": "BZ=F",
        "Natural Gas": "NG=F"
    }

    c_cols = st.columns(len(commodities))
    for col, (name, ticker_id) in zip(c_cols, commodities.items()):
        try:
            t = yf.Ticker(ticker_id)
            c_hist = t.history(period="7d").dropna() # 7 days prevents weekend crash
            if len(c_hist) >= 2:
                latest_p = float(c_hist['Close'].iloc[-1])
                prev_p = float(c_hist['Close'].iloc[-2])
                delta_p = latest_p - prev_p
                delta_pct = (delta_p / prev_p) * 100
                col.metric(name, f"${latest_p:,.2f}", f"{delta_pct:+.2f}%")
            elif len(c_hist) == 1:
                latest_p = float(c_hist['Close'].iloc[-1])
                col.metric(name, f"${latest_p:,.2f}")
            else:
                col.metric(name, "N/A")
        except Exception:
            col.metric(name, "N/A")

# ==========================================
# TAB 3: FED, BANK OF AMERICA & JP MORGAN NEWS
# ==========================================
with tab3:
    st.subheader("🏦 Latest Banking & Central Bank News")

    n_col1, n_col2, n_col3 = st.columns(3)

    with n_col1:
        st.markdown("### 🏛️ Federal Reserve / Fed")
        for article in fetch_rss_news("Federal Reserve interest rates economy", limit=5):
            st.markdown(f"**[{article['title']}]({article['link']})**")
            st.caption(article['date'])
            st.divider()

    with n_col2:
        st.markdown("### 🏦 Bank of America (NYSE: BAC)")
        for article in fetch_rss_news("Bank of America earnings BAC stock", limit=5):
            st.markdown(f"**[{article['title']}]({article['link']})**")
            st.caption(article['date'])
            st.divider()

    with n_col3:
        st.markdown("### 🏢 JPMorgan Chase (NYSE: JPM)")
        for article in fetch_rss_news("JPMorgan Chase JPM stock", limit=5):
            st.markdown(f"**[{article['title']}]({article['link']})**")
            st.caption(article['date'])
            st.divider()