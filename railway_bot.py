import os
import time
import requests
import json
from datetime import datetime
from ai_signal_bot_pro import AISignalBotPro

# Telegram Config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8439293396:AAHAkRFRAkgLmU17M4I8_LPXocAezDvQxE0')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '5580867960')

class PaperTradingBotWithTelegram:
    """Paper Trading Bot مع Telegram Notifications"""
    
    def __init__(self, initial_balance=10000):
        self.bot = AISignalBotPro()
        self.balance = initial_balance
        self.positions = {}
        self.trade_history = []
        self.initial_balance = initial_balance
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
        
        price = signal_data['price']
        signal_type = signal_data['signal']
        
        # Calculate TP/SL (2%, 4%, 6% / -2% SL)
        if signal_type == 'BUY':
            tp1, tp2, tp3, sl = price * 1.02, price * 1.04, price * 1.06, price * 0.98
        else:
            tp1, tp2, tp3, sl = price * 0.98, price * 0.96, price * 0.94, price * 1.02
        
        # Position size (10% of balance)
        position_value = min(self.balance * 0.10, 1000)
        amount = position_value / price
        
        self.positions[symbol] = {
            'entry': price, 'amount': amount, 'type': signal_type,
            'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl,
            'opened_at': datetime.now().isoformat()
        }
        
        self.balance -= position_value
        
        # Send Telegram
        emoji = '🟢' if signal_type == 'BUY' else '🔴'
        message = f"""{emoji} <b>PAPER TRADE OPENED</b> {emoji}

📊 <b>{symbol}</b> | {signal_type}
💰 Entry: <code>${price:,.2f}</code>
💵 Size: ${position_value:,.2f}
📦 Amount: {amount:.4f} {symbol}

🎯 <b>Targets:</b>
🥇 TP1: ${tp1:,.2f}
🥈 TP2: ${tp2:,.2f}
🥉 TP3: ${tp3:,.2f}

🛑 SL: ${sl:,.2f}

💼 Balance: ${self.balance:,.2f}
⏰ {datetime.now().strftime('%H:%M:%S')}

<i>📝 Paper Trading - Not Real Money</i>"""
        
        self.send_telegram(message)
        print(f"🟢 OPENED {signal_type} {symbol} @ ${price:.2f}")
        
        self.save_state()
        return True
    
    def close_position(self, symbol, exit_price, reason):
        """إغلاق صفقة"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        entry, amount, signal_type = pos['entry'], pos['amount'], pos['type']
        
        # Calculate P&L
        if signal_type == 'BUY':
            pnl = (exit_price - entry) * amount
        else:
            pnl = (entry - exit_price) * amount
        
        position_value = entry * amount
        pnl_percent = (pnl / position_value) * 100
        
        # Update balance
        self.balance += position_value + pnl
        
        # Send Telegram
        emoji = '✅' if pnl > 0 else '❌'
        message = f"""{emoji} <b>PAPER TRADE CLOSED</b> {emoji}

📊 <b>{symbol}</b> | {signal_type}
🔔 Reason: {reason}

💰 Entry: <code>${entry:,.2f}</code>
💰 Exit: <code>${exit_price:,.2f}</code>

📈 <b>P&L:</b>
💵 ${pnl:,.2f} ({pnl_percent:+.2f}%)

💼 Balance: ${self.balance:,.2f}
📊 Total P&L: ${self.balance - self.initial_balance:+.2f}
⏰ {datetime.now().strftime('%H:%M:%S')}

<i>📝 Paper Trading - Not Real Money</i>"""
        
        self.send_telegram(message)
        print(f"{emoji} CLOSED {symbol} ({reason}) P&L: ${pnl:.2f}")
        
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
            elif current_price >= pos['tp2'] and not pos.get('tp2_hit'):
                pos['tp2_hit'] = True
                print(f"🎯 TP2 hit: {symbol}")
            elif current_price >= pos['tp1'] and not pos.get('tp1_hit'):
                pos['tp1_hit'] = True
                print(f"🎯 TP1 hit: {symbol}")
        else:  # SELL
            if current_price >= pos['sl']:
                self.close_position(symbol, current_price, 'SL')
            elif current_price <= pos['tp3']:
                self.close_position(symbol, current_price, 'TP3')
            elif current_price <= pos['tp2'] and not pos.get('tp2_hit'):
                pos['tp2_hit'] = True
                print(f"🎯 TP2 hit: {symbol}")
            elif current_price <= pos['tp1'] and not pos.get('tp1_hit'):
                pos['tp1_hit'] = True
                print(f"🎯 TP1 hit: {symbol}")
    
    def run(self, symbols=None, interval_minutes=5):
        """تشغيل البوت"""
        if symbols is None:
            symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
        
        print("🤖 PAPER TRADING BOT WITH TELEGRAM")
        print(f"💰 Paper Balance: ${self.balance:,.2f}")
        
        # Startup message
        self.send_telegram(f"""🤖 <b>Paper Trading Bot Started</b>

💰 Balance: ${self.balance:,.2f}
📊 Symbols: {', '.join(symbols)}
⏰ Interval: {interval_minutes} min

<i>📝 Trading with virtual money</i>""")
        
        while True:
            print(f"\n🔍 {datetime.now().strftime('%H:%M:%S')}")
            
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
                    
                    print(f"{symbol}: {signal['signal']} ({signal['confidence']}%)")
                    
                    # Open position
                    if signal['signal'] in ['BUY', 'SELL'] and signal['confidence'] >= 60:
                        if symbol not in self.positions:
                            self.open_position(symbol, signal)
                    
                except Exception as e:
                    print(f"❌ {symbol}: {e}")
            
            print(f"⏳ Waiting {interval_minutes} min...")
            time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    bot = PaperTradingBotWithTelegram(initial_balance=10000)
    bot.run()
