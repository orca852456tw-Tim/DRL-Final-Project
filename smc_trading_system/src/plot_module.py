import plotly.graph_objects as go
import pandas as pd

def plot_trade_chart(df: pd.DataFrame, trade_log: list, zones: list):
    """
    Plot candlesticks, demand zones, and trade entries/exits.
    zones is a list of [zone_top, zone_bottom].
    """
    fig = go.Figure()

    # 1. Candlestick trace
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price'
    ))

    # 2. Demand Zones (Rectangles)
    shapes = []
    for zone in zones:
        zone_top, zone_bottom = zone
        shapes.append(dict(
            type="rect",
            x0=df.index[0],
            y0=zone_bottom,
            x1=df.index[-1],
            y1=zone_top,
            fillcolor="green",
            opacity=0.2,
            layer="below",
            line_width=0,
        ))
    fig.update_layout(shapes=shapes)

    # 3. Trade Signals
    buy_dates = []
    buy_prices = []
    buy_texts = []
    
    sell_dates = []
    sell_prices = []
    sell_texts = []

    for trade in trade_log:
        buy_dates.append(trade['entry_date'])
        # Place arrow slightly below the low
        low_price = df.loc[trade['entry_date'], 'Low'] if trade['entry_date'] in df.index else trade['entry_price']
        buy_prices.append(low_price * 0.98) # Adjust visually
        buy_texts.append(f"BUY<br>{round(trade['entry_price'], 2)}")

        sell_dates.append(trade['exit_date'])
        high_price = df.loc[trade['exit_date'], 'High'] if trade['exit_date'] in df.index else trade['exit_price']
        sell_prices.append(high_price * 1.02)
        reason = "TP" if trade['result'] == 'WIN' else "SL"
        sell_texts.append(f"{reason}<br>{round(trade['exit_price'], 2)}")

    fig.add_trace(go.Scatter(
        x=buy_dates,
        y=buy_prices,
        mode='markers+text',
        marker=dict(symbol='triangle-up', size=15, color='blue'),
        text=buy_texts,
        textposition='bottom center',
        name='BUY'
    ))

    fig.add_trace(go.Scatter(
        x=sell_dates,
        y=sell_prices,
        mode='markers+text',
        marker=dict(symbol='triangle-down', size=15, color='red'),
        text=sell_texts,
        textposition='top center',
        name='SELL'
    ))

    fig.update_layout(
        title="SMC Trading System Backtest Result",
        yaxis_title="Price",
        xaxis_title="Date",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=800
    )

    fig.write_html("backtest_result.html")
