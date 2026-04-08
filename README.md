# Bitcoin Scalping Bot

Bot de scalping para Bitcoin en Binance Futures con estrategia basada en indicadores técnicos, dashboard web en tiempo real y notificaciones por Telegram.

## Características

- ✅ **Trading en vivo** en Binance Futures (testnet y mainnet)
- ✅ **Dashboard web** en tiempo real con gráficos y métricas
- ✅ **Notificaciones por Telegram** de operaciones y señales
- ✅ **Backtesting** con datos históricos
- ✅ **Optimizador de parámetros** con walk-forward analysis
- ✅ **Gestión de riesgo** con stop loss y take profit dinámicos

## Estrategia

La estrategia utiliza una combinación de indicadores para generar señales de trading:

### Indicadores
- **EMA Crossover**: EMA rápida (9) vs EMA lenta (21)
- **RSI**: Sobrecompra (>70) / Sobreventa (<30)
- **Bandas de Bollinger**: Detección de extremos de volatilidad
- **Volumen**: Confirmación de movimientos (ratio > 1.5)
- **ATR**: Stop loss dinámico basado en volatilidad

### Señales de Entrada

**LONG:**
- EMA rápida cruza por encima de EMA lenta
- RSI < 70 (no sobrecomprado)
- Precio toca o está cerca de banda inferior de Bollinger
- Volumen por encima del promedio

**SHORT:**
- EMA rápida cruza por debajo de EMA lenta
- RSI > 30 (no sobrevendido)
- Precio toca o está cerca de banda superior de Bollinger
- Volumen por encima del promedio

### Gestión de Riesgo

- Stop Loss: 1.5 x ATR
- Take Profit: 3.0 x ATR (ratio 2:1)
- Máxima posición: 0.001 BTC (configurable)
- Límite de pérdida diaria: $100 (configurable)

## Instalación

1. Clonar o descargar los archivos

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Configurar variables de entorno:
```bash
cp .env.example .env
```

4. Editar `.env` con tus credenciales de Binance:
```
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_api_secret
TESTNET=true
```

## Uso

### Trading en Vivo (con dashboard y Telegram)
```bash
python trading_bot.py
```

El dashboard web estará disponible en `http://localhost:5000`

### Solo Dashboard
```bash
python dashboard.py
```

### Backtest
```bash
python backtest.py
```

### Optimizar Parámetros
```bash
python optimizer.py
```

## Configuración (.env)

| Variable | Descripción | Default |
|----------|-------------|---------|
| `BINANCE_API_KEY` | API Key de Binance | - |
| `BINANCE_API_SECRET` | API Secret de Binance | - |
| `TESTNET` | Usar testnet (true/false) | true |
| `SYMBOL` | Par de trading | BTCUSDT |
| `TIMEFRAME` | Temporalidad | 1m |
| `MAX_POSITION_SIZE` | Máxima posición en BTC | 0.001 |
| `MAX_DAILY_LOSS` | Pérdida diaria máxima ($) | 100 |
| `RSI_PERIOD` | Período RSI | 14 |
| `RSI_OVERBOUGHT` | Nivel sobrecompra RSI | 70 |
| `RSI_OVERSOLD` | Nivel sobreventa RSI | 30 |
| `EMA_FAST` | EMA rápida | 9 |
| `EMA_SLOW` | EMA lenta | 21 |
| `VOLUME_THRESHOLD` | Mínimo ratio volumen | 1.5 |
| `TELEGRAM_BOT_TOKEN` | Token de bot Telegram | - |
| `TELEGRAM_CHAT_ID` | Chat ID de Telegram | - |
| `DASHBOARD_PORT` | Puerto del dashboard | 5000 |

## Configuración de Telegram

1. Crea un bot con [@BotFather](https://t.me/botfather):
   - Envía `/newbot`
   - Sigue las instrucciones
   - Copia el token

2. Obtén tu Chat ID:
   - Envía un mensaje a [@userinfobot](https://t.me/userinfobot)
   - Copia tu ID

3. Agrega en `.env`:
```
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

## Crear API Key en Binance

1. Ir a https://www.binance.com > Profile > API Management
2. Crear nueva API Key
3. Habilitar **Futures Trading**
4. Restringir IP (recomendado)
5. Copiar Key y Secret en `.env`

### Testnet vs Mainnet

- **Testnet**: Dinero ficticio, ideal para pruebas
  - URL: https://testnet.binancefuture.com
  - Configura `TESTNET=true`
  
- **Mainnet**: Dinero real
  - Configura `TESTNET=false`
  - ⚠️ Usar solo después de probar exhaustivamente

## Dashboard Web

El dashboard incluye:

- 📊 **Estado en tiempo real** del bot
- 📈 **Gráfico de precios** actualizado
- 💰 **Balance y PnL** diario
- 📍 **Posición actual** con entrada y PnL no realizado
- 📉 **Indicadores técnicos** (RSI, EMAs, Volumen)
- 📜 **Historial de trades** ejecutados

Accede en: `http://localhost:5000`

## Estructura

```
scalper/
├── strategy.py         # Lógica de la estrategia
├── trading_bot.py      # Bot de trading en vivo
├── backtest.py         # Módulo de backtesting
├── optimizer.py        # Optimizador de parámetros
├── dashboard.py        # Dashboard web en tiempo real
├── notifications.py    # Notificaciones por Telegram
├── requirements.txt    # Dependencias
├── .env.example        # Ejemplo de configuración
└── README.md           # Este archivo
```

## Advertencias

⚠️ **Riesgo**: El trading de criptomonedas conlleva alto riesgo. Usa solo dinero que puedas permitirte perder.

⚠️ **Backtest ≠ Resultados Reales**: Los resultados históricos no garantizan ganancias futuras. El slippage, fees y latencia afectan los resultados reales.

⚠️ **Paper Trading**: Prueba primero en testnet de Binance Futures antes de usar dinero real.

⚠️ **Ninguna estrategia es infalible**: Este bot puede generar pérdidas. Monitorea constantemente y ajusta parámetros según condiciones de mercado.

## Licencia

MIT
