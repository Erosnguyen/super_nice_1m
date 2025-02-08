import logging
from binance.client import Client

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Binance API Keys (Ensure to set them in your environment variables)
API_KEY = "a44d949f9e99e9cbb49bfb15d368524454dbe3032d4001fb6c75eb932f5dd001"
API_SECRET = "9be962776fa8625b48fc0188f5643fef0747d6e785908ca059826a424b88eeec"

# ✅ Initialize Binance Client
client = Client(API_KEY, API_SECRET, testnet=True)

def get_futures_fee(symbol="BTCUSDT"):
    """
    Fetches Binance Futures trading fee for the given symbol.
    Returns the maker & taker fee as percentages.
    """
    try:
        fee_info = client.futures_commission_rate(symbol=symbol)
        maker_fee = float(fee_info["makerCommissionRate"])
        taker_fee = float(fee_info["takerCommissionRate"])
        logger.info(f"📊 Binance Futures Fees - Maker: {maker_fee}, Taker: {taker_fee}")
        return maker_fee, taker_fee
    except Exception as e:
        logger.error(f"❌ Error fetching futures fee: {e}")
        return 0.0002, 0.0004  # Default Binance Futures fees (0.02% Maker, 0.04% Taker)

# ✅ Test Fetching Fees
if __name__ == "__main__":
    symbol = "BTCUSDT"
    maker, taker = get_futures_fee(symbol)
    print(f"✅ {symbol} Fees - Maker: {maker}, Taker: {taker}")
