import os
import time
import requests
import json
from datetime import datetime
from ai_signal_bot_pro import AISignalBotPro

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
        self.default_leverage = default_leverage  # x5 leverage
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
        signal_type = signal_data['signal']  # BUY = Long, SELL = Short
        
        # Calculate TP/SL with leverage effect
        # TP: 2%, 4%, 6% | SL: -2%
        if signal_type == 'BUY':  # Long
            tp1 = price * 1.02
            tp2 = price * 1.04
            tp3 = price * 1.06
            sl = price * 0.98
        else:  # Short
            tp1 = price * 0.98
            tp2 = price * 0.96
            tp3 = price * 0.94
            sl = price * 1.02
        
        # Position size with leverage
        # With 5x leverage, $1000 position = $200 margin
        position_value = min(self.balance * 0.10, 1000)  # $1000 position
        margin_required = position_value / leverage  # $200 margin for 5x
        amount = position_value / price
        
        self.positions[symbol] = {
            'entry': price,
            'amount': amount,
            'type': signal_type,  # BUY/SELL (Long/Short)
            'leverage': leverage,
            'margin': margin_required,
            'position_value': position_value,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'sl': sl,
            'opened_at': datetime.now().isoformat()
        }
        
        self.balance -= margin_required  # Only deduct margin, not full position
        
        # Send Telegram
        emoji = '🟢' if signal_type == 'BUY' else '🔴'
        direction = 'LONG' if signal_type == 'BUY' else 'SHORT'
        
        message = f"""{emoji} <b>PAPER TRADE OPENED - {direction}</b> {emoji}

📊 <b>{symbol}</b> | {direction} x{leverage}
💰 Entry: <code>${price:,.2f}</code>
💵 Position Size: ${position_value:,.2f}
🔷 Margin Used: ${margin_required:,.2f}
⚡ Leverage: x{leverage}
📦 Amount: {amount:.4f} {symbol}

🎯 <b>Targets:</b>
🥇 TP1: ${tp1:,.2f}
🥈 TP2: ${tp2:,.2f}
🥉 TP3: ${tp3:,.2f}

🛑 SL: ${sl:,.2f}

💼 Available Balance: ${self.balance:,.2f}
⏰ {datetime.now().strftime('%H:%M:%S')}

<i>📝 Paper Trading with Leverage</i>"""
        
        self.send_telegram(message)
        print(f"🟢 OPENED {direction} {symbol} x{leverage} @ ${price:.2f}")
        
        self.save_state()
        return True
    
    def close_position(self, symbol, exit_price, reason):
        """إغلاق صفقة مع حساب Leverage"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        entry = pos['entry']
        amount = pos['amount']
        signal_type = pos['type']
        leverage = pos['leverage']
        margin = pos['margin']
        position_value = pos['position_value']
        
        # Calculate P&L with leverage
        # Price change % * leverage = actual P&L %
        if signal_type == 'BUY':  # Long
            price_change_pct = (exit_price - entry) / entry
        else:  # Short
            price_change_pct = (entry - exit_price) / entry
        
        # Apply leverage
        leveraged_change_pct = price_change_pct * leverage
        pnl = position_value * leveraged_change_pct
        
        # Update balance (return margin + P&L)
        self.balance += margin + pnl
        
        # Send Telegram
        emoji = '✅' if pnl > 0 else '❌'
        direction = 'LONG' if signal_type == 'BUY' else 'SHORT'
        
        message = f"""{emoji} <b>PAPER TRADE CLOSED - {direction}</b> {emoji}

📊 <b>{symbol}</b> | {direction} x{leverage}
🔔 Reason: {reason}

💰 Entry: <code>${entry:,.2f}</code>
💰 Exit: <code>${exit_price:,.2f}</code>

📊 Price Change: {price_change_pct*100:+.2f}%
⚡ With x{leverage} Leverage: {leveraged_change_pct*100:+.2f}%

📈 <b>P&L:</b>
💵 ${pnl:,.2f}

💰 Margin Returned: ${margin:,.2f}
💼 Balance: ${self.balance:,.2f}
📊 Total P&L: ${self.balance - self.initial_balance:+.2f}
⏰ {datetime.now().strftime('%H:%M:%S')}

