import ccxt
import pandas as pd
import time

def fetch_all_delta_india_tickers(exchange):
    """Fetches all active perpetual contracts hosted on the Delta India cluster."""
    raw_markets = exchange.fetch_markets()
    
    tradeable_pairs = []
    for m in raw_markets:
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
            
            clean_name = raw_id.replace('_', '').replace('-', '').replace('/', '').replace(':', '')
            
            if (symbol, clean_name) not in tradeable_pairs:
                tradeable_pairs.append((symbol, clean_name))
                
    return tradeable_pairs

def scan_momentum(symbol, exchange, timeframe):
    """Fetches historical candles, calculates EMAs, and checks for momentum with Volume + IST Time."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=300)
        if len(ohlcv) < 200:
            return None
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Native Pandas Calculations (No pandas_ta required)
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
        
        # Native ATR Calculation
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.ewm(span=14, adjust=False).mean()
        
        # Extract previous and current positions
        prev_9 = df['ema9'].iloc[-2]
        prev_20 = df['ema20'].iloc[-2]
        curr_9 = df['ema9'].iloc[-1]
        curr_20 = df['ema20'].iloc[-1]
        curr_close = df['close'].iloc[-1]
        curr_200 = df['ema200'].iloc[-1]
        
        candle_body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
        avg_atr = df['atr'].iloc[-1]
        
        # Capture the raw volume and timestamp of the alert candle
        alert_volume = df['volume'].iloc[-1]
        raw_ts = df['timestamp'].iloc[-1]
        
        # Convert the exchange millisecond timestamp to pandas datetime, then localize to UTC, and convert to IST
        ist_time = pd.to_datetime(raw_ts, unit='ms', utc=True).tz_convert('Asia/Kolkata')
        formatted_ist = ist_time.strftime('%Y-%m-%d %H:%M:%S IST')
        
        results = {}
        
        # 1. Bearish Breakdown Logic
        is_crossunder = (prev_9 >= prev_20) and (curr_9 < curr_20)
        if is_crossunder and (curr_close < curr_200):
            if candle_body > (avg_atr * 0.5): 
                results['type'] = 'BEARISH BREAKDOWN 📉'
                results['close'] = curr_close
                results['volume'] = alert_volume
                results['time'] = formatted_ist
                return results

        # 2. Bullish Breakout Logic
        is_crossover = (prev_9 <= prev_20) and (curr_9 > curr_20)
        if is_crossover and (curr_close > curr_200):
            if candle_body > (avg_atr * 0.5):
                results['type'] = 'BULLISH BREAKOUT 🚀'
                results['close'] = curr_close
                results['volume'] = alert_volume
                results['time'] = formatted_ist
                return results
                
    except Exception as e:
        return None
    return None

def main():
    exchange = ccxt.delta({
        'enableRateLimit': True,
        'urls': {
            'api': {
                'public': 'https://api.india.delta.exchange',
                'private': 'https://api.india.delta.exchange',
            }
        }
    })
    
    target_tf = '15m' 
    
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
            # Updated alert output string formatting
            print(f"🚨 DELTA ALERT | {app_ticker} | {setup['type']} | Price: {setup['close']} | Vol: {setup['volume']:.2f} | Time: {setup['time']}")
            detected_count += 1

    print("-" * 50)
    print(f"Scan complete. Total active setups found: {detected_count}")

if __name__ == "__main__":
    main()