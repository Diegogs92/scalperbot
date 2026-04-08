"""
Dashboard Web para el Scalping Bot
===================================
Interfaz web en tiempo real para monitorear el bot de trading.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO, emit
from strategy import ScalpingStrategy, Signal
from dotenv import load_dotenv
import threading
import asyncio

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Estado global del bot
bot_state = {
    'running': False,
    'connected': False,
    'testnet': True,
    'current_position': None,
    'entry_price': 0,
    'account_balance': 0,
    'daily_pnl': 0,
    'price': 0,
    'rsi': 0,
    'ema_fast': 0,
    'ema_slow': 0,
    'volume_ratio': 0,
    'last_signal': 'HOLD',
    'last_update': None,
}

# Historial de trades
trades_history = []

# Historial de precios para gráfico
price_history = []
MAX_HISTORY_POINTS = 100


@app.route('/')
def index():
    """Página principal del dashboard."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/status')
def get_status():
    """API endpoint para obtener estado actual."""
    return jsonify(bot_state)


@app.route('/api/trades')
def get_trades():
    """API endpoint para obtener historial de trades."""
    return jsonify(trades_history)


@app.route('/api/prices')
def get_prices():
    """API endpoint para obtener historial de precios."""
    return jsonify(price_history)


@socketio.on('connect')
def handle_connect():
    """Cliente conectado."""
    logger.info("Cliente conectado al dashboard")
    emit('initial_state', bot_state)