<i>📝 Paper Trading with Leverage</i>"""
        
        self.send_telegram(message)
        print(f"{emoji} CLOSED {symbol} ({reason}) P&L: ${pnl:.2f}")
        
        del self.positions[symbol]
        self.save_state()
    
    def check_positions(self, symbol, current_price):
        """التحقق من TP/SL مع Leverage"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        signal_type = pos['type']
        leverage = pos['leverage']
        
        # Check SL first (more important with leverage!)
        if signal_type == 'BUY':  # Long
            if current_price <= pos['sl']:
                self.close_position(symbol, current_price, 'SL')
                return
            elif current_price >= pos['tp3']:
                self.close_position(symbol, current_price, 'TP3')
            elif current_price >= pos['tp2'] and not pos.get('tp2_hit'):
                pos['tp2_hit'] = True
                self.send_tp_hit_notification(symbol, 'TP2', current_price, pos)
            elif current_price >= pos['tp1'] and not pos.get('tp1_hit'):
                pos['tp1_hit'] = True
                self.send_tp_hit_notification(symbol, 'TP1', current_price, pos)
        
        else:  # Short
            if current_price >= pos['sl']:
                self.close_position(symbol, current_price, 'SL')
                return
            elif current_price <= pos['tp3']:
                self.close_position(symbol, current_price, 'TP3')
            elif current_price <= pos['tp2'] and not pos.get('tp2_hit'):
                pos['tp2_hit'] = True
                self.send_tp_hit_notification(symbol, 'TP2', current_price, pos)
            elif current_price <= pos['tp1'] and not pos.get('tp1_hit'):
                pos['tp1_hit'] = True
                self.send_tp_hit_notification(symbol, 'TP1', current_price, pos)
    
    def send_tp_hit_notification(self, symbol, tp_level, current_price, pos):
        """إرسال إشعار TP"""
        entry = pos['entry']
        signal_type = pos['type']
        leverage = pos['leverage']
        tp1, tp2, tp3, sl = pos['tp1'], pos['tp2'], pos['tp3'], pos['sl']
        
        direction = 'LONG' if signal_type == 'BUY' else 'SHORT'
        tp_emoji = '🥇' if tp_level == 'TP1' else '🥈'
        
        message = f"""{tp_emoji} <b>TARGET HIT - {tp_level} - {direction}</b> {tp_emoji}

📊 <b>{symbol}</b> | {direction} x{leverage}

💰 Entry: <code>${entry:,.2f}</code>
💰 Current: <code>${current_price:,.2f}</code>

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
        # Calculate stats - FIXED: use .get() to avoid KeyError
        closed_trades = [t for t in self.trade_history if t.get('type') == 'CLOSE']
        total_trades = len(closed_trades)
        winning_trades = len([t for t in closed_trades if t.get('pnl', 0) > 0])
        losing_trades = len([t for t in closed_trades if t.get('pnl', 0) <= 0])
        
        total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Current positions
        open_positions_text = ""
        if self.positions:
            for symbol, pos in self.positions.items():
                direction = 'LONG' if pos['type'] == 'BUY' else 'SHORT'
                open_positions_text += f"\n📊 {symbol} {direction} x{pos['leverage']} @ ${pos['entry']:.2f}"
        else:
            open_positions_text = "\n<i>لا صفقات مفتوحة</i>"
        
        message = f"""📊 <b>DAILY TRADING SUMMARY</b>

💰 <b>Account:</b>
• Balance: ${self.balance:,.2f}
• Total P&L: ${total_pnl:+.2f}
• Win Rate: {win_rate:.1f}%

📈 <b>Trades Today:</b>
• Total: {total_trades}
• Wins: {winning_trades} ✅
• Losses: {losing_trades} ❌

🔄 <b>Open Positions:{open_positions_text}</b>

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}

<i>📝 Paper Trading Summary</i>"""
        
        self.send_telegram(message)
        print(f"📊 Daily summary sent: {total_trades} trades")
    
    def run(self, symbols=None, interval_minutes=5):
        """تشغيل البوت"""
        if symbols is None:
            symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
        
        print("🤖 PAPER TRADING BOT WITH LEVERAGE")
        print(f"💰 Balance: ${self.balance:,.2f}")
        print(f"⚡ Default Leverage: x{self.default_leverage}")
        
        # Startup message
        self.send_telegram(f"""🤖 <b>Paper Trading Bot Started</b>

💰 Balance: ${self.balance:,.2f}
⚡ Leverage: x{self.default_leverage}
📊 Symbols: {', '.join(symbols)}
⏰ Interval: {interval_minutes} min

<i>📝 Long/Short with Leverage</i>""")
        
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
                    
                    direction = 'LONG' if signal['signal'] == 'BUY' else 'SHORT' if signal['signal'] == 'SELL' else 'HOLD'
                    print(f"{symbol}: {direction} ({signal['confidence']}%)")
                    
                    # Open position
                    if signal['signal'] in ['BUY', 'SELL'] and signal['confidence'] >= 60:
                        if symbol not in self.positions:
                            self.open_position(symbol, signal, leverage=self.default_leverage)
                    
                except Exception as e:
                    print(f"❌ {symbol}: {e}")
            
            print(f"⏳ Waiting {interval_minutes} min...")
            time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    # Create bot with $10,000 and x5 leverage
    bot = PaperTradingBotWithLeverage(initial_balance=10000, default_leverage=5)
    bot.run()
