"""
Backtesting para Estrategia de Scalping
=======================================
Módulo para probar la estrategia con datos históricos.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from binance import Client
from strategy import ScalpingStrategy, Signal


class Backtester:
    """
    Backtester para la estrategia de scalping.
    """

    def __init__(self, config: Dict, initial_capital: float = 10000):
        self.config = config
        self.initial_capital = initial_capital
        self.strategy = ScalpingStrategy(config)

        # Resultados
        self.trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.daily_returns: List[float] = []

    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        days: int = 7
    ) -> pd.DataFrame:
        """
        Obtener datos históricos de Binance.

        Args:
            symbol: Símbolo (ej. BTCUSDT)
            timeframe: Timeframe (ej. 1m, 5m, 15m)
            days: Cantidad de días hacia atrás
        """
        client = Client()

        # Calcular cantidad de velas necesarias
        timeframe_minutes = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15,
            '30m': 30, '1h': 60, '4h': 240
        }
        minutes = timeframe_minutes.get(timeframe, 1)
        candles_needed = (days * 24 * 60) // minutes

        # Binance permite máximo 1000 velas por request
        klines = []
        for i in range(0, candles_needed, 1000):
            batch = client.futures_klines(
                symbol=symbol,
                interval=timeframe,
                limit=1000,
                startTime=int((
                    datetime.now().timestamp() -
                    (days * 24 * 60 * 60)
                ) * 1000) + (i * minutes * 60 * 1000)
            )
            klines.extend(batch)
            if len(batch) < 1000:
                break

        # Convertir a DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_av', 'num_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])

        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)

        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

    def run(
        self,
        df: pd.DataFrame,
        fee_rate: float = 0.0004
    ) -> Dict:
        """
        Ejecutar backtest.

        Args:
            df: DataFrame con datos OHLCV
            fee_rate: Comisión por trade (0.04% default para Binance futures)
        """
        capital = self.initial_capital
        position = None
        equity_history = []

        # Calcular indicadores para todo el DataFrame
        df = self.strategy.calculate_indicators(df)

        # Eliminar filas con NaN
        df = df.dropna()

        for i in range(1, len(df)):
            curr_row = df.iloc[i]
            prev_row = df.iloc[i - 1]

            # Analizar señal
            signal, info = self.strategy.analyze(
                df.iloc[:i + 1],
                position['side'] if position else None
            )

            # Cerrar posición existente
            if position:
                pnl_pct = 0
                if position['side'] == 'LONG':
                    pnl_pct = (
                        curr_row['close'] - position['entry_price']
                    ) / position['entry_price']
                else:
                    pnl_pct = (
                        position['entry_price'] - curr_row['close']
                    ) / position['entry_price']

                # Check stop loss / take profit
                sl_hit = False
                tp_hit = False

                if position['side'] == 'LONG':
                    if curr_row['low'] <= position['stop_loss']:
                        sl_hit = True
                    if curr_row['high'] >= position['take_profit']:
                        tp_hit = True
                else:
                    if curr_row['high'] >= position['stop_loss']:
                        sl_hit = True
                    if curr_row['low'] <= position['take_profit']:
                        tp_hit = True

                # Cerrar si hay señal contraria o SL/TP
                if (
                    signal == Signal.SELL and position['side'] == 'LONG' or
                    signal == Signal.BUY and position['side'] == 'SHORT' or
                    sl_hit or tp_hit
                ):
                    # Calcular PnL
                    if position['side'] == 'LONG':
                        pnl = (
                            (curr_row['close'] - position['entry_price'])
                            / position['entry_price']
                        )
                    else:
                        pnl = (
                            (position['entry_price'] - curr_row['close'])
                            / position['entry_price']
                        )

                    # Aplicar comisiones
                    fee = fee_rate * 2  # Entrada + salida
                    pnl = pnl - fee

                    # Actualizar capital
                    capital *= (1 + pnl)

                    # Guardar trade
                    self.trades.append({
                        'entry_time': position['entry_time'],
                        'exit_time': curr_row['timestamp'],
                        'side': position['side'],
                        'entry_price': position['entry_price'],
                        'exit_price': curr_row['close'],
                        'pnl_pct': pnl * 100,
                        'pnl_usd': capital - self.initial_capital,
                        'exit_type': (
                            'SL' if sl_hit else
                            'TP' if tp_hit else 'SIGNAL'
                        )
                    })

                    position = None

            # Abrir nueva posición
            if signal == Signal.BUY and not position:
                atr = info.get('atr', curr_row['close'] * 0.01)
                sl, tp = self.strategy.get_stop_loss_take_profit(
                    curr_row['close'], atr, 'LONG'
                )
                position = {
                    'side': 'LONG',
                    'entry_price': curr_row['close'],
                    'entry_time': curr_row['timestamp'],
                    'stop_loss': sl,
                    'take_profit': tp,
                }

            elif signal == Signal.SELL and not position:
                atr = info.get('atr', curr_row['close'] * 0.01)
                sl, tp = self.strategy.get_stop_loss_take_profit(
                    curr_row['close'], atr, 'SHORT'
                )
                position = {
                    'side': 'SHORT',
                    'entry_price': curr_row['close'],
                    'entry_time': curr_row['timestamp'],
                    'stop_loss': sl,
                    'take_profit': tp,
                }

            # Registrar equity
            equity_history.append(capital)

        self.equity_curve = equity_history

        # Calcular métricas
        return self.calculate_metrics(df)

    def calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """Calcular métricas de performance."""
        if not self.trades:
            return {'error': 'No se realizaron operaciones'}

        trades_df = pd.DataFrame(self.trades)

        # Métricas básicas
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl_pct'] > 0])
        losing_trades = len(trades_df[trades_df['pnl_pct'] <= 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        avg_win = trades_df[trades_df['pnl_pct'] > 0]['pnl_pct'].mean()
        avg_loss = trades_df[trades_df['pnl_pct'] <= 0]['pnl_pct'].mean()

        profit_factor = (
            abs(avg_win * winning_trades / (avg_loss * losing_trades))
            if losing_trades > 0 and avg_loss != 0 else float('inf')
        )

        # Drawdown máximo
        equity_series = pd.Series(self.equity_curve)
        running_max = equity_series.expanding().max()
        drawdowns = (equity_series - running_max) / running_max
        max_drawdown = drawdowns.min()

        # Sharpe ratio (asumiendo 252 días de trading)
        if len(self.equity_curve) > 1:
            returns = equity_series.pct_change().dropna()
            sharpe = (
                returns.mean() / returns.std() * np.sqrt(252)
                if returns.std() != 0 else 0
            )
        else:
            sharpe = 0

        # Retorno total
        total_return = (
            (self.equity_curve[-1] - self.initial_capital)
            / self.initial_capital * 100
            if self.equity_curve else 0
        )

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate * 100,
            'avg_win_pct': avg_win if not pd.isna(avg_win) else 0,
            'avg_loss_pct': avg_loss if not pd.isna(avg_loss) else 0,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown * 100,
            'sharpe_ratio': sharpe,
            'total_return_pct': total_return,
            'final_capital': self.equity_curve[-1] if self.equity_curve else 0,
            'trades': trades_df.to_dict('records')
        }

    def print_report(self, metrics: Dict):
        """Imprimir reporte de backtest."""
        print("\n" + "=" * 50)
        print("REPORTE DE BACKTEST")
        print("=" * 50)
        print(f"\nCapital Inicial: ${self.initial_capital:,.2f}")
        print(f"Capital Final: ${metrics.get('final_capital', 0):,.2f}")
        print(f"Retorno Total: {metrics.get('total_return_pct', 0):.2f}%")
        print(f"\nOperaciones Totales: {metrics.get('total_trades', 0)}")
        print(f"Operaciones Ganadoras: {metrics.get('winning_trades', 0)}")
        print(f"Operaciones Perdedoras: {metrics.get('losing_trades', 0)}")
        print(f"Win Rate: {metrics.get('win_rate', 0):.2f}%")
        print(f"\nGanancia Promedio: {metrics.get('avg_win_pct', 0):.4f}%")
        print(f"Pérdida Promedio: {metrics.get('avg_loss_pct', 0):.4f}%")
        print(f"Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        print(f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
        print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        print("=" * 50 + "\n")


def main():
    """Ejecutar backtest de ejemplo."""
    # Configuración
    config = {
        'rsi_period': 14,
        'rsi_overbought': 70,
        'rsi_oversold': 30,
        'ema_fast': 9,
        'ema_slow': 21,
        'volume_threshold': 1.5,
        'max_position_size': 0.001,
    }

    # Inicializar backtester
    backtester = Backtester(config, initial_capital=10000)

    # Obtener datos históricos (últimos 7 días, 1m)
    print("Obteniendo datos históricos...")
    df = backtester.fetch_historical_data('BTCUSDT', '1m', days=7)
    print(f"Datos obtenidos: {len(df)} velas")

    # Ejecutar backtest
    print("Ejecutando backtest...")
    metrics = backtester.run(df)

    # Imprimir reporte
    backtester.print_report(metrics)


if __name__ == "__main__":
    main()
