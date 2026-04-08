"""
Módulo de Notificaciones para Telegram
======================================
Envía alertas de trading a Telegram.
"""

import os
import logging
from typing import Optional
from datetime import datetime
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Envía notificaciones a Telegram sobre operaciones de trading.
    """

    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.info(
                "Telegram notificado deshabilitado. "
                "Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env"
            )

    async def send_message(
        self,
        message: str,
        parse_mode: str = 'HTML'
    ):
        """Enviar mensaje a Telegram."""
        if not self.enabled:
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info("Notificación enviada a Telegram")
                    else:
                        error = await response.text()
                        logger.error(f"Error enviando a Telegram: {error}")
        except Exception as e:
            logger.error(f"Excepción enviando a Telegram: {e}")

    async def notify_order(
        self,
        action: str,  # 'OPEN' o 'CLOSE'
        side: str,  # 'LONG' o 'SHORT'
        symbol: str,
        price: float,
        quantity: float,
        pnl: Optional[float] = None,
        reason: str = ''
    ):
        """
        Notificar apertura o cierre de posición.

        Args:
            action: 'OPEN' o 'CLOSE'
            side: 'LONG' o 'SHORT'
            symbol: Símbolo (ej. BTCUSDT)
            price: Precio de entrada/salida
            quantity: Cantidad en BTC
            pnl: PnL en USD (solo para cierre)
            reason: Razón de la operación
        """
        # Emojis
        emojis = {
            'OPEN': '🔴',
            'CLOSE': '🟢',
            'LONG': '📈',
            'SHORT': '📉',
        }

        if action == 'OPEN':
            message = (
                f"{emojis.get(action, '🔔')} <b>NUEVA POSICIÓN</b>\n\n"
                f"{emojis.get(side, '')} <b>{side}</b> en {symbol}\n\n"
                f"💰 Precio: <b>${price:,.2f}</b>\n"
                f"📊 Cantidad: <b>{quantity:.6f} BTC</b>\n"
                f"💵 Valor: <b>${price * quantity:,.2f} USDT</b>\n\n"
                f"📝 Razón: <i>{reason}</i>"
            )
        else:
            pnl_emoji = '💰' if pnl and pnl > 0 else '💸'
            pnl_color = 'green' if pnl and pnl > 0 else 'red'

            message = (
                f"{emojis.get(action, '🔔')} <b>POSICIÓN CERRADA</b>\n\n"
                f"{emojis.get(side, '')} <b>{side}</b> en {symbol}\n\n"
                f"💰 Precio: <b>${price:,.2f}</b>\n"
                f"📊 Cantidad: <b>{quantity:.6f} BTC</b>\n"
                f"{pnl_emoji} PnL: <b><font color='{pnl_color}'>${pnl:,.2f}</font></b>\n\n"
                f"📝 Razón: <i>{reason}</i>"
            )

        await self.send_message(message)

    async def notify_signal(
        self,
        signal: str,  # 'BUY', 'SELL', 'HOLD'
        symbol: str,
        price: float,
        rsi: float,
        volume_ratio: float,
        reason: str
    ):
        """Notificar señal de trading."""
        emojis = {
            'BUY': '🟢',
            'SELL': '🔴',
            'HOLD': '⚪',
        }

        message = (
            f"{emojis.get(signal, '📊')} <b>SEÑAL DETECTADA</b>\n\n"
            f"📊 Símbolo: <b>{symbol}</b>\n"
            f"💰 Precio: <b>${price:,.2f}</b>\n"
            f"📈 RSI: <b>{rsi:.1f}</b>\n"
            f"📊 Volumen: <b>{volume_ratio:.2f}x</b>\n\n"
            f"📝 Razón: <i>{reason}</i>"
        )

        await self.send_message(message)

    async def notify_daily_summary(
        self,
        total_trades: int,
        wins: int,
        losses: int,
        total_pnl: float,
        win_rate: float
    ):
        """Enviar resumen diario de trading."""
        pnl_emoji = '💰' if total_pnl >= 0 else '💸'
        pnl_color = 'green' if total_pnl >= 0 else 'red'

        message = (
            f"📊 <b>RESUMEN DIARIO</b> 📊\n\n"
            f"📈 Operaciones: <b>{total_trades}</b>\n"
            f"✅ Ganadoras: <b>{wins}</b>\n"
            f"❌ Perdedoras: <b>{losses}</b>\n"
            f"📊 Win Rate: <b>{win_rate:.1f}%</b>\n\n"
            f"{pnl_emoji} <b>PnL Total: <font color='{pnl_color}'>${total_pnl:,.2f}</font></b>"
        )

        await self.send_message(message)

    async def notify_error(self, error_message: str):
        """Notificar error crítico."""
        message = (
            f"🚨 <b>ERROR CRÍTICO</b> 🚨\n\n"
            f"⚠️ El bot ha encontrado un error:\n\n"
            f"<code>{error_message}</code>\n\n"
            f"⏰ Timestamp: <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>"
        )

        await self.send_message(message)

    async def notify_startup(self, testnet: bool = True):
        """Notificar inicio del bot."""
        mode = "TESTNET (Papel)" if testnet else "MAINNET (Real)"

        message = (
            f"🤖 <b>BOT INICIADO</b> 🤖\n\n"
            f"📊 Modo: <b>{mode}</b>\n"
            f"💰 Símbolo: <b>BTCUSDT</b>\n"
            f"⏰ Hora: <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n\n"
            f"✅ El bot está funcionando correctamente"
        )

        await self.send_message(message)

    async def notify_shutdown(self, reason: str = ''):
        """Notificar cierre del bot."""
        message = (
            f"🛑 <b>BOT DETENIDO</b> 🛑\n\n"
            f"⏰ Hora: <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
            f"📝 Razón: <i>{reason}</i>"
        )

        await self.send_message(message)


# Notificador global
notifier = TelegramNotifier()


async def send_trade_notification(
    action: str,
    side: str,
    symbol: str,
    price: float,
    quantity: float,
    pnl: float = None,
    reason: str = ''
):
    """Función helper para notificar operaciones."""
    await notifier.notify_order(action, side, symbol, price, quantity, pnl, reason)


async def send_signal_notification(
    signal: str,
    symbol: str,
    price: float,
    rsi: float,
    volume_ratio: float,
    reason: str
):
    """Función helper para notificar señales."""
    await notifier.notify_signal(signal, symbol, price, rsi, volume_ratio, reason)
