import os
import time
import requests
import json
import hashlib
import sqlite3
import threading
from datetime import datetime
from flask import Flask, request, redirect, jsonify, render_template_string
from ai_signal_bot_pro import AISignalBotPro

app = Flask(__name__)
DATABASE = 'urls.db'

# Telegram Config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8439293396:AAHAkRFRAkgLmU17M4I8_LPXocAezDvQxE0')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '5580867960')

class PaperTradingBotWithLeverage:
    """Paper Trading Bot مع Leverage + Long/Short"""
    
    def __init__(self, initial_balance=10000, default_leverage=5):
        self.bot = AISignalBotPro()
        self.balance = initial_balance
        self.positions = {}
        self.trade_history = []
        self.initial_balance = initial_balance
        self.default_leverage = default_leverage
        self.running = False
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
    
    def open_position(self, symbol, signal_data, leverage=None):
        """فتح صفقة مع Leverage"""
        if symbol in self.positions:
            return False
        
        if leverage is None:
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
        
        message = f"""{emoji} <b>PAPER TRADE OPENED - {direction}</b> {emoji}

📊 <b>{symbol}</b> | {direction} x{leverage}
💰 Entry: <code>${price:,.2f}</code>
💵 Position: ${position_value:,.2f}
🔷 Margin: ${margin_required:,.2f}
⚡ Leverage: x{leverage}

🎯 TP1: ${tp1:,.2f} | TP2: ${tp2:,.2f} | TP3: ${tp3:,.2f}
🛑 SL: ${sl:,.2f}

💼 Balance: ${self.balance:,.2f}
⏰ {datetime.now().strftime('%H:%M:%S')}"""
        
        self.send_telegram(message)
        print(f"🟢 OPENED {direction} {symbol} x{leverage}")
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

📊 {symbol} | {direction} x{leverage}
🔔 {reason}

💰 Entry: ${entry:,.2f} → Exit: ${exit_price:,.2f}
📊 Change: {price_change_pct*100:+.2f}% → {leveraged_change_pct*100:+.2f}%
💵 P&L: ${pnl:,.2f}

💼 Balance: ${self.balance:,.2f}
📈 Total: ${self.balance - self.initial_balance:+.2f}"""
        
        self.send_telegram(message)
        print(f"{emoji} CLOSED {symbol} P&L: ${pnl:.2f}")
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
    
    def run_scan(self):
        """مسح واحد"""
        symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
        print(f"\n🔍 {datetime.now().strftime('%H:%M:%S')}")
        
        for symbol in symbols:
            try:
                price_data = self.bot.get_price(symbol)
                if price_data:
                    self.check_positions(symbol, price_data['price'])
                
                signal = self.bot.generate_signal(symbol)
                if not signal:
                    continue
                
                direction = 'LONG' if signal['signal'] == 'BUY' else 'SHORT' if signal['signal'] == 'SELL' else 'HOLD'
                print(f"{symbol}: {direction} ({signal['confidence']}%)")
                
                if signal['signal'] in ['BUY', 'SELL'] and signal['confidence'] >= 60:
                    if symbol not in self.positions:
                        self.open_position(symbol, signal, self.default_leverage)
                
            except Exception as e:
                print(f"❌ {symbol}: {e}")
    
    def run_loop(self):
        """Loop رئيسي - Sleep مقسم باش Railway ما يوقفش"""
        self.running = True
        last_scan = 0
        scan_interval = 300  # 5 minutes
        
        self.send_telegram("🤖 <b>Paper Trading Bot Started</b>\n\n💰 Balance: $10,000\n⚡ Leverage: x5\n⏰ Scanning every 5 min")
        
        while self.running:
            current_time = time.time()
            
            # إلا مرات 5 دقايق، دير Scan
            if current_time - last_scan >= scan_interval:
                self.run_scan()
                last_scan = current_time
                print("⏳ Next scan in 5 min...")
            
            # Sleep 30 ثانية فقط (باش Railway ما يحسبش Idle)
            time.sleep(30)

# Global bot instance
bot_instance = None

def start_bot():
    """Start bot in background thread"""
    global bot_instance
    bot_instance = PaperTradingBotWithLeverage(initial_balance=10000, default_leverage=5)
    bot_instance.run_loop()

# ========== FLASK ROUTES ==========

@app.route('/')
def index():
    """Health check + status"""
    global bot_instance
    status = {
        'status': 'running' if bot_instance and bot_instance.running else 'stopped',
        'time': datetime.now().isoformat(),
        'balance': bot_instance.balance if bot_instance else 10000,
        'positions': len(bot_instance.positions) if bot_instance else 0
    }
    return jsonify(status)

@app.route('/health')
def health():
    """Simple health check"""
    return jsonify({
        'status': 'alive',
        'time': datetime.now().isoformat(),
        'bot_running': bot_instance.running if bot_instance else False
    })

@app.route('/scan', methods=['POST'])
def manual_scan():
    """Manual scan trigger"""
    global bot_instance
    if bot_instance:
        bot_instance.run_scan()
        return jsonify({'status': 'scan completed'})
    return jsonify({'status': 'bot not running'}), 500

if __name__ == '__main__':
    # Start bot in background thread
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)
