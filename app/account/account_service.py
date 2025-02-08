import asyncio
import logging
import threading
import time
import os
from binance import ThreadedWebsocketManager
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from binance.client import Client

# ✅ Use Binance Testnet API for Mock Trading
API_KEY = "a44d949f9e99e9cbb49bfb15d368524454dbe3032d4001fb6c75eb932f5dd001"
API_SECRET = "9be962776fa8625b48fc0188f5643fef0747d6e785908ca059826a424b88eeec"

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Initialize Binance Client with Testnet
client = Client(API_KEY, API_SECRET, testnet=True)

# ✅ WebSocket-Based Position Tracking
twm = None  # WebSocket instance

# ✅ Risk-Reward Ratio (RR)
RISK_REWARD_RATIO = 2  # Example: 2:1 RR

# ✅ Store Open Positions
positions = {}

def get_open_positions():
    """Fetch currently open positions from Binance Testnet Futures."""
    global positions
    positions.clear()
    try:
        account_info = client.futures_account()
        for pos in account_info["positions"]:
            if float(pos["positionAmt"]) != 0:  # Only track open positions
                symbol = pos["symbol"]
                entry_price = float(pos["entryPrice"])
                positionAmt = float(pos["positionAmt"])

                # ✅ Calculate TP & SL using Risk-Reward Ratio
                if positionAmt > 0:  # Long (BUY)
                    tp_price = entry_price + (entry_price * RISK_REWARD_RATIO / 100)
                    sl_price = entry_price - (entry_price * (RISK_REWARD_RATIO / 2) / 100)
                else:  # Short (SELL)
                    tp_price = entry_price - (entry_price * RISK_REWARD_RATIO / 100)
                    sl_price = entry_price + (entry_price * (RISK_REWARD_RATIO / 2) / 100)

                positions[symbol] = {
                    "positionAmt": positionAmt,
                    "entryPrice": entry_price,
                    "tpPrice": tp_price,
                    "slPrice": sl_price
                }
        logger.info(f"📊 Tracked Positions: {positions}")
    except Exception as e:
        logger.error(f"❌ Error fetching positions: {e}")

def close_position(symbol, side):
    """Close a position when TP or SL is hit."""
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL if side == SIDE_BUY else SIDE_BUY,  # Close in opposite direction
            type=ORDER_TYPE_MARKET,
            quantity=abs(float(positions[symbol]["positionAmt"]))  # Close full position
        )
        logger.info(f"✅ Closed position for {symbol}: {order}")
    except Exception as e:
        logger.error(f"❌ Error closing position for {symbol}: {e}")

def handle_message(msg):
    """Handle real-time WebSocket messages."""
    if msg["e"] == "ACCOUNT_UPDATE":
        positions_update = msg["a"]["P"]
        for position in positions_update:
            symbol = position["s"]
            positionAmt = float(position["pa"])  # Position amount
            entryPrice = float(position["ep"]) if "ep" in position else None

            # ✅ Fetch Latest Market Price
            marketPrice = float(position.get("mp", 0))
            if marketPrice == 0.0:
                ticker = client.futures_mark_price(symbol=symbol)
                marketPrice = float(ticker["markPrice"])
                logger.info(f"🔄 Updated Market Price for {symbol}: {marketPrice}")

            if symbol in positions and entryPrice is not None and positionAmt != 0:
                tp_price = positions[symbol]["tpPrice"]
                sl_price = positions[symbol]["slPrice"]

                logger.info(f"📊 {symbol}: Market Price = {marketPrice}, TP = {tp_price}, SL = {sl_price}")

                # ✅ Check TP & SL Conditions
                if (positionAmt > 0 and marketPrice >= tp_price) or (positionAmt < 0 and marketPrice <= tp_price):
                    logger.info(f"🎯 TAKE PROFIT HIT for {symbol} at {marketPrice}")
                    close_position(symbol, positionAmt)

                elif (positionAmt > 0 and marketPrice <= sl_price) or (positionAmt < 0 and marketPrice >= sl_price):
                    logger.info(f"⛔ STOP LOSS HIT for {symbol} at {marketPrice}")
                    close_position(symbol, positionAmt)

def start_websocket():
    """Start Binance WebSocket for real-time account updates."""
    global twm
    twm = ThreadedWebsocketManager(API_KEY, API_SECRET, testnet=True)
    twm.start()

    logger.info("🚀 WebSocket started. Listening for account updates...")
    
    twm.start_futures_user_socket(callback=handle_message)  # ✅ Ensure it's tracking futures

# ✅ FIX: Run WebSocket in a separate thread
if __name__ == "__main__":
    get_open_positions()  # Fetch open positions at startup
    
    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()

    # Keep main thread alive
    while True:
        try:
            time.sleep(1)  # ✅ FIX: Use standard sleep to avoid asyncio error
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down WebSocket...")
            twm.stop()
            break
