"""
Bitcoin Scalping Strategy
=========================
Estrategia de scalping basada en múltiples indicadores técnicos:
- EMA crossover (9/21 períodos)
- RSI para sobrecompra/sobreventa
- Volumen para confirmación
- Bandas de Bollinger para volatilidad
"""

import pandas as pd
import pandas_ta as ta
from datetime import datetime
from typing import Dict, Optional, Tuple
from enum import Enum


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ScalpingStrategy:
    """
    Estrategia de scalping para Bitcoin en timeframe de 1 minuto.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.ema_fast = config.get('ema_fast', 9)
        self.ema_slow = config.get('ema_slow', 21)
        self.volume_threshold = config.get('volume_threshold', 1.5)
        self.bollinger_period = config.get('bollinger_period', 20)
        self.bollinger_std = config.get('bollinger_std', 2.0)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcular todos los indicadores técnicos necesarios."""
        if df.empty or len(df) < self.ema_slow:
            return df

        # EMA crossover
        df['ema_fast'] = ta.ema(df['close'], length=self.ema_fast)
        df['ema_slow'] = ta.ema(df['close'], length=self.ema_slow)

        # RSI
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)

        # Bandas de Bollinger
        bbands = ta.bbands(
            df['close'],
            length=self.bollinger_period,
            std=self.bollinger_std
        )
        df['bb_upper'] = bbands.iloc[:, 2]
        df['bb_middle'] = bbands.iloc[:, 1]
        df['bb_lower'] = bbands.iloc[:, 0]

        # Volumen promedio (últimas 20 velas)
        df['volume_sma'] = ta.sma(df['volume'], length=20)
        df['volume_ratio'] = df['volume'] / df['volume_sma']

        # ATR para stop loss dinámico
        df['atr'] = ta.atr(
            df['high'],
            df['low'],
            df['close'],
            length=14
        )

        return df

    def analyze(
        self,
        df: pd.DataFrame,
        current_position: Optional[str] = None
    ) -> Tuple[Signal, Dict]:
        """
        Analizar el mercado y generar señal de trading.

        Args:
            df: DataFrame con datos OHLCV
            current_position: Posición actual ('LONG', 'SHORT', o None)

        Returns:
            Tuple con Signal y dict de información adicional
        """
        df = self.calculate_indicators(df)

        if len(df) < 2:
            return Signal.HOLD, {'reason': 'Datos insuficientes'}

        # Obtener últimos datos
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        info = {
            'timestamp': datetime.now().isoformat(),
            'price': curr['close'],
            'rsi': curr['rsi'],
            'ema_fast': curr['ema_fast'],
            'ema_slow': curr['ema_slow'],
            'volume_ratio': curr['volume_ratio'],
            'bb_upper': curr['bb_upper'],
            'bb_lower': curr['bb_lower'],
            'atr': curr['atr'],
        }

        # Validar volumen mínimo
        if curr['volume_ratio'] < 1.0:
            return Signal.HOLD, {**info, 'reason': 'Volumen insuficiente'}

        # Señales de compra (LONG)
        long_conditions = (
            # EMA crossover alcista
            (prev['ema_fast'] <= prev['ema_slow']) and
            (curr['ema_fast'] > curr['ema_slow']) and
            # RSI no sobrecomprado
            (curr['rsi'] < self.rsi_overbought) and
            # Precio cerca o tocando banda inferior
            (curr['close'] <= curr['bb_lower'] * 1.001)
        )

        # Señales de venta (SHORT)
        short_conditions = (
            # EMA crossover bajista
            (prev['ema_fast'] >= prev['ema_slow']) and
            (curr['ema_fast'] < curr['ema_slow']) and
            # RSI no sobrevendido
            (curr['rsi'] > self.rsi_oversold) and
            # Precio cerca o tocando banda superior
            (curr['close'] >= curr['bb_upper'] * 0.999)
        )

        # Condiciones de salida
        exit_long = False
        exit_short = False

        if current_position == 'LONG':
            # Salir si RSI sobrecomprado o EMA crossover bajista
            exit_long = (
                (curr['rsi'] > self.rsi_overbought) or
                (curr['ema_fast'] < curr['ema_slow'])
            )
        elif current_position == 'SHORT':
            # Salir si RSI sobrevendido o EMA crossover alcista
            exit_short = (
                (curr['rsi'] < self.rsi_oversold) or
                (curr['ema_fast'] > curr['ema_slow'])
            )

        if exit_long:
            return Signal.SELL, {**info, 'reason': 'Salida de LONG'}
        elif exit_short:
            return Signal.BUY, {**info, 'reason': 'Salida de SHORT'}
        elif long_conditions:
            return Signal.BUY, {**info, 'reason': 'Entrada en LONG'}
        elif short_conditions:
            return Signal.SELL, {**info, 'reason': 'Entrada en SHORT'}

        return Signal.HOLD, {**info, 'reason': 'Sin señal clara'}

    def calculate_position_size(
        self,
        price: float,
        account_balance: float,
        atr: float
    ) -> float:
        """
        Calcular tamaño de posición basado en volatilidad (ATR).

        Usa el método de volatilidad para ajustar el tamaño según el riesgo.
        """
        max_position = self.config.get('max_position_size', 0.001)
        risk_per_trade = account_balance * 0.02  # 2% riesgo por trade

        # Tamaño basado en ATR (menor volatilidad = mayor posición)
        atr_risk = atr * 2  # 2 ATR de stop
        position_by_atr = risk_per_trade / atr_risk if atr_risk > 0 else max_position

        # Limitar al máximo configurado
        return min(position_by_atr, max_position)

    def get_stop_loss_take_profit(
        self,
        entry_price: float,
        atr: float,
        direction: str
    ) -> Tuple[float, float]:
        """
        Calcular niveles de stop loss y take profit basados en ATR.
        """
        atr_mult = 1.5

        if direction == 'LONG':
            stop_loss = entry_price - (atr * atr_mult)
            take_profit = entry_price + (atr * atr_mult * 2)  # 2:1 reward/risk
        else:  # SHORT
            stop_loss = entry_price + (atr * atr_mult)
            take_profit = entry_price - (atr * atr_mult * 2)

        return round(stop_loss, 2), round(take_profit, 2)
