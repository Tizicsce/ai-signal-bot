import requests
import json
import time
from datetime import datetime

class AISignalBotPro:
    """AI Signal Bot مع ICT Strategy + SMA"""
    
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
        """جلب بيانات الشموع [open, high, low, close, volume]"""
        try:
            response = requests.get(
                f"{self.binance_url}/klines",
                params={'symbol': f'{symbol}USDT', 'interval': interval, 'limit': limit}
            )
            data = response.json()
            # [timestamp, open, high, low, close, volume, ...]
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
        """حساب Simple Moving Average (SMA)"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def calculate_ema(self, prices, period):
        """حساب Exponential Moving Average (EMA)"""
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
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def detect_fvg(self, candles):
        """
        ICT: Fair Value Gap (FVG) Detection
        FVG =gap بين high شمعة والlow شمعة تاليها
        """
        fvgs = []
        for i in range(len(candles) - 2):
            c1 = candles[i]   # شمعة أولى
            c2 = candles[i+1] # شمعة وسط (الإشارة)
            c3 = candles[i+2] # شمعة تالتة
            
            # Bullish FVG: low شمعة 3 > high شمعة 1
            if c3['low'] > c1['high']:
                fvgs.append({
                    'type': 'Bullish',
                    'top': c1['high'],
                    'bottom': c3['low'],
                    'index': i+1
                })
            
            # Bearish FVG: high شمعة 3 < low شمعة 1  
            elif c3['high'] < c1['low']:
                fvgs.append({
                    'type': 'Bearish',
                    'top': c1['low'],
                    'bottom': c3['high'],
                    'index': i+1
                })
        
        return fvgs
    
    def detect_order_blocks(self, candles):
        """
        ICT: Order Blocks (OB)
        منطقة شراء/بيع قوية قبل حركة كبيرة
        """
        obs = []
        for i in range(3, len(candles)):
            c_current = candles[i]
            c_prev = candles[i-1]
            c_before = candles[i-2]
            
            # Bullish OB: شمعة حمراء كبيرة قبل صعود قوي
            if (c_before['close'] < c_before['open'] and  # شمعة حمراء
                c_current['close'] > c_current['open'] and  # شمعة خضراء
                c_current['close'] > c_before['high']):     # اختراق
                obs.append({
                    'type': 'Bullish',
                    'high': c_before['high'],
                    'low': c_before['low'],
                    'index': i-1
                })
            
            # Bearish OB: شمعة خضراء كبيرة قبل هبوط قوي
            elif (c_before['close'] > c_before['open'] and  # شمعة خضراء
                  c_current['close'] < c_current['open'] and  # شمعة حمراء
                  c_current['close'] < c_before['low']):      # كسر
                obs.append({
                    'type': 'Bearish',
                    'high': c_before['high'],
                    'low': c_before['low'],
                    'index': i-1
                })
        
        return obs
    
    def detect_liquidity_sweep(self, candles, lookback=10):
        """
        ICT: Liquidity Sweep
        السعر يكسر high/low السابق ثم يرجع
        """
        if len(candles) < lookback + 2:
            return None
        
        recent = candles[-lookback-1:-1]
        current = candles[-1]
        
        prev_high = max([c['high'] for c in recent])
        prev_low = min([c['low'] for c in recent])
        
        # Bullish sweep: كسر low ثم ارتداد
        if current['low'] < prev_low and current['close'] > prev_low:
            return {
                'type': 'Bullish',
                'sweep_price': current['low'],
                'level': prev_low,
                'confirmation': current['close'] > prev_low
            }
        
        # Bearish sweep: كسر high ثم ارتداد
        elif current['high'] > prev_high and current['close'] < prev_high:
            return {
                'type': 'Bearish', 
                'sweep_price': current['high'],
                'level': prev_high,
                'confirmation': current['close'] < prev_high
            }
        
        return None
    
    def check_killzone(self):
        """
        ICT: Killzones (أوقات التداول النشط)
        London: 8:00-11:00 UTC
        New York: 13:00-16:00 UTC
        Asia: 0:00-4:00 UTC
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        if 8 <= hour < 11:
            return "London Killzone 🏴󠁧󠁢󠁥󠁮󠁧󠁿"
        elif 13 <= hour < 16:
            return "New York Killzone 🇺🇸"
        elif 0 <= hour < 4:
            return "Asia Killzone 🇯🇵"
        else:
            return "Low Activity ⏸️"
    
    def sma_crossover(self, prices):
        """
        SMA Crossover Strategy
        SMA 9 و SMA 21
        """
        sma9 = self.calculate_sma(prices, 9)
        sma21 = self.calculate_sma(prices, 21)
        sma50 = self.calculate_sma(prices, 50)
        
        if not sma9 or not sma21 or not sma50:
            return None, {}
        
        # Golden Cross: SMA9 > SMA21 > SMA50
        # Death Cross: SMA9 < SMA21 < SMA50
        
        signal = None
        if sma9 > sma21 > sma50:
            signal = 'BULLISH_CROSS'
        elif sma9 < sma21 < sma50:
            signal = 'BEARISH_CROSS'
        elif sma9 > sma21 and prices[-2] <= self.calculate_sma(prices[:-1], 9):
            signal = 'GOLDEN_CROSS'  # تقاطع للأعلى
        elif sma9 < sma21 and prices[-2] >= self.calculate_sma(prices[:-1], 9):
            signal = 'DEATH_CROSS'   # تقاطع للأسفل
        
        return signal, {
            'sma9': round(sma9, 2),
            'sma21': round(sma21, 2),
            'sma50': round(sma50, 2)
        }
    
    def generate_signal(self, symbol, timeframe='1h'):
        """توليد الإشارة الكاملة مع ICT + SMA"""
        
        # جلب البيانات
        ticker = self.get_price(symbol)
        candles = self.get_klines(symbol, timeframe, 200)
        
        if not ticker or len(candles) < 50:
            return None
        
        prices = [c['close'] for c in candles]
        current_price = prices[-1]
        
        # حساب المؤشرات التقليدية
        rsi = self.calculate_rsi(prices)
        
        # حساب SMA Crossover
        sma_signal, sma_data = self.sma_crossover(prices)
        
        # تحليل ICT
        fvgs = self.detect_fvg(candles[-20:])  # آخر 20 شمعة
        obs = self.detect_order_blocks(candles[-20:])
        sweep = self.detect_liquidity_sweep(candles)
        killzone = self.check_killzone()
        
        # منطق الإشارة المتكامل
        signal = 'HOLD'
        confidence = 50
        reasons = []
        ict_score = 0
        
        # 1. تحليل SMA
        if sma_signal in ['BULLISH_CROSS', 'GOLDEN_CROSS']:
            signal = 'BUY'
            confidence += 15
            reasons.append(f"📈 SMA Golden Cross ({sma_data['sma9']} > {sma_data['sma21']})")
            ict_score += 1
        elif sma_signal in ['BEARISH_CROSS', 'DEATH_CROSS']:
            signal = 'SELL'
            confidence += 15
            reasons.append(f"📉 SMA Death Cross ({sma_data['sma9']} < {sma_data['sma21']})")
            ict_score += 1
        
        # 2. تحليل RSI
        if rsi < 30:
            if signal == 'BUY':
                confidence += 10
            else:
                signal = 'BUY'
                confidence = 65
            reasons.append(f"💪 RSI Oversold ({rsi:.1f})")
        elif rsi > 70:
            if signal == 'SELL':
                confidence += 10
            else:
                signal = 'SELL'
                confidence = 65
            reasons.append(f"⚠️ RSI Overbought ({rsi:.1f})")
        
        # 3. تحليل ICT - FVG
        if fvgs:
            last_fvg = fvgs[-1]
            if last_fvg['type'] == 'Bullish' and current_price > last_fvg['top']:
                if signal == 'BUY':
                    confidence += 10
                reasons.append(f"🎯 Bullish FVG Filled")
                ict_score += 1
            elif last_fvg['type'] == 'Bearish' and current_price < last_fvg['bottom']:
                if signal == 'SELL':
                    confidence += 10
                reasons.append(f"🎯 Bearish FVG Filled")
                ict_score += 1
        
        # 4. تحليل ICT - Order Blocks
        if obs:
            last_ob = obs[-1]
            if last_ob['type'] == 'Bullish' and current_price > last_ob['high']:
                if signal == 'BUY':
                    confidence += 10
                reasons.append(f"🧱 Bullish OB Breakout")
                ict_score += 1
            elif last_ob['type'] == 'Bearish' and current_price < last_ob['low']:
                if signal == 'SELL':
                    confidence += 10
                reasons.append(f"🧱 Bearish OB Breakout")
                ict_score += 1
        
        # 5. تحليل ICT - Liquidity Sweep
        if sweep:
            if sweep['type'] == 'Bullish' and sweep['confirmation']:
                if signal != 'SELL':
                    signal = 'BUY'
                    confidence += 15
                reasons.append(f"💧 Bullish Liquidity Sweep")
                ict_score += 2
            elif sweep['type'] == 'Bearish' and sweep['confirmation']:
                if signal != 'BUY':
                    signal = 'SELL'
                    confidence += 15
                reasons.append(f"💧 Bearish Liquidity Sweep")
                ict_score += 2
        
        # 6. Killzone bonus
        if 'Killzone' in killzone:
            confidence += 5
            reasons.append(f"⏰ {killzone}")
        
        # 7. Volume Analysis
        if ticker['volume'] > 1000000:
            confidence += 5
            reasons.append("📊 High Volume")
        
        # تحديد درجة الثقة النهائية
        confidence = min(98, confidence)
        
        # تجميع البيانات
        signal_data = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'timeframe': timeframe,
            'signal': signal,
            'confidence': confidence,
            'price': current_price,
            'rsi': round(rsi, 2),
            'sma': sma_data,
            'ict_score': ict_score,
            'killzone': killzone,
            'fvg_count': len(fvgs),
            'ob_count': len(obs),
            'sweep': sweep['type'] if sweep else None,
            'change_24h': round(ticker['change_24h'], 2),
            'volume': ticker['volume'],
            'reasons': reasons,
            'strategy': 'ICT + SMA Crossover'
        }
        
        self.signals.append(signal_data)
        return signal_data
    
    def print_signal(self, signal):
        """عرض الإشارة بشكل جميل"""
        emoji = {'BUY': '🟢', 'SELL': '🔴', 'HOLD': '⚪'}[signal['signal']]
        
        print(f"\n{'='*60}")
        print(f"{emoji} {signal['signal']} SIGNAL - {signal['symbol']}")
        print(f"{'='*60}")
        print(f"💰 Price: ${signal['price']:,.2f}")
        print(f"📊 Confidence: {signal['confidence']}%")
        print(f"🎯 Strategy: {signal['strategy']}")
        print(f"⏰ Timeframe: {signal['timeframe']}")
        print(f"🕒 Killzone: {signal['killzone']}")
        print(f"\n📈 Indicators:")
        print(f"   RSI: {signal['rsi']}")
        print(f"   SMA9: ${signal['sma']['sma9']:,.2f}")
        print(f"   SMA21: ${signal['sma']['sma21']:,.2f}")
        print(f"   SMA50: ${signal['sma']['sma50']:,.2f}")
        print(f"\n🎯 ICT Analysis:")
        print(f"   FVGs detected: {signal['fvg_count']}")
        print(f"   Order Blocks: {signal['ob_count']}")
        print(f"   Liquidity Sweep: {signal['sweep'] or 'None'}")
        print(f"   ICT Score: {signal['ict_score']}/6")
        print(f"\n📋 Reasons:")
        for reason in signal['reasons']:
            print(f"   • {reason}")
        print(f"{'='*60}\n")
    
    def monitor(self, symbols=['BTC', 'ETH', 'SOL'], interval=300):
        """مراقبة مستمرة"""
        print("=" * 70)
        print("🤖 AI Signal Bot PRO - ICT + SMA Strategy")
        print("=" * 70)
        print("\n📚 Strategies:")
        print("   • ICT: Fair Value Gaps, Order Blocks, Liquidity Sweeps")
        print("   • SMA: 9/21/50 Crossover System")
        print("   • RSI: Overbought/Oversold Confirmation")
        print("   • Killzones: London, NY, Asia Sessions")
        print("=" * 70)
        
        while True:
            print(f"\n🔍 Scanning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("-" * 70)
            
            for symbol in symbols:
                signal = self.generate_signal(symbol)
                if signal:
                    self.print_signal(signal)
            
            print(f"\n⏳ Next scan in {interval}s...")
            print("💡 Press Ctrl+C to stop")
            time.sleep(interval)
    
    def scan_once(self, symbols=['BTC', 'ETH', 'SOL', 'BNB', 'XRP']):
        """مسح لمرة واحدة"""
        print("=" * 70)
        print("🤖 AI Signal Bot PRO - Single Scan")
        print("=" * 70)
        
        results = []
        for symbol in symbols:
            signal = self.generate_signal(symbol)
            if signal:
                self.print_signal(signal)
                results.append(signal)
        
        return results

if __name__ == "__main__":
    bot = AISignalBotPro()
    
    # مسح لمرة واحدة
    bot.scan_once()
    
    # للمراقبة المستمرة، شيل التعليق:
    # bot.monitor(['BTC', 'ETH', 'SOL'], interval=300)
