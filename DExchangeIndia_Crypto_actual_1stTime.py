import ccxt
import pandas as pd
import pandas_ta as ta
import time

def fetch_all_delta_india_tickers(exchange):
    """Fetches all active perpetual contracts hosted on the Delta India cluster."""
    # Force CCXT to request the market products array
    raw_markets = exchange.fetch_markets()
    
    tradeable_pairs = []
    for m in raw_markets:
        # Match derivatives (swaps/futures) that are active
        is_derivative = (
            m.get('swap', False) or 
            m.get('future', False) or 
            m.get('linear', False) or
            (m.get('type') in ['swap', 'future', 'linear'])
        )
        is_active = m.get('active', True)
        
        if is_derivative and is_active:
            symbol = m.get('symbol')
            raw_id = m.get('id', '')
            
            # Clean formatting characters to ensure it prints clean app tickers
            clean_name = raw_id.replace('_', '').replace('-', '').replace('/', '').replace(':', '')
            
            if (symbol, clean_name) not in tradeable_pairs:
                tradeable_pairs.append((symbol, clean_name))
                
    return tradeable_pairs

def scan_momentum(symbol, exchange, timeframe):
    """Fetches historical candles, calculates EMAs, and checks breakdown/breakout momentum."""
    try:
        # Fetch 300 candles to give the 200 EMA baseline an accurate calculation runway
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=300)
        if len(ohlcv) < 200:
            return None
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Calculate Technical Indicators
        df['ema9'] = ta.ema(df['close'], length=9)
        df['ema20'] = ta.ema(df['close'], length=20)
        df['ema200'] = ta.ema(df['close'], length=200)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        prev_9 = df['ema9'].iloc[-2]
        prev_20 = df['ema20'].iloc[-2]
        curr_9 = df['ema9'].iloc[-1]
        curr_20 = df['ema20'].iloc[-1]
        curr_close = df['close'].iloc[-1]
        curr_200 = df['ema200'].iloc[-1]
        
        candle_body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
        avg_atr = df['atr'].iloc[-1]
        
        results = {}
        
        # 1. Bearish Breakdown Logic (9 EMA crosses under 20 EMA below 200 EMA)
        is_crossunder = (prev_9 >= prev_20) and (curr_9 < curr_20)
        if is_crossunder and (curr_close < curr_200):
            if candle_body > (avg_atr * 0.5): 
                results['type'] = 'BEARISH BREAKDOWN 📉'
                results['close'] = curr_close
                return results

        # 2. Bullish Breakout Logic (9 EMA crosses over 20 EMA above 200 EMA)
        is_crossover = (prev_9 <= prev_20) and (curr_9 > curr_20)
        if is_crossover and (curr_close > curr_200):
            if candle_body > (avg_atr * 0.5):
                results['type'] = 'BULLISH BREAKOUT 🚀'
                results['close'] = curr_close
                return results
                
    except Exception as e:
        return None
    return None

def main():
    # Fix: Point to the raw domain root. CCXT handles adding '/v2' internally.
    exchange = ccxt.delta({
        'enableRateLimit': True,
        'urls': {
            'api': {
                'public': 'https://api.india.delta.exchange',
                'private': 'https://api.india.delta.exchange',
            }
        }
    })
    
    target_tf = '5m' 
    
    print(f"Connecting to Delta India servers... Scanning active markets on {target_tf}...")
    pairs = fetch_all_delta_india_tickers(exchange)
    
    print(f"Total Active Futures Pairs Found on Delta India: {len(pairs)}")
    print(f"Initiating EMA calculation matrix...")
    print("-" * 50)
    
    detected_count = 0
    
    for ccxt_symbol, app_ticker in pairs:
        time.sleep(0.05)  # Slight rate-limiting safety pause
        setup = scan_momentum(ccxt_symbol, exchange, timeframe=target_tf)
        
        if setup:
            print(f"🚨 DELTA ALERT | {app_ticker} | {setup['type']} at price {setup['close']}")
            detected_count += 1

    print("-" * 50)
    print(f"Scan complete. Total active setups found: {detected_count}")

if __name__ == "__main__":
    main()