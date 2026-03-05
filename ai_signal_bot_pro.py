import requests
import json
import time
from datetime import datetime

class AISignalBotPro:
    """
    Advanced Trading Strategy
    ICT + SMA + Order Flow + Market Structure
    شرط: 4+ تأكيدات للدخول
    """
    
    def __init__(self):
        self.binance_url = "https://api.binance.com/api/v3"
        self.signals = []
        
    def get_price(self, symbol):
        """جلب السعر الحالي"""
        try:
            response = requests.get(f"{self.binance_url}/ticker/24hr?symbol={symbol}USDT")
            data = response.json()
            return {
                'symbol': symbol,
                'price': float(data['lastPrice']),
                'change_24h': float(data['priceChangePercent']),
                'volume': float(data['volume']),
                'quote_volume': float(data['quoteVolume']),
                'high': float(data['highPrice']),
                'low': float(data['lowPrice']),
                'open': float(data['openPrice']),
                'bid_qty': float(data.get('bidQty', 0)),
                'ask_qty': float(data.get('askQty', 0))
            }
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def get_klines(self, symbol, interval='1h', limit=200):
        """جلب بيانات الشموع"""
        try:
            response = requests.get(
                f"{self.binance_url}/klines",
                params={'symbol': f'{symbol}USDT', 'interval': interval, 'limit': limit}
            )
            data = response.json()
            candles = []
            for k in data:
                candles.append({
                    'timestamp': k[0],
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5]),
                    'quote_volume': float(k[7]),
                    'buy_volume': float(k[9]),  # Taker buy base volume
                    'buy_quote': float(k[10])   # Taker buy quote volume
                })
            return candles
        except:
            return []
    
    def calculate_sma(self, prices, period):
        """حساب SMA"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def calculate_ema(self, prices, period):
        """حساب EMA"""
        if len(prices) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def calculate_rsi(self, prices, period=14):
        """حساب RSI"""
        if len(prices) < period + 1:
            return 50
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def calculate_macd(self, prices):
        """حساب MACD"""
        ema12 = self.calculate_ema(prices, 12)
        ema26 = self.calculate_ema(prices, 26)
        if not ema12 or not ema26:
            return None, None
        macd_line = ema12 - ema26
        signal_line = self.calculate_ema([macd_line] * 9, 9)  # Simplified
        return macd_line, signal_line
    
    # ========== ICT STRATEGY ==========
    
    def detect_fvg(self, candles):
        """Fair Value Gaps"""
        fvgs = []
        for i in range(len(candles) - 2):
            c1, c2, c3 = candles[i], candles[i+1], candles[i+2]
            # Bullish FVG
            if c3['low'] > c1['high']:
                fvgs.append({'type': 'Bullish', 'top': c1['high'], 'bottom': c3['low'], 'index': i+1})
            # Bearish FVG
            elif c3['high'] < c1['low']:
                fvgs.append({'type': 'Bearish', 'top': c1['low'], 'bottom': c3['high'], 'index': i+1})
        return fvgs
    
    def detect_order_blocks(self, candles):
        """Order Blocks"""
        obs = []
        for i in range(3, len(candles)):
            c_before = candles[i-2]
            c_current = candles[i]
            # Bullish OB
            if (c_before['close'] < c_before['open'] and 
                c_current['close'] > c_before['high']):
                obs.append({'type': 'Bullish', 'high': c_before['high'], 'low': c_before['low']})
            # Bearish OB
            elif (c_before['close'] > c_before['open'] and 
                  c_current['close'] < c_before['low']):
                obs.append({'type': 'Bearish', 'high': c_before['high'], 'low': c_before['low']})
        return obs
    
    def detect_break_of_structure(self, candles):
        """Break of Structure (BOS)"""
        if len(candles) < 10:
            return None
        
        recent = candles[-10:]
        highs = [c['high'] for c in recent]
        lows = [c['low'] for c in recent]
        
        current = candles[-1]
        
        # Bullish BOS: كسر أعلى high سابق
        if current['close'] > max(highs[:-1]):
            return 'BULLISH_BOS'
        # Bearish BOS: كسر أقل low سابق
        elif current['close'] < min(lows[:-1]):
            return 'BEARISH_BOS'
        return None
    
    def detect_liquidity_sweep(self, candles):
        """Liquidity Sweep"""
        if len(candles) < 10:
            return None
        
        recent = candles[-10:-1]
        current = candles[-1]
        
        prev_high = max([c['high'] for c in recent])
        prev_low = min([c['low'] for c in recent])
        
        # Bullish sweep
        if current['low'] < prev_low and current['close'] > prev_low:
            return {'type': 'Bullish', 'swept': prev_low, 'close': current['close']}
        # Bearish sweep
        elif current['high'] > prev_high and current['close'] < prev_high:
            return {'type': 'Bearish', 'swept': prev_high, 'close': current['close']}
        return None
    
    # ========== ORDER FLOW ==========
    
    def analyze_order_flow(self, candles):
        """تحليل Order Flow"""
        if len(candles) < 5:
            return None
        
        recent = candles[-5:]
        
        # حساب delta (buy volume - sell volume)
        total_buy = sum([c['buy_volume'] for c in recent])
        total_vol = sum([c['volume'] for c in recent])
        
        buy_ratio = total_buy / total_vol if total_vol > 0 else 0.5
        
        # Volume analysis
        avg_volume = sum([c['volume'] for c in candles[-20:]]) / 20
        current_volume = recent[-1]['volume']
        volume_spike = current_volume > avg_volume * 1.5
        
        return {
            'buy_ratio': buy_ratio,
            'volume_spike': volume_spike,
            'delta_bullish': buy_ratio > 0.55,
            'delta_bearish': buy_ratio < 0.45
        }
    
    def analyze_market_structure(self, candles):
        """تحليل بنية السوق"""
        if len(candles) < 20:
            return 'NEUTRAL'
        
        # Higher Highs & Higher Lows = Uptrend
        highs = [c['high'] for c in candles[-20:]]
        lows = [c['low'] for c in candles[-20:]]
        
        hh = highs[-1] > max(highs[:10])
        hl = lows[-1] > min(lows[:10])
        
        lh = highs[-1] < max(highs[:10])
        ll = lows[-1] < min(lows[:10])
        
        if hh and hl:
            return 'UPTREND'
        elif lh and ll:
            return 'DOWNTREND'
        return 'NEUTRAL'
    
    # ========== MAIN STRATEGY ==========
    
    def generate_signal(self, symbol, timeframe='1h'):
        """
        توليد الإشارة مع 4+ تأكيدات:
        1. ICT (FVG, OB, BOS, Sweep)
        2. SMA (9/21/50)
        3. Order Flow
        4. Market Structure
        5. MACD
        6. RSI
        """
        
        ticker = self.get_price(symbol)
        candles = self.get_klines(symbol, timeframe, 200)
        
        if not ticker or len(candles) < 50:
            return None
        
        prices = [c['close'] for c in candles]
        current_price = prices[-1]
        
        # حساب المؤشرات
        rsi = self.calculate_rsi(prices)
        sma9 = self.calculate_sma(prices, 9)
        sma21 = self.calculate_sma(prices, 21)
        sma50 = self.calculate_sma(prices, 50)
        macd, macd_signal = self.calculate_macd(prices)
        
        # ICT Analysis
        fvgs = self.detect_fvg(candles[-30:])
        obs = self.detect_order_blocks(candles[-30:])
        bos = self.detect_break_of_structure(candles)
        sweep = self.detect_liquidity_sweep(candles)
        
        # Order Flow & Structure
        order_flow = self.analyze_order_flow(candles)
        market_structure = self.analyze_market_structure(candles)
        
        # التأكيدات
        confirmations = []
        signal = 'HOLD'
        
        # ========== تحليل LONG ==========
        long_confirmations = []
        
        # 1. Market Structure (أهم شي)
        if market_structure == 'UPTREND':
            long_confirmations.append("✅ UPTREND Structure")
        
        # 2. SMA Alignment
        if sma9 and sma21 and sma50:
            if sma9 > sma21 > sma50:
                long_confirmations.append("✅ SMA Bullish (9>21>50)")
        
        # 3. MACD
        if macd and macd_signal and macd > macd_signal and macd > 0:
            long_confirmations.append("✅ MACD Bullish")
        
        # 4. RSI
        if 40 < rsi < 65:
            long_confirmations.append(f"✅ RSI Optimal ({rsi:.1f})")
        
        # 5. ICT - BOS
        if bos == 'BULLISH_BOS':
            long_confirmations.append("✅ Bullish BOS")
        
        # 6. ICT - Liquidity Sweep
        if sweep and sweep['type'] == 'Bullish':
            long_confirmations.append("✅ Bullish Liquidity Sweep")
        
        # 7. ICT - FVG
        if fvgs and fvgs[-1]['type'] == 'Bullish':
            long_confirmations.append("✅ Bullish FVG")
        
        # 8. ICT - Order Block
        if obs and obs[-1]['type'] == 'Bullish':
            long_confirmations.append("✅ Bullish Order Block")
        
        # 9. Order Flow
        if order_flow:
            if order_flow['delta_bullish'] and order_flow['volume_spike']:
                long_confirmations.append("✅ Bullish Order Flow + Volume")
        
        # ========== تحليل SHORT ==========
        short_confirmations = []
        
        # 1. Market Structure
        if market_structure == 'DOWNTREND':
            short_confirmations.append("✅ DOWNTREND Structure")
        
        # 2. SMA Alignment
        if sma9 and sma21 and sma50:
            if sma9 < sma21 < sma50:
                short_confirmations.append("✅ SMA Bearish (9<21<50)")
        
        # 3. MACD
        if macd and macd_signal and macd < macd_signal and macd < 0:
            short_confirmations.append("✅ MACD Bearish")
        
        # 4. RSI
        if 35 < rsi < 60:
            short_confirmations.append(f"✅ RSI Optimal ({rsi:.1f})")
        
        # 5. ICT - BOS
        if bos == 'BEARISH_BOS':
            short_confirmations.append("✅ Bearish BOS")
        
        # 6. ICT - Liquidity Sweep
        if sweep and sweep['type'] == 'Bearish':
            short_confirmations.append("✅ Bearish Liquidity Sweep")
        
        # 7. ICT - FVG
        if fvgs and fvgs[-1]['type'] == 'Bearish':
            short_confirmations.append("✅ Bearish FVG")
        
        # 8. ICT - Order Block
        if obs and obs[-1]['type'] == 'Bearish':
            short_confirmations.append("✅ Bearish Order Block")
        
        # 9. Order Flow
        if order_flow:
            if order_flow['delta_bearish'] and order_flow['volume_spike']:
                short_confirmations.append("✅ Bearish Order Flow + Volume")
        
        # ========== اختيار الإشارة ==========
        
        # شرط الدخول: 5+ تأكيدات
        if len(long_confirmations) >= 5:
            signal = 'BUY'
            confirmations = long_confirmations
        elif len(short_confirmations) >= 5:
            signal = 'SELL'
            confirmations = short_confirmations
        else:
            # لا إشارة
            max_conf = max(len(long_confirmations), len(short_confirmations))
            return {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'signal': 'HOLD',
                'confidence': max_conf * 10,
                'price': current_price,
                'reasons': [f"⚠️ Only {max_conf}/9 confirmations - Waiting"],
                'long_score': len(long_confirmations),
                'short_score': len(short_confirmations),
                'confirmations': 0
            }
        
        # حساب الثقة
        confidence = min(98, 60 + len(confirmations) * 5)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'timeframe': timeframe,
            'signal': signal,
            'confidence': confidence,
            'price': current_price,
            'rsi': round(rsi, 2),
            'sma9': round(sma9, 2) if sma9 else None,
            'sma21': round(sma21, 2) if sma21 else None,
            'sma50': round(sma50, 2) if sma50 else None,
            'macd': round(macd, 4) if macd else None,
            'market_structure': market_structure,
            'bos': bos,
            'sweep': sweep['type'] if sweep else None,
            'fvg_count': len(fvgs),
            'ob_count': len(obs),
            'order_flow': order_flow['buy_ratio'] if order_flow else None,
            'change_24h': round(ticker['change_24h'], 2),
            'reasons': confirmations,
            'confirmations': len(confirmations),
            'long_score': len(long_confirmations),
            'short_score': len(short_confirmations)
        }
    
    def print_signal(self, signal):
        """عرض الإشارة"""
        if not signal:
            return
        
        emoji = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '⚪'}.get(signal['signal'], '⚪')
        
        print(f"\n{'='*70}")
        print(f"{emoji} {signal['signal']} SIGNAL - {signal['symbol']} (ADVANCED STRATEGY)")
        print(f"{'='*70}")
        print(f"💰 Price: ${signal['price']:,.2f}")
        print(f"📊 Confidence: {signal['confidence']}%")
        print(f"🎯 Confirmations: {signal['confirmations']}/9 REQUIRED")
        print(f"📈 Long Score: {signal['long_score']}/9 | Short Score: {signal['short_score']}/9")
        print(f"📊 Market Structure: {signal['market_structure']}")
        print(f"🔄 BOS: {signal['bos'] or 'None'}")
        print(f"💧 Sweep: {signal['sweep'] or 'None'}")
        print(f"\n📋 Confirmations:")
        for reason in signal['reasons']:
            print(f"   {reason}")
        print(f"{'='*70}\n")

if __name__ == "__main__":
    bot = AISignalBotAdvanced()
    
    symbols = ['BTC', 'ETH', 'SOL']
    for symbol in symbols:
        signal = bot.generate_signal(symbol)
        if signal:
            bot.print_signal(signal)
        time.sleep(1)
