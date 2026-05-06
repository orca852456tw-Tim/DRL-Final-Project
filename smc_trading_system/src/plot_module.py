import plotly.graph_objects as go
import pandas as pd

def generate_dashboard_html(df: pd.DataFrame, trade_log: list, zones: list, risk_profile: str, cagr: float, mc_results: dict):
    """
    Generate a split-screen HTML dashboard with trade chart and performance metrics.
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

    trade_details_html = ""

    for idx, trade in enumerate(trade_log, 1):
        buy_dates.append(trade['entry_date'])
        low_price = df.loc[trade['entry_date'], 'Low'] if trade['entry_date'] in df.index else trade['entry_price']
        buy_prices.append(low_price * 0.98) 
        buy_texts.append(f"BUY<br>{round(trade['entry_price'], 2)}")

        sell_dates.append(trade['exit_date'])
        high_price = df.loc[trade['exit_date'], 'High'] if trade['exit_date'] in df.index else trade['exit_price']
        sell_prices.append(high_price * 1.02)
        reason = "TP" if trade['result'] == 'WIN' else "SL"
        sell_texts.append(f"{reason}<br>{round(trade['exit_price'], 2)}")

        # Build trade details for sidebar
        entry_date_str = trade['entry_date'].strftime('%Y-%m-%d')
        exit_date_str = trade['exit_date'].strftime('%Y-%m-%d') if pd.notna(trade['exit_date']) else "N/A"
        res_color = "#28a745" if trade['result'] == 'WIN' else "#dc3545" if trade['result'] == 'LOSS' else "#ffc107"
        
        trade_details_html += f"""
        <div class="trade-card" style="border-left: 4px solid {res_color};">
            <h4>Trade #{idx} <span style="color:{res_color}; float:right;">{trade['result']}</span></h4>
            <p><strong>Entry:</strong> {entry_date_str} @ {round(trade['entry_price'], 2)}</p>
            <p><strong>Exit:</strong> {exit_date_str} @ {round(trade['exit_price'], 2)}</p>
            <p><strong>Return:</strong> {round(trade['return_pct']*100, 2)}%</p>
        </div>
        """

    fig.add_trace(go.Scatter(
        x=buy_dates,
        y=buy_prices,
        mode='markers+text',
        marker=dict(symbol='triangle-up', size=15, color='#00ffcc'),
        text=buy_texts,
        textposition='bottom center',
        name='BUY'
    ))

    fig.add_trace(go.Scatter(
        x=sell_dates,
        y=sell_prices,
        mode='markers+text',
        marker=dict(symbol='triangle-down', size=15, color='#ff3366'),
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
        margin=dict(l=20, r=20, t=50, b=20),
        autosize=True
    )

    plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

    mc_best = round(mc_results['best_case_95th'], 2)
    mc_expected = round(mc_results['expected_50th'], 2)
    mc_worst = round(mc_results['worst_case_5th'], 2)
    cagr_pct = round(cagr * 100, 2)

    dashboard_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SMC System Dashboard</title>
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #121212;
                color: #e0e0e0;
                display: flex;
                height: 100vh;
                overflow: hidden;
            }}
            .sidebar {{
                width: 350px;
                background-color: #1e1e1e;
                padding: 20px;
                overflow-y: auto;
                box-shadow: 2px 0 5px rgba(0,0,0,0.5);
                display: flex;
                flex-direction: column;
                gap: 20px;
            }}
            .main-content {{
                flex: 1;
                display: flex;
                flex-direction: column;
            }}
            .card {{
                background-color: #2c2c2c;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }}
            .card h3 {{
                margin-top: 0;
                border-bottom: 1px solid #444;
                padding-bottom: 10px;
                color: #00ffcc;
            }}
            .trade-card {{
                background-color: #2a2a2a;
                margin-bottom: 10px;
                padding: 10px;
                border-radius: 5px;
                font-size: 0.9em;
            }}
            .trade-card h4 {{ margin: 0 0 5px 0; }}
            .trade-card p {{ margin: 3px 0; }}
            .mc-stat {{
                display: flex;
                justify-content: space-between;
                margin: 8px 0;
                padding: 5px;
                background-color: #333;
                border-radius: 4px;
            }}
            .mc-stat.best {{ border-left: 3px solid #28a745; }}
            .mc-stat.expected {{ border-left: 3px solid #17a2b8; }}
            .mc-stat.worst {{ border-left: 3px solid #dc3545; }}
            
            #plot-container {{
                flex: 1;
                width: 100%;
                height: 100%;
            }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div class="card">
                <h3>Risk Profile</h3>
                <h2 style="margin:0; color:#fff;">{risk_profile}</h2>
            </div>
            
            <div class="card">
                <h3>📈 3-Year Future Forecast (Monte Carlo)</h3>
                <p><strong>Historical CAGR:</strong> <span style="color:#00ffcc; font-size:1.2em;">{cagr_pct}%</span></p>
                <div class="mc-stat best">
                    <span>Best Case (95th):</span>
                    <strong>{mc_best}x</strong>
                </div>
                <div class="mc-stat expected">
                    <span>Expected (50th):</span>
                    <strong>{mc_expected}x</strong>
                </div>
                <div class="mc-stat worst">
                    <span>Worst Case (5th):</span>
                    <strong>{mc_worst}x</strong>
                </div>
            </div>

            <div class="card" style="flex: 1; overflow-y: auto;">
                <h3>Trade Details</h3>
                {trade_details_html}
            </div>
        </div>
        <div class="main-content">
            <div id="plot-container">
                {plot_html}
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("demo_dashboard.html", "w", encoding="utf-8") as f:
        f.write(dashboard_html)
