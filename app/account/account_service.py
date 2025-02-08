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

# ✅ Set Take Profit (TP) and Stop Loss (SL) Levels
TP_PERCENT = 5  # Take profit at +5%
SL_PERCENT = 3  # Stop loss at -3%

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
                positions[symbol] = {
                    "positionAmt": float(pos["positionAmt"]),
                    "entryPrice": float(pos["entryPrice"]),
                    "unrealizedProfit": float(pos.get("unRealizedProfit", 0))  # ✅ FIXED
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

            # ✅ Fix: Fetch Latest Price if `mp` is Missing or 0.0
            marketPrice = float(position.get("mp", 0))
            if marketPrice == 0.0:  # If `mp` is 0.0, fetch latest price
                ticker = client.futures_mark_price(symbol=symbol)
                marketPrice = float(ticker["markPrice"])
                logger.info(f"🔄 Updated Market Price for {symbol}: {marketPrice}")

            # 🔍 Debugging: Check if entryPrice and positionAmt exist
            logger.debug(f"🔍 {symbol} - PositionAmt: {positionAmt}, EntryPrice: {entryPrice}")

            if symbol in positions and entryPrice is not None and positionAmt != 0:
                if positionAmt > 0:  # ✅ Long Position (BUY)
                    tp_price = entryPrice * (1 + TP_PERCENT / 100)
                    sl_price = entryPrice * (1 - SL_PERCENT / 100)
                else:  # ✅ Short Position (SELL)
                    tp_price = entryPrice * (1 - TP_PERCENT / 100)
                    sl_price = entryPrice * (1 + SL_PERCENT / 100)

                logger.info(f"📊 {symbol}: Market Price = {marketPrice}, TP = {tp_price}, SL = {sl_price}")

                # ✅ Fix: Only Close When a Real TP/SL Condition is Met
                if (positionAmt > 0 and marketPrice >= tp_price) or (positionAmt < 0 and marketPrice <= tp_price):
                    logger.info(f"🎯 TAKE PROFIT HIT for {symbol} at {marketPrice}")
                    close_position(symbol, positionAmt)

                elif (positionAmt > 0 and marketPrice <= sl_price) or (positionAmt < 0 and marketPrice >= sl_price):
                    logger.info(f"⛔ STOP LOSS HIT for {symbol} at {marketPrice}")
                    close_position(symbol, positionAmt)
            else:
                logger.warning(f"⚠️ {symbol} is missing entryPrice or positionAmt is zero, skipping TP/SL check.")



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
