import os
import time
import requests
from datetime import datetime
from ai_signal_bot_pro import AISignalBotPro

# Telegram Config from Environment Variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

def send_telegram(message):
    """Send message to Telegram"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Telegram not configured")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.json().get('ok'):
            print("✅ Telegram sent")
            return True
        return False
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

def calculate_tp_sl(signal_type, price):
    """Calculate TP/SL"""
    if signal_type == 'BUY':
        return price * 1.02, price * 1.04, price * 1.06, price * 0.98
    elif signal_type == 'SELL':
        return price * 0.98, price * 0.96, price * 0.94, price * 1.02
    return None, None, None, None

def main():
    """Simple bot that sends signals to Telegram"""
    bot = AISignalBotPro()
    symbols = os.getenv('SYMBOLS', 'BTC,ETH,SOL,BNB,XRP').split(',')
    interval = int(os.getenv('INTERVAL_MINUTES', '5')) * 60
    
    print("🤖 AI Signal Bot - Railway Deployment")
    print("="*50)
    print(f"📊 Symbols: {symbols}")
    print(f"⏰ Interval: {interval//60} minutes")
    print(f"📱 Telegram: {'✅' if TELEGRAM_TOKEN else '❌'}")
    
    # Send startup message
    if TELEGRAM_TOKEN and CHAT_ID:
        send_telegram(f"🤖 <b>AI Signal Bot Started on Railway</b>\n\n📊 Monitoring: {', '.join(symbols)}\n⏰ Every {interval//60} minutes\n✅ TP/SL Enabled")
    
    while True:
        print(f"\n🔍 {datetime.now().strftime('%H:%M:%S')} - Scanning...")
        
        for symbol in symbols:
            try:
                signal = bot.generate_signal(symbol.strip())
                if not signal:
                    continue
                
                print(f"{symbol}: {signal['signal']} ({signal['confidence']}%)")
                
                # Send only BUY/SELL with confidence >= 60
                if signal['signal'] in ['BUY', 'SELL'] and signal['confidence'] >= 60:
                    tp1, tp2, tp3, sl = calculate_tp_sl(signal['signal'], signal['price'])
                    
                    emoji = '🟢' if signal['signal'] == 'BUY' else '🔴'
                    conf_emoji = '🔥' if signal['confidence'] >= 80 else '⭐' if signal['confidence'] >= 70 else '⚡'
                    
                    reasons_text = '\n'.join([f"• {r}" for r in signal['reasons'][:5]])
                    
                    tp_sign = '+' if signal['signal'] == 'BUY' else ''
                    sl_sign = '-' if signal['signal'] == 'BUY' else '+'
                    
                    message = f"""{emoji} <b>{signal['signal']} SIGNAL</b> {emoji}

📊 <b>{signal['symbol']}</b> ({signal['timeframe']})
💰 Entry: <code>${signal['price']:,.2f}</code>
📈 24h: {signal['change_24h']:+.2f}%

🎯 <b>Analysis:</b>
• Confidence: {signal['confidence']}% {conf_emoji}
• ICT Score: {signal.get('ict_score', 0)}/6
• RSI: {signal['rsi']}
• SMA9: ${signal['sma']['sma9']:,.2f}
• SMA21: ${signal['sma']['sma21']:,.2f}

💡 <b>Reasons:</b>
{reasons_text}

🎯 <b>TARGETS:</b>
🥇 TP1: <code>${tp1:,.2f}</code> ({tp_sign}2%)
🥈 TP2: <code>${tp2:,.2f}</code> ({tp_sign}4%)
🥉 TP3: <code>${tp3:,.2f}</code> ({tp_sign}6%)

🛑 <b>STOP LOSS:</b>
⛔ SL: <code>${sl:,.2f}</code> ({sl_sign}2%)

📊 Risk/Reward: 1:3
⏰ {datetime.now().strftime('%H:%M:%S')}"""
                    
                    send_telegram(message)
                    time.sleep(2)  # Rate limit
                    
            except Exception as e:
                print(f"❌ Error with {symbol}: {e}")
                continue
        
        print(f"⏳ Waiting {interval//60} minutes...")
        time.sleep(interval)

if __name__ == "__main__":
    main()
