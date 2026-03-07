import os
import sys
import time
import requests
import json
import hashlib
import sqlite3
import threading
from flask import Flask
from datetime import datetime
from ai_signal_bot_pro import AISignalBotPro

# Flask App for Keep-Alive
app = Flask(__name__)

# Telegram Config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8439293396:AAHAkRFRAkgLmU17M4I8_LPXocAezDvQxE0')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '5580867960')

class PaperTradingBotCron:
    """Paper Trading Bot - Cron Version (يشغل مرة كل 5 دقايق)"""
    
    def __init__(self, initial_balance=10000, default_leverage=5):
        self.bot = AISignalBotPro()
        self.balance = initial_balance
        self.positions = {}
        self.trade_history = []
        self.initial_balance = initial_balance
        self.default_leverage = default_leverage
        self.load_state()
    
    def send_telegram(self, message):
        """Send message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
            requests.post(url, json=payload, timeout=10)
        except:
            pass
    
    def load_state(self):
        """تحميل الحالة"""
        try:
            if os.path.exists('paper_trading_state.json'):
                with open('paper_trading_state.json', 'r') as f:
                    data = json.load(f)
                    self.balance = data.get('balance', self.initial_balance)
                    self.positions = data.get('positions', {})
                    self.trade_history = data.get('trade_history', [])
        except:
            pass
    
    def save_state(self):
        """حفظ الحالة"""
        try:
            data = {
                'balance': self.balance,
                'positions': self.positions,
                'trade_history': self.trade_history[-100:],
                'last_update': datetime.now().isoformat()
            }
            with open('paper_trading_state.json', 'w') as f:
                json.dump(data, f, indent=2)
        except:
            pass
    
    def open_position(self, symbol, signal_data):
        """فتح صفقة"""
        if symbol in self.positions:
            return False
        
        leverage = self.default_leverage
        price = signal_data['price']
        signal_type = signal_data['signal']
        
        if signal_type == 'BUY':
            tp1, tp2, tp3, sl = price * 1.02, price * 1.04, price * 1.06, price * 0.98
        else:
            tp1, tp2, tp3, sl = price * 0.98, price * 0.96, price * 0.94, price * 1.02
        
        position_value = min(self.balance * 0.10, 1000)
        margin_required = position_value / leverage
        amount = position_value / price
        
        self.positions[symbol] = {
            'entry': price, 'amount': amount, 'type': signal_type,
            'leverage': leverage, 'margin': margin_required,
            'position_value': position_value,
            'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl,
            'opened_at': datetime.now().isoformat()
        }
        
        self.balance -= margin_required
        
        emoji = '🟢' if signal_type == 'BUY' else '🔴'
        direction = 'LONG' if signal_type == 'BUY' else 'SHORT'
        
        message = f"""{emoji} <b>TRADE OPENED - {direction}</b> {emoji}

📊 <b>{symbol}</b> | x{leverage}
💰 Entry: <code>${price:,.2f}</code>
💵 Position: ${position_value:,.2f}
🔷 Margin: ${margin_required:,.2f}

🎯 TP1: ${tp1:,.2f} | TP2: ${tp2:,.2f} | TP3: ${tp3:,.2f}
🛑 SL: ${sl:,.2f}