@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectado."""
    logger.info("Cliente desconectado del dashboard")


def update_state(data: dict):
    """
    Actualizar el estado del bot desde el trading bot.

    Args:
        data: Diccionario con los nuevos valores de estado
    """
    global bot_state, price_history

    for key, value in data.items():
        if key in bot_state:
            bot_state[key] = value

    bot_state['last_update'] = datetime.now().isoformat()

    # Actualizar historial de precios
    if 'price' in data and data['price'] > 0:
        price_history.append({
            'time': bot_state['last_update'],
            'price': data['price']
        })
        # Mantener solo últimos N puntos
        if len(price_history) > MAX_HISTORY_POINTS:
            price_history = price_history[-MAX_HISTORY_POINTS:]

    # Emitir actualización a todos los clientes conectados
    socketio.emit('state_update', data)


def add_trade(trade: dict):
    """Agregar trade al historial y notificar."""
    global trades_history
    trades_history.append(trade)
    socketio.emit('new_trade', trade)


# Template HTML del dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bitcoin Scalping Bot - Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }

        header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #f39c12, #e74c3c);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .status-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }

        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }

        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .status-dot.online {
            background: #2ecc71;
        }

        .status-dot.offline {
            background: #e74c3c;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }

        .card h3 {
            color: #f39c12;
            margin-bottom: 15px;
            font-size: 1.1em;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        .metric:last-child {
            border-bottom: none;
        }

        .metric-label {
            color: #aaa;
        }

        .metric-value {
            font-weight: bold;
            font-size: 1.2em;
        }

        .metric-value.positive {
            color: #2ecc71;
        }

        .metric-value.negative {
            color: #e74c3c;
        }

        .position-card {
            background: linear-gradient(135deg, rgba(243,156,18,0.1) 0%, rgba(231,76,60,0.1) 100%);
            border: 2px solid #f39c12;
        }

        .position-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
        }

        .position-badge.long {
            background: rgba(46,204,113,0.2);
            color: #2ecc71;
        }

        .position-badge.short {
            background: rgba(231,76,60,0.2);
            color: #e74c3c;
        }

        .position-badge.none {
            background: rgba(150,150,150,0.2);
            color: #999;
        }

        #price-chart {
            width: 100%;
            height: 400px;
        }

        .trades-table {
            width: 100%;
            border-collapse: collapse;
        }

        .trades-table th,
        .trades-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        .trades-table th {
            color: #f39c12;
            font-weight: 600;
        }

        .trades-table tr:hover {
            background: rgba(255,255,255,0.05);
        }

        .pnl-positive {
            color: #2ecc71;
        }

        .pnl-negative {
            color: #e74c3c;
        }

        .last-update {
            text-align: center;
            color: #666;
            margin-top: 20px;
            font-size: 0.9em;
        }

        .signal-badge {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 25px;
            font-weight: bold;
            text-transform: uppercase;
        }

        .signal-badge.buy {
            background: rgba(46,204,113,0.2);
            color: #2ecc71;
        }

        .signal-badge.sell {
            background: rgba(231,76,60,0.2);
            color: #e74c3c;
        }

        .signal-badge.hold {
            background: rgba(150,150,150,0.2);
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>₿ Bitcoin Scalping Bot</h1>
            <div class="status-bar">
                <div class="status-item">
                    <div class="status-dot" id="connection-status"></div>
                    <span id="connection-text">Conectando...</span>
                </div>
                <div class="status-item">
                    <span>🌐</span>
                    <span id="mode-badge">TESTNET</span>
                </div>
                <div class="status-item">
                    <span>📊</span>
                    <span id="symbol-display">BTCUSDT</span>
                </div>
            </div>
        </header>

        <div class="grid">
            <div class="card position-card">
                <h3>📍 Posición Actual</h3>
                <div class="metric">
                    <span class="metric-label">Estado</span>
                    <span class="position-badge none" id="position-status">SIN POSICIÓN</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Precio de Entrada</span>
                    <span id="entry-price">$0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">PnL No Realizado</span>
                    <span id="unrealized-pnl" class="metric-value">$0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">PnL Diario</span>
                    <span id="daily-pnl" class="metric-value">$0.00</span>
                </div>
            </div>

            <div class="card">
                <h3>💰 Cuenta</h3>
                <div class="metric">
                    <span class="metric-label">Balance</span>
                    <span id="account-balance" class="metric-value">$0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Última Señal</span>
                    <span class="signal-badge hold" id="last-signal">HOLD</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Actualizado</span>
                    <span id="last-update">--:--:--</span>
                </div>
            </div>

            <div class="card">
                <h3>📈 Indicadores</h3>
                <div class="metric">
                    <span class="metric-label">Precio BTC</span>
                    <span id="current-price" class="metric-value">$0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">RSI (14)</span>
                    <span id="rsi-value">0.0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">EMA Fast (9)</span>
                    <span id="ema-fast">0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">EMA Slow (21)</span>
                    <span id="ema-slow">0.00</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Volume Ratio</span>
                    <span id="volume-ratio">0.00x</span>
                </div>
            </div>
        </div>

        <div class="card" style="margin-bottom: 30px;">
            <h3>📊 Precio en Tiempo Real</h3>
            <div id="price-chart"></div>
        </div>

        <div class="card">
            <h3>📜 Historial de Trades</h3>
            <table class="trades-table">
                <thead>
                    <tr>
                        <th>Hora</th>
                        <th>Lado</th>
                        <th>Precio</th>
                        <th>Cantidad</th>
                        <th>PnL</th>
                        <th>Razón</th>
                    </tr>
                </thead>
                <tbody id="trades-body">
                    <tr>
                        <td colspan="6" style="text-align: center; color: #666;">Sin trades registrados</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <p class="last-update" id="last-update-footer"></p>
    </div>

    <script>
        // Conectar al servidor Socket.IO
        const socket = io();

        // Elementos del DOM
        const elements = {
            connectionStatus: document.getElementById('connection-status'),
            connectionText: document.getElementById('connection-text'),
            modeBadge: document.getElementById('mode-badge'),
            positionStatus: document.getElementById('position-status'),
            entryPrice: document.getElementById('entry-price'),
            unrealizedPnl: document.getElementById('unrealized-pnl'),
            dailyPnl: document.getElementById('daily-pnl'),
            accountBalance: document.getElementById('account-balance'),
            lastSignal: document.getElementById('last-signal'),
            lastUpdate: document.getElementById('last-update'),
            currentPrice: document.getElementById('current-price'),
            rsiValue: document.getElementById('rsi-value'),
            emaFast: document.getElementById('ema-fast'),
            emaSlow: document.getElementById('ema-slow'),
            volumeRatio: document.getElementById('volume-ratio'),
            tradesBody: document.getElementById('trades-body'),
        };

        // Manejar estado inicial
        socket.on('initial_state', (state) => {
            updateUI(state);
        });

        // Manejar actualizaciones en tiempo real
        socket.on('state_update', (data) => {
            updateUI(data);
        });

        // Manejar nuevo trade
        socket.on('new_trade', (trade) => {
            addTradeToTable(trade);
        });

        // Conectado
        socket.on('connect', () => {
            elements.connectionStatus.className = 'status-dot online';
            elements.connectionText.textContent = 'Conectado';
        });

        // Desconectado
        socket.on('disconnect', () => {
            elements.connectionStatus.className = 'status-dot offline';
            elements.connectionText.textContent = 'Desconectado';
        });

        // Actualizar UI
        function updateUI(data) {
            if (data.testnet !== undefined) {
                elements.modeBadge.textContent = data.testnet ? 'TESTNET' : 'MAINNET';
            }

            if (data.current_position !== undefined) {
                const pos = data.current_position || 'NONE';
                elements.positionStatus.textContent = pos;
                elements.positionStatus.className = 'position-badge ' + pos.toLowerCase();
            }

            if (data.entry_price !== undefined && data.entry_price > 0) {
                elements.entryPrice.textContent = '$' + data.entry_price.toLocaleString('en-US', {minimumFractionDigits: 2});
            }

            if (data.daily_pnl !== undefined) {
                elements.dailyPnl.textContent = '$' + data.daily_pnl.toLocaleString('en-US', {minimumFractionDigits: 2});
                elements.dailyPnl.className = 'metric-value ' + (data.daily_pnl >= 0 ? 'positive' : 'negative');
            }

            if (data.account_balance !== undefined) {
                elements.accountBalance.textContent = '$' + data.account_balance.toLocaleString('en-US', {minimumFractionDigits: 2});
            }

            if (data.last_signal !== undefined) {
                elements.lastSignal.textContent = data.last_signal;
                elements.lastSignal.className = 'signal-badge ' + data.last_signal.toLowerCase();
            }

            if (data.last_update !== undefined) {
                const time = new Date(data.last_update).toLocaleTimeString();
                elements.lastUpdate.textContent = time;
                document.getElementById('last-update-footer').textContent = 'Última actualización: ' + time;
            }

            if (data.price !== undefined && data.price > 0) {
                elements.currentPrice.textContent = '$' + data.price.toLocaleString('en-US', {minimumFractionDigits: 2});
                updateChart(data.price);
            }

            if (data.rsi !== undefined) {
                elements.rsiValue.textContent = data.rsi.toFixed(1);
            }

            if (data.ema_fast !== undefined) {
                elements.emaFast.textContent = data.ema_fast.toFixed(2);
            }

            if (data.ema_slow !== undefined) {
                elements.emaSlow.textContent = data.ema_slow.toFixed(2);
            }

            if (data.volume_ratio !== undefined) {
                elements.volumeRatio.textContent = data.volume_ratio.toFixed(2) + 'x';
            }
        }

        // Agregar trade a la tabla
        function addTradeToTable(trade) {
            const tbody = elements.tradesBody;
            const firstRow = tbody.querySelector('tr');
            if (firstRow && firstRow.cells.length === 1) {
                tbody.innerHTML = '';
            }

            const row = document.createElement('tr');
            const time = new Date(trade.time).toLocaleTimeString();
            const pnlClass = trade.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
            const pnlSign = trade.pnl >= 0 ? '+' : '';

            row.innerHTML = `
                <td>${time}</td>
                <td><span class="position-badge ${trade.side.toLowerCase()}">${trade.side}</span></td>
                <td>$${trade.price.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                <td>${trade.quantity.toFixed(6)} BTC</td>
                <td class="${pnlClass}">${pnlSign}$${trade.pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                <td>${trade.reason}</td>
            `;

            tbody.insertBefore(row, tbody.firstChild);
        }

        // Gráfico de precios
        let priceData = [];
        let chartInitialized = false;

        function updateChart(price) {
            const now = new Date();
            priceData.push({
                x: now,
                y: price
            });

            // Mantener últimos 100 puntos
            if (priceData.length > 100) {
                priceData.shift();
            }

            if (!chartInitialized) {
                Plotly.newPlot('price-chart', [{
                    x: priceData.map(p => p.x),
                    y: priceData.map(p => p.y),
                    type: 'scatter',
                    mode: 'lines',
                    line: {
                        color: '#f39c12',
                        width: 2
                    },
                    fill: 'tozeroy',
                    fillcolor: 'rgba(243,156,18,0.1)'
                }], {
                    margin: { t: 20, r: 20, l: 60, b: 40 },
                    xaxis: {
                        title: 'Hora',
                        type: 'date',
                        gridcolor: '#333'
                    },
                    yaxis: {
                        title: 'Precio (USDT)',
                        gridcolor: '#333'
                    },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)'
                }, {
                    responsive: true,
                    displayModeBar: false
                });
                chartInitialized = true;
            } else {
                Plotly.extendTraces('price-chart', {
                    x: [[now]],
                    y: [[price]]
                }, [0]);
            }
        }

        // Cargar datos iniciales
        fetch('/api/status')
            .then(r => r.json())
            .then(data => updateUI(data));

        fetch('/api/trades')
            .then(r => r.json())
            .then(trades => {
                trades.forEach(addTradeToTable);
            });
    </script>
</body>
</html>
"""


def run_dashboard(host='0.0.0.0', port=None, debug=False):
    """
    Ejecutar el dashboard web.

    Args:
        host: Host para escuchar
        port: Puerto para escuchar
        debug: Modo debug de Flask
    """
    if port is None:
        port = int(os.getenv('PORT', 5000))
        
    logger.info(f"Iniciando dashboard web en http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


def run_in_background():
    """Ejecutar dashboard en thread separado."""
    thread = threading.Thread(
        target=run_dashboard,
        kwargs={'debug': False},
        daemon=True
    )
    thread.start()
    logger.info("Dashboard ejecutándose en background")
    return thread


if __name__ == '__main__':
    run_dashboard(debug=True)
