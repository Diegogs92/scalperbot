"""
Bitcoin Scalping Trading Bot
============================
Bot de trading que ejecuta la estrategia de scalping en Binance.
"""

import asyncio
import os
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from binance import AsyncClient
from strategy import ScalpingStrategy, Signal
from notifications import notifier
from dashboard import update_state, add_trade, run_in_background

# URLs de Binance
BINANCE_URLS = {
    'testnet': 'https://testnet.binancefuture.com',
    'mainnet': 'https://fapi.binance.com'
}

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TradingBot:
    """
    Bot de trading para ejecutar órdenes de scalping en Binance.
    """

    def __init__(self):
        load_dotenv()

        # Credenciales
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Faltan credenciales de Binance. Configura .env file."
            )

        # Configuración
        self.symbol = os.getenv('SYMBOL', 'BTCUSDT')
        self.timeframe = os.getenv('TIMEFRAME', '1m')
        self.max_position_size = float(os.getenv('MAX_POSITION_SIZE', 0.001))
        self.stop_loss_pct = float(os.getenv('STOP_LOSS_PCT', 0.5))
        self.take_profit_pct = float(os.getenv('TAKE_PROFIT_PCT', 1.0))

        # Estado
        self.client: Optional[AsyncClient] = None
        self.current_position: Optional[str] = None
        self.entry_price: float = 0
        self.account_balance: float = 0
        self.daily_pnl: float = 0
        self.running = False
        self.testnet = os.getenv('TESTNET', 'true').lower() == 'true'

        # Inicializar estrategia
        config = {
            'rsi_period': int(os.getenv('RSI_PERIOD', 14)),
            'rsi_overbought': int(os.getenv('RSI_OVERBOUGHT', 70)),
            'rsi_oversold': int(os.getenv('RSI_OVERSOLD', 30)),
            'ema_fast': int(os.getenv('EMA_FAST', 9)),
            'ema_slow': int(os.getenv('EMA_SLOW', 21)),
            'volume_threshold': float(os.getenv('VOLUME_THRESHOLD', 1.5)),
            'max_position_size': self.max_position_size,
        }
        self.strategy = ScalpingStrategy(config)

    async def connect(self):
        """Conectar a Binance API."""
        # Usar testnet si está configurado
        base_url = BINANCE_URLS['testnet'] if self.testnet else BINANCE_URLS['mainnet']

        self.client = await AsyncClient.create(
            self.api_key,
            self.api_secret,
            testnet=self.testnet
        )

        mode = "TESTNET (Papel Trading)" if self.testnet else "MAINNET (Dinero Real)"
        logger.info(f"Conectado a Binance API - {mode}")

        if self.testnet:
            logger.warning("⚠️ USANDO TESTNET - Las órdenes son simuladas")

        # Notificar inicio a Telegram
        await notifier.notify_startup(self.testnet)

    async def disconnect(self):
        """Desconectar de Binance API."""
        if self.client:
            await self.client.close_connection()
            logger.info("Desconectado de Binance API")

    async def get_klines(self, limit: int = 50) -> list:
        """Obtener velas del mercado."""
        klines = await self.client.futures_klines(
            symbol=self.symbol,
            interval=self.timeframe,
            limit=limit
        )

        return [{
            'timestamp': k[0],
            'open': float(k[1]),
            'high': float(k[2]),
            'low': float(k[3]),
            'close': float(k[4]),
            'volume': float(k[5]),
        } for k in klines]

    async def get_account_balance(self) -> float:
        """Obtener balance de la cuenta."""
        account = await self.client.futures_account()
        # Balance disponible en USDT
        for asset in account['assets']:
            if asset['asset'] == 'USDT':
                return float(asset['availableBalance'])
        return 0

    async def get_current_position(self) -> Optional[dict]:
        """Obtener posición actual."""
        positions = await self.client.futures_position_information(
            symbol=self.symbol
        )

        for pos in positions:
            if pos['symbol'] == self.symbol:
                position_amt = float(pos['positionAmt'])
                if position_amt != 0:
                    return {
                        'side': 'LONG' if position_amt > 0 else 'SHORT',
                        'size': abs(position_amt),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit']),
                    }
        return None

    async def place_market_order(
        self,
        side: str,
        quantity: float
    ) -> dict:
        """
        Colocar orden de mercado.

        Args:
            side: 'BUY' o 'SELL'
            quantity: Cantidad en BTC
        """
        order = await self.client.futures_create_order(
            symbol=self.symbol,
            type='MARKET',
            side=side,
            quantity=quantity
        )

        logger.info(
            f"Orden {side} ejecutada: {quantity} BTC @ "
            f"{order['avgPrice'] or order['price']}"
        )

        return order

    async def place_stop_loss_order(
        self,
        side: str,
        quantity: float,
        stop_price: float
    ):
        """Colocar orden de stop loss."""
        await self.client.futures_create_order(
            symbol=self.symbol,
            type='STOP_MARKET',
            side=side,
            quantity=quantity,
            stopPrice=stop_price,
            timeInForce='GTC'
        )
        logger.info(f"Stop Loss colocado @ {stop_price}")

    async def execute_trade(self, signal: Signal, info: dict):
        """Ejecutar operación basada en la señal."""
        price = info['price']
        atr = info.get('atr', 0)

        # Verificar límite de pérdida diaria
        if self.daily_pnl <= -float(os.getenv('MAX_DAILY_LOSS', 100)):
            logger.warning(
                f"Límite de pérdida diaria alcanzado: ${self.daily_pnl}"
            )
            return

        if signal == Signal.BUY and not self.current_position:
            # Abrir LONG
            quantity = self.strategy.calculate_position_size(
                price, self.account_balance, atr
            )

            if quantity > 0:
                await self.place_market_order('BUY', quantity)
                self.current_position = 'LONG'
                self.entry_price = price

                # Calcular y colocar stop loss / take profit
                sl, tp = self.strategy.get_stop_loss_take_profit(
                    price, atr, 'LONG'
                )
                logger.info(f"LONG: Entry={price}, SL={sl}, TP={tp}")

                # Notificar a Telegram
                await notifier.notify_order(
                    'OPEN', 'LONG', self.symbol, price, quantity,
                    reason='Señal de compra detectada'
                )

        elif signal == Signal.SELL and not self.current_position:
            # Abrir SHORT
            quantity = self.strategy.calculate_position_size(
                price, self.account_balance, atr
            )

            if quantity > 0:
                await self.place_market_order('SELL', quantity)
                self.current_position = 'SHORT'
                self.entry_price = price

                sl, tp = self.strategy.get_stop_loss_take_profit(
                    price, atr, 'SHORT'
                )
                logger.info(f"SHORT: Entry={price}, SL={sl}, TP={tp}")

                # Notificar a Telegram
                await notifier.notify_order(
                    'OPEN', 'SHORT', self.symbol, price, quantity,
                    reason='Señal de venta detectada'
                )

        elif signal == Signal.SELL and self.current_position == 'LONG':
            # Cerrar LONG
            position = await self.get_current_position()
            if position:
                await self.place_market_order('SELL', position['size'])
                pnl = position['unrealized_pnl']
                self.daily_pnl += pnl
                logger.info(
                    f"LONG cerrado: PnL=${pnl:.2f} | "
                    f"Daily PnL=${self.daily_pnl:.2f}"
                )

                # Notificar a Telegram
                await notifier.notify_order(
                    'CLOSE', 'LONG', self.symbol, price, position['size'],
                    pnl=pnl, reason=info.get('reason', 'Señal de salida')
                )

                # Agregar al historial del dashboard
                add_trade({
                    'time': datetime.now().isoformat(),
                    'side': 'LONG',
                    'price': price,
                    'quantity': position['size'],
                    'pnl': pnl,
                    'reason': info.get('reason', 'Señal de salida')
                })

                self.current_position = None
                self.entry_price = 0

        elif signal == Signal.BUY and self.current_position == 'SHORT':
            # Cerrar SHORT
            position = await self.get_current_position()
            if position:
                await self.place_market_order('BUY', position['size'])
                pnl = position['unrealized_pnl']
                self.daily_pnl += pnl
                logger.info(
                    f"SHORT cerrado: PnL=${pnl:.2f} | "
                    f"Daily PnL=${self.daily_pnl:.2f}"
                )

                # Notificar a Telegram
                await notifier.notify_order(
                    'CLOSE', 'SHORT', self.symbol, price, position['size'],
                    pnl=pnl, reason=info.get('reason', 'Señal de salida')
                )

                # Agregar al historial del dashboard
                add_trade({
                    'time': datetime.now().isoformat(),
                    'side': 'SHORT',
                    'price': price,
                    'quantity': position['size'],
                    'pnl': pnl,
                    'reason': info.get('reason', 'Señal de salida')
                })

                self.current_position = None
                self.entry_price = 0

    async def run(self):
        """Ejecutar el bot de trading."""
        self.running = True
        logger.info("Iniciando Bitcoin Scalping Bot...")

        # Iniciar dashboard en background
        run_in_background()
        await asyncio.sleep(2)  # Esperar que el dashboard inicie

        while self.running:
            try:
                # Actualizar balance
                self.account_balance = await self.get_account_balance()

                # Obtener datos del mercado
                klines = await self.get_klines()

                # Convertir a DataFrame
                import pandas as pd
                df = pd.DataFrame(klines)

                # Analizar y obtener señal
                signal, info = self.strategy.analyze(
                    df,
                    self.current_position
                )

                # Actualizar estado del dashboard
                update_state({
                    'price': info.get('price', 0),
                    'rsi': info.get('rsi', 0),
                    'ema_fast': info.get('ema_fast', 0),
                    'ema_slow': info.get('ema_slow', 0),
                    'volume_ratio': info.get('volume_ratio', 0),
                    'current_position': self.current_position,
                    'entry_price': self.entry_price,
                    'account_balance': self.account_balance,
                    'daily_pnl': self.daily_pnl,
                    'last_signal': signal.value,
                    'testnet': self.testnet,
                })

                # Log de información relevante
                logger.info(
                    f"Price: ${info['price']:.2f} | "
                    f"RSI: {info['rsi']:.1f} | "
                    f"Vol Ratio: {info['volume_ratio']:.2f} | "
                    f"Signal: {signal.value} | "
                    f"Position: {self.current_position or 'NONE'}"
                )

                # Ejecutar trade si hay señal
                if signal != Signal.HOLD:
                    await self.execute_trade(signal, info)

                # Esperar antes de la siguiente iteración
                await asyncio.sleep(5)  # Check cada 5 segundos

            except Exception as e:
                logger.error(f"Error en el loop principal: {e}")
                await notifier.notify_error(str(e))
                await asyncio.sleep(10)

    async def stop(self):
        """Detener el bot."""
        self.running = False
        logger.info("Deteniendo bot...")

        # Cerrar posiciones abiertas si está configurado
        if os.getenv('CLOSE_ON_STOP', 'false').lower() == 'true':
            if self.current_position:
                side = 'SELL' if self.current_position == 'LONG' else 'BUY'
                position = await self.get_current_position()
                if position:
                    await self.place_market_order(side, position['size'])
                    logger.info("Posición cerrada al detener")

        # Notificar cierre a Telegram
        await notifier.notify_shutdown("Bot detenido por usuario")

        await self.disconnect()


async def main():
    """Función principal."""
    bot = TradingBot()

    try:
        await bot.connect()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Interrupción manual detectada")
        await bot.stop()
    except Exception as e:
        logger.error(f"Error crítico: {e}")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
