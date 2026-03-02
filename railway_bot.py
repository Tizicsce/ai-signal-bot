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
                self.send_tp_hit_notification(symbol, 'TP2', current_price, pos)
            elif current_price >= pos['tp1'] and not pos.get('tp1_hit'):
                pos['tp1_hit'] = True
                self.send_tp_hit_notification(symbol, 'TP1', current_price, pos)
        else:  # SELL
            if current_price >= pos['sl']:
                self.close_position(symbol, current_price, 'SL')
            elif current_price <= pos['tp3']:
                self.close_position(symbol, current_price, 'TP3')
            elif current_price <= pos['tp2'] and not pos.get('tp2_hit'):
                pos['tp2_hit'] = True
                self.send_tp_hit_notification(symbol, 'TP2', current_price, pos)
            elif current_price <= pos['tp1'] and not pos.get('tp1_hit'):
                pos['tp1_hit'] = True
                self.send_tp_hit_notification(symbol, 'TP1', current_price, pos)
    
    def send_tp_hit_notification(self, symbol, tp_level, current_price, pos):
        """إرسال إشعار عند الوصول لـ TP"""
        entry = pos['entry']
        signal_type = pos['type']
        tp1 = pos['tp1']
        tp2 = pos['tp2']
        tp3 = pos['tp3']
        sl = pos['sl']
        
        # Calculate P&L so far
        amount = pos['amount']
        if signal_type == 'BUY':
            pnl = (current_price - entry) * amount
        else:
            pnl = (entry - current_price) * amount
        pnl_percent = (pnl / (entry * amount)) * 100
        
        tp_emoji = '🥇' if tp_level == 'TP1' else '🥈'
        
        message = f"""{tp_emoji} <b>TARGET HIT - {tp_level}</b> {tp_emoji}

📊 <b>{symbol}</b> | {signal_type}

💰 Entry: <code>${entry:,.2f}</code>
💰 Current: <code>${current_price:,.2f}</code>

📈 <b>P&L so far:</b>
💵 ${pnl:,.2f} ({pnl_percent:+.2f}%)

🎯 <b>Progress:</b>
🥇 TP1: ${tp1:,.2f} {'✅' if tp_level in ['TP1', 'TP2', 'TP3'] else '⏳'}
🥈 TP2: ${tp2:,.2f} {'✅' if tp_level in ['TP2', 'TP3'] else '⏳'}
🥉 TP3: ${tp3:,.2f} {'✅' if tp_level == 'TP3' else '⏳'}
🛑 SL: ${sl:,.2f}

<i>📝 Waiting for next target...</i>"""
        
        self.send_telegram(message)
        print(f"🎯 {tp_level} hit: {symbol} @ ${current_price:.2f}")
        self.save_state()
    
    def send_daily_summary(self):
        """إرسال ملخص يومي"""
        # Calculate stats
        total_trades = len([t for t in self.trade_history if t['type'] == 'CLOSE'])
        winning_trades = len([t for t in self.trade_history if t['type'] == 'CLOSE' and t['pnl'] > 0])
        losing_trades = len([t for t in self.trade_history if t['type'] == 'CLOSE' and t['pnl'] <= 0])
        
        total_pnl = sum(t['pnl'] for t in self.trade_history if t['type'] == 'CLOSE')
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Current positions
        open_positions_text = ""
        if self.positions:
            for symbol, pos in self.positions.items():
                open_positions_text += f"\n📊 {symbol} {pos['type']} @ ${pos['entry']:.2f}"
        else:
            open_positions_text = "\n<i>لا صفقات مفتوحة</i>"
        
        message = f"""📊 <b>DAILY TRADING SUMMARY</b>

💰 <b>Account:</b>
• Balance: ${self.balance:,.2f}
• Total P&L: ${total_pnl:+.2f}
• Win Rate: {win_rate:.1f}%

📈 <b>Trades:</b>
• Total: {total_trades}
• Wins: {winning_trades} ✅
• Losses: {losing_trades} ❌

🔄 <b>Open Positions:{open_positions_text}</b>

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}

<i>📝 Paper Trading Summary</i>"""
        
        self.send_telegram(message)
        print("📊 Daily summary sent")
    
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
        
        last_summary_day = datetime.now().day
        
        while True:
            current_time = datetime.now()
            print(f"\n🔍 {current_time.strftime('%H:%M:%S')}")
            
            # Send daily summary at midnight
            if current_time.day != last_summary_day:
                self.send_daily_summary()
                last_summary_day = current_time.day
            
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
