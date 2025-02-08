from flask import Flask, request, jsonify
import ccxt
import os

# ✅ Load Binance API Keys
API_KEY = "a44d949f9e99e9cbb49bfb15d368524454dbe3032d4001fb6c75eb932f5dd001"
API_SECRET = "9be962776fa8625b48fc0188f5643fef0747d6e785908ca059826a424b88eeec"

# ✅ Initialize Binance Futures Client (CCXT) in TESTNET MODE
exchange = ccxt.binance({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "options": {
        "defaultType": "future",  # Enable Futures Trading
    },
    "enableRateLimit": True,
})

# ✅ Activate Testnet Mode
exchange.set_sandbox_mode(True)  # ← This enables TESTNET trading

app = Flask(__name__)

@app.route('/order', methods=['POST'])
def place_order():
    """Place an order on Binance Futures Testnet."""
    data = request.json
    symbol = data.get("symbol", "BTC/USDT")
    side = data.get("side", "buy").lower()
    quantity = float(data.get("quantity", 0.01))
    order_type = data.get("type", "market").lower()

    try:
        # ✅ Place Order on Binance TESTNET
        order = exchange.create_order(
            symbol=symbol,
            type=order_type.upper(),
            side=side.upper(),
            amount=quantity
        )

        return jsonify({"status": "success", "order": order})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)