💼 Balance: ${self.balance:,.2f}
⏰ {datetime.now().strftime('%H:%M:%S')}"""
        
        self.send_telegram(message)
        self.save_state()
        return True
    
    def close_position(self, symbol, exit_price, reason):
        """إغلاق صفقة"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        entry, amount, signal_type = pos['entry'], pos['amount'], pos['type']
        leverage, margin = pos['leverage'], pos['margin']
        position_value = pos['position_value']
        
        if signal_type == 'BUY':
            price_change_pct = (exit_price - entry) / entry
        else:
            price_change_pct = (entry - exit_price) / entry
        
        leveraged_change_pct = price_change_pct * leverage
        pnl = position_value * leveraged_change_pct
        
        self.balance += margin + pnl
        
        emoji = '✅' if pnl > 0 else '❌'
        direction = 'LONG' if signal_type == 'BUY' else 'SHORT'
        
        message = f"""{emoji} <b>CLOSED - {direction}</b> {emoji}

📊 {symbol} | x{leverage}
🔔 {reason}
💰 ${entry:,.2f} → ${exit_price:,.2f}
📊 {leveraged_change_pct*100:+.2f}%
💵 P&L: ${pnl:,.2f}

💼 Balance: ${self.balance:,.2f}
📈 Total: ${self.balance - self.initial_balance:+.2f}"""
        
        self.send_telegram(message)
        del self.positions[symbol]
        self.save_state()
    
    def check_positions(self, symbol, current_price):
        """التحقق من TP/SL"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        signal_type = pos['type']
        
        if signal_type == 'BUY':
            if current_price <= pos['sl']:
                self.close_position(symbol, current_price, 'SL')
            elif current_price >= pos['tp3']:
                self.close_position(symbol, current_price, 'TP3')
        else:
            if current_price >= pos['sl']:
                self.close_position(symbol, current_price, 'SL')
            elif current_price <= pos['tp3']:
                self.close_position(symbol, current_price, 'TP3')
    
    def run_once(self):
        """تشغيل مرة واحدة (لـ Cron Job)"""
        print(f"🔍 {datetime.now().strftime('%H:%M:%S')} - Starting scan...")
        
        symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
        
        for symbol in symbols:
            try:
                # Check positions
                price_data = self.bot.get_price(symbol)
                if price_data:
                    self.check_positions(symbol, price_data['price'])
                
                # Generate signal
                signal = self.bot.generate_signal(symbol)
                if not signal:
                    continue
                
                direction = 'LONG' if signal['signal'] == 'BUY' else 'SHORT' if signal['signal'] == 'SELL' else 'HOLD'
                print(f"{symbol}: {direction} ({signal['confidence']}%)")
                
                # Open position if strong signal
                if signal['signal'] in ['BUY', 'SELL'] and signal['confidence'] >= 60:
                    if symbol not in self.positions:
                        self.open_position(symbol, signal)
                
            except Exception as e:
                print(f"❌ {symbol}: {e}")
        
        print(f"✅ Scan complete. Positions: {len(self.positions)}")
        print(f"💰 Balance: ${self.balance:,.2f}")

# Flask Routes for Keep-Alive
@app.route('/')
def home():
    return {
        "status": "alive",
        "bot": "AI Signal Bot - Paper Trading",
        "time": datetime.now().isoformat(),
        "version": "2.0"
    }

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.route('/status')
def status():
    """Get current trading status"""
    try:
        bot = PaperTradingBotCron()
        return {
            "balance": bot.balance,
            "positions": len(bot.positions),
            "open_positions": list(bot.positions.keys()),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    # Create bot instance
    bot = PaperTradingBotCron()
    
    # Function to run trading in background
    def run_trading_loop():
        print("🤖 Starting trading loop...")
        while True:
            try:
                bot.run_once()
                print(f"⏳ Sleeping 5 minutes...")
                time.sleep(300)  # 5 minutes
            except Exception as e:
                print(f"❌ Error in trading loop: {e}")
                time.sleep(60)  # Wait 1 min on error
    
    # Start trading in background thread
    trading_thread = threading.Thread(target=run_trading_loop, daemon=True)
    trading_thread.start()
    
    # Send startup message
    bot.send_telegram("""🚀 <b>AI Signal Bot Started</b>

🤖 Mode: Paper Trading + Leverage
⚡ Leverage: x5
📊 Symbols: BTC, ETH, SOL, BNB, XRP
⏰ Scan Interval: 5 minutes

<i>📝 Bot is now running and monitoring markets...</i>""")
    
    # Start Flask server (keeps Railway alive)
    print("🌐 Starting keep-alive server on port 5000...")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
