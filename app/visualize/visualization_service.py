from flask import Flask, jsonify
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

app = Flask(__name__)

STRATEGY_SERVICE_URL = "http://strategy_service:5002/strategy"  # Docker service name

def plot_candlestick(df):
    """Generate a candlestick chart with buy/sell signals."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.1)

    fig.add_trace(go.Candlestick(
        x=df["timestamp"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Candlesticks"
    ), row=1, col=1)

    # Add Buy Signals
    buy_signals = df[df["Buy_Signal"] == True]
    fig.add_trace(go.Scatter(
        x=buy_signals["timestamp"],
        y=buy_signals["low"],
        mode="markers",
        marker=dict(symbol="triangle-up", size=12, color="green"),
        name="Buy Signal"
    ), row=1, col=1)

    # Add Sell Signals
    sell_signals = df[df["Sell_Signal"] == True]
    fig.add_trace(go.Scatter(
        x=sell_signals["timestamp"],
        y=sell_signals["high"],
        mode="markers",
        marker=dict(symbol="triangle-down", size=12, color="red"),
        name="Sell Signal"
    ), row=1, col=1)

    # Add Volume
    fig.add_trace(go.Bar(x=df["timestamp"], y=df["volume"], name="Volume"), row=2, col=1)

    fig.update_layout(title="Candlestick Chart with Buy/Sell Signals", template="plotly_dark", height=800)
    return fig.to_json()

@app.route('/visualize', methods=['GET'])
def visualize():
    """Fetch data from the strategy service and return the visualization."""
    try:
        response = requests.get(STRATEGY_SERVICE_URL)
        response.raise_for_status()
        data = response.json()

        if not data:
            return jsonify({"error": "No data received from strategy service"}), 500

        df = pd.DataFrame(data)
        chart = plot_candlestick(df)
        return jsonify(chart)

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch data from strategy service: {e}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)
