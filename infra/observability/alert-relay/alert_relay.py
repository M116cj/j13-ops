"""Alertmanager webhook relay → Telegram Thread 354 (Alerts)."""
import os, json, requests, logging
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('alert-relay')

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '-1003601437444')
THREAD_ID = os.environ.get('TELEGRAM_THREAD_ID', '354')  # Alerts thread

SEVERITY_EMOJI = {'critical': '🔴', 'warning': '🟡', 'info': '🔵', 'none': '✅'}

def send_telegram(text):
    if not BOT_TOKEN:
        log.warning('TELEGRAM_BOT_TOKEN not set')
        return
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'message_thread_id': int(THREAD_ID),
        'text': text,
        'parse_mode': 'HTML',
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            log.warning(f'Telegram API error: {r.status_code} {r.text[:200]}')
    except Exception as e:
        log.error(f'Telegram send failed: {e}')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/alert', methods=['POST'])
def receive_alert():
    try:
        data = request.get_json(force=True, silent=True) or {}
        alerts = data.get('alerts', [])
        if not alerts:
            return jsonify({'status': 'no alerts'}), 200

        for alert in alerts:
            status   = alert.get('status', 'unknown')
            labels   = alert.get('labels', {})
            ann      = alert.get('annotations', {})
            name     = labels.get('alertname', 'Unknown')
            severity = labels.get('severity', 'none')
            summary  = ann.get('summary', 'No summary')
            description = ann.get('description', '')

            emoji = SEVERITY_EMOJI.get(severity, '⚠️')
            if status == 'resolved':
                emoji = '✅'
                text = f'{emoji} <b>RESOLVED: {name}</b>\n{summary}'
            else:
                text = f'{emoji} <b>ALERT: {name}</b> [{severity}]\n{summary}'
                if description:
                    text += f'\n<i>{description[:300]}</i>'

            send_telegram(text)
            log.info(f'Relayed alert: {name} [{severity}] {status}')

        return jsonify({'status': 'ok', 'count': len(alerts)}), 200
    except Exception as e:
        log.error(f'Alert processing error: {e}')
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9087)
