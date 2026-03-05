import requests
import json
import time
from datetime import datetime

class AISignalBotPro:
    """AI Signal Bot مع ICT Strategy + SMA - محسن"""
    
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
                'high': float(data['highPrice']),
                'low': float(data['lowPrice']),
                'open': float(data['openPrice'])
            }
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
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
                    'volume': float(k[5])
                })
            return candles
        except Exception as e:
            print(f"Error fetching klines: {e}")
            return []
    
    def calculate_sma(self, prices, period):
        """حساب SMA"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
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
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_atr(self, candles, period=14):
        """حساب ATR (Average True Range)"""
        if len(candles) < period + 1:
            return None
        
        tr_values = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            tr_values.append(max(tr1, tr2, tr3))
        
        return sum(tr_values[-period:]) / period
    
    def check_trend(self, candles):
        """التحقق من الاتجاه العام"""
        if len(candles) < 50:
            return 'NEUTRAL'
        
        prices = [c['close'] for c in candles]
        
        sma20 = self.calculate_sma(prices, 20)
        sma50 = self.calculate_sma(prices, 50)
        
        if not sma20 or not sma50:
            return 'NEUTRAL'
        
        # Higher highs and higher lows = UPTREND
        recent_highs = [c['high'] for c in candles[-20:]]
        recent_lows = [c['low'] for c in candles[-20:]]
        
        higher_highs = recent_highs[-1] > max(recent_highs[:10])
        higher_lows = recent_lows[-1] > min(recent_lows[:10])
        
        if sma20 > sma50 and higher_highs and higher_lows:
            return 'UPTREND'
        elif sma20 < sma50 and not higher_highs and not higher_lows:
            return 'DOWNTREND'
        else:
            return 'NEUTRAL'
    
    def check_killzone(self):
        """التحقق من Killzone"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # فقط London و NY (أعلى probability)
        if 8 <= hour < 11:
            return "London", True
        elif 13 <= hour < 16:
            return "New York", True
        else:
            return "Off-Hours", False
    
    def generate_signal(self, symbol, timeframe='1h'):
        """توليد الإشارة مع تأكيدات متعددة"""
        
        ticker = self.get_price(symbol)
        candles = self.get_klines(symbol, timeframe, 100)
        
        if not ticker or len(candles) < 50:
            return None
        
        prices = [c['close'] for c in candles]
        current_price = prices[-1]
        
        # حساب المؤشرات
        rsi = self.calculate_rsi(prices)
        atr = self.calculate_atr(candles)
        trend = self.check_trend(candles)
        killzone_name, in_killzone = self.check_killzone()
        
        sma9 = self.calculate_sma(prices, 9)
        sma21 = self.calculate_sma(prices, 21)
        
        # قائمة التأكيدات
        confirmations = []
        signal = 'HOLD'
        
        # 1. التحقق من Killzone (إجباري)
        if not in_killzone:
            return {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'signal': 'HOLD',
                'confidence': 0,
                'price': current_price,
                'rsi': round(rsi, 2),
                'reasons': [f"⏰ Outside Killzone ({killzone_name}) - No trading"],
                'confirmations': 0
            }
        
        # 2. تحليل الاتجاه + RSI + SMA
        # LONG Setup
        if trend == 'UPTREND' and rsi < 60 and sma9 > sma21:
            signal = 'BUY'
            confirmations.append("✅ Uptrend confirmed")
            confirmations.append(f"✅ RSI bullish ({rsi:.1f})")
            confirmations.append("✅ SMA9 > SMA21")
            
        # SHORT Setup  
        elif trend == 'DOWNTREND' and rsi > 40 and sma9 < sma21:
            signal = 'SELL'
            confirmations.append("✅ Downtrend confirmed")
            confirmations.append(f"✅ RSI bearish ({rsi:.1f})")
            confirmations.append("✅ SMA9 < SMA21")
        
        # 3. التحقق من الحجم
        if ticker['volume'] > 1000000:  # Volume كبير
            confirmations.append("✅ High volume")
        
        # 4. التحقق من 24h change (لا نتداول ضد الاتجاه اليومي)
        if signal == 'BUY' and ticker['change_24h'] < -5:
            signal = 'HOLD'
            confirmations.append("❌ 24h change too negative")
        elif signal == 'SELL' and ticker['change_24h'] > 5:
            signal = 'HOLD'
            confirmations.append("❌ 24h change too positive")
        
        # 5. حساب الثقة (3+ تأكيدات = 80%+ confidence)
        base_confidence = 50
        base_confidence += len(confirmations) * 10
        
        if in_killzone:
            base_confidence += 10
        
        confidence = min(95, base_confidence)
        
        # لا نتداول إلا بـ 3+ تأكيدات و confidence 80+
        if signal != 'HOLD' and (len(confirmations) < 3 or confidence < 80):
            signal = 'HOLD'
            confirmations.append(f"⚠️ Only {len(confirmations)} confirmations - No trade")
        
        signal_data = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'timeframe': timeframe,
            'signal': signal,
            'confidence': confidence,
            'price': current_price,
            'rsi': round(rsi, 2),
            'sma9': round(sma9, 2) if sma9 else None,
            'sma21': round(sma21, 2) if sma21 else None,
            'trend': trend,
            'killzone': killzone_name,
            'change_24h': round(ticker['change_24h'], 2),
            'volume': ticker['volume'],
            'reasons': confirmations,
            'confirmations': len(confirmations),
            'atr': round(atr, 2) if atr else None
        }
        
        return signal_data
    
    def print_signal(self, signal):
        """عرض الإشارة"""
        if not signal:
            return
            
        emoji = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '⚪'}.get(signal['signal'], '⚪')
        
        print(f"\n{'='*60}")
        print(f"{emoji} {signal['signal']} SIGNAL - {signal['symbol']}")
        print(f"{'='*60}")
        print(f"💰 Price: ${signal['price']:,.2f}")
        print(f"📊 Confidence: {signal['confidence']}%")
        print(f"🎯 Confirmations: {signal['confirmations']}/5")
        print(f"⏰ Killzone: {signal['killzone']}")
        print(f"📈 Trend: {signal['trend']}")
        print(f"\n📋 Confirmations:")
        for reason in signal['reasons']:
            print(f"   {reason}")
        print(f"{'='*60}\n")

if __name__ == "__main__":
    bot = AISignalBotPro()
    
    symbols = ['BTC', 'ETH', 'SOL']
    for symbol in symbols:
        signal = bot.generate_signal(symbol)
        if signal:
            bot.print_signal(signal)
        time.sleep(1)
