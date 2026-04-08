"""
Optimizador de Parámetros para Estrategia de Scalping
=====================================================
Encuentra los mejores parámetros usando walk-forward analysis.
"""

import pandas as pd
import numpy as np
from itertools import product
from typing import Dict, List, Tuple
from datetime import datetime
from strategy import ScalpingStrategy
from backtest import Backtester
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """
    Optimizador de parámetros con walk-forward analysis.
    """

    def __init__(
        self,
        symbol: str = 'BTCUSDT',
        timeframe: str = '1m',
        initial_capital: float = 10000
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_capital = initial_capital

        # Rangos de parámetros a optimizar
        self.param_ranges = {
            'rsi_period': [10, 14, 20],
            'rsi_overbought': [65, 70, 75],
            'rsi_oversold': [25, 30, 35],
            'ema_fast': [7, 9, 12],
            'ema_slow': [18, 21, 26],
            'volume_threshold': [1.2, 1.5, 2.0],
        }

    def fetch_data(self, days: int = 30) -> pd.DataFrame:
        """Obtener datos históricos para optimización."""
        from binance import Client
        client = Client()

        timeframe_minutes = {'1m': 1, '5m': 5, '15m': 15, '1h': 60}
        minutes = timeframe_minutes.get(self.timeframe, 1)
        candles_needed = (days * 24 * 60) // minutes

        klines = []
        for i in range(0, candles_needed, 1000):
            batch = client.futures_klines(
                symbol=self.symbol,
                interval=self.timeframe,
                limit=1000,
                startTime=int((
                    datetime.now().timestamp() - (days * 24 * 60 * 60)
                ) * 1000) + (i * minutes * 60 * 1000)
            )
            klines.extend(batch)
            if len(batch) < 1000:
                break

        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_av', 'num_trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])

        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

    def walk_forward_analysis(
        self,
        df: pd.DataFrame,
        train_days: int = 7,
        test_days: int = 2,
        folds: int = 5
    ) -> Tuple[Dict, List[Dict]]:
        """
        Walk-forward analysis para validar parámetros.

        Divide los datos en múltiples períodos de entrenamiento/test.

        Args:
            df: Datos históricos
            train_days: Días para entrenamiento
            test_days: Días para test
            folds: Cantidad de folds

        Returns:
            Mejores parámetros y resultados de cada fold
        """
        timeframe_minutes = {'1m': 1, '5m': 5, '15m': 15, '1h': 60}
        minutes = timeframe_minutes.get(self.timeframe, 1)

        train_candles = (train_days * 24 * 60) // minutes
        test_candles = (test_days * 24 * 60) // minutes

        # Generar combinaciones de parámetros
        param_combinations = list(product(
            self.param_ranges['rsi_period'],
            self.param_ranges['rsi_overbought'],
            self.param_ranges['rsi_oversold'],
            self.param_ranges['ema_fast'],
            self.param_ranges['ema_slow'],
            self.param_ranges['volume_threshold']
        ))

        logger.info(f"Probando {len(param_combinations)} combinaciones...")

        fold_results = []
        best_params = None
        best_score = -float('inf')

        for fold in range(folds):
            # Dividir datos
            start_idx = fold * (train_candles + test_candles)
            train_end = start_idx + train_candles
            test_end = train_end + test_candles

            if test_end > len(df):
                break

            train_df = df.iloc[start_idx:train_end].copy()
            test_df = df.iloc[train_end:test_end].copy()

            logger.info(f"Fold {fold + 1}/{folds}: Train={len(train_df)}, Test={len(test_df)}")

            # Optimizar en datos de entrenamiento
            fold_best_params = None
            fold_best_score = -float('inf')

            for params in param_combinations[:100]:  # Limitar para tiempo
                config = {
                    'rsi_period': params[0],
                    'rsi_overbought': params[1],
                    'rsi_oversold': params[2],
                    'ema_fast': params[3],
                    'ema_slow': params[4],
                    'volume_threshold': params[5],
                    'max_position_size': 0.001,
                }

                backtester = Backtester(config, self.initial_capital)
                metrics = backtester.run(train_df.copy())

                # Score: combinar retorno, sharpe y win rate
                score = (
                    metrics.get('total_return_pct', 0) * 0.4 +
                    metrics.get('sharpe_ratio', 0) * 0.3 +
                    metrics.get('win_rate', 0) * 0.3
                )

                if score > fold_best_score:
                    fold_best_score = score
                    fold_best_params = config

            if fold_best_params is None:
                continue

            # Validar en datos de test
            test_backtester = Backtester(fold_best_params, self.initial_capital)
            test_metrics = test_backtester.run(test_df.copy())

            fold_results.append({
                'fold': fold + 1,
                'params': fold_best_params,
                'train_score': fold_best_score,
                'test_return': test_metrics.get('total_return_pct', 0),
                'test_sharpe': test_metrics.get('sharpe_ratio', 0),
                'test_drawdown': test_metrics.get('max_drawdown_pct', 0),
                'test_win_rate': test_metrics.get('win_rate', 0),
            })

            # Acumular para encontrar mejores parámetros globales
            avg_test_score = (
                test_metrics.get('total_return_pct', 0) * 0.4 +
                test_metrics.get('sharpe_ratio', 0) * 0.3 +
                test_metrics.get('win_rate', 0) * 0.3
            )

            if avg_test_score > best_score:
                best_score = avg_test_score
                best_params = fold_best_params

        # Promediar resultados
        if fold_results:
            avg_test_return = np.mean([r['test_return'] for r in fold_results])
            avg_test_sharpe = np.mean([r['test_sharpe'] for r in fold_results])
            avg_test_drawdown = np.mean([r['test_drawdown'] for r in fold_results])
            avg_test_win_rate = np.mean([r['test_win_rate'] for r in fold_results])

            logger.info(f"\nResultados Walk-Forward:")
            logger.info(f"Retorno promedio: {avg_test_return:.2f}%")
            logger.info(f"Sharpe promedio: {avg_test_sharpe:.2f}")
            logger.info(f"Drawdown promedio: {avg_test_drawdown:.2f}%")
            logger.info(f"Win Rate promedio: {avg_test_win_rate:.1f}%")

        return best_params or self._default_config(), fold_results

    def _default_config(self) -> Dict:
        """Configuración por defecto."""
        return {
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            'ema_fast': 9,
            'ema_slow': 21,
            'volume_threshold': 1.5,
            'max_position_size': 0.001,
        }

    def grid_search(self, df: pd.DataFrame) -> Tuple[Dict, Dict]:
        """
        Búsqueda exhaustiva de parámetros.

        Args:
            df: Datos históricos

        Returns:
            Mejores parámetros y métricas
        """
        param_combinations = list(product(
            self.param_ranges['rsi_period'],
            self.param_ranges['rsi_overbought'],
            self.param_ranges['rsi_oversold'],
            self.param_ranges['ema_fast'],
            self.param_ranges['ema_slow'],
            self.param_ranges['volume_threshold']
        ))

        logger.info(f"Grid Search: {len(param_combinations)} combinaciones")

        best_params = None
        best_metrics = None
        best_score = -float('inf')

        for i, params in enumerate(param_combinations):
            if i % 50 == 0:
                logger.info(f"Procesando {i}/{len(param_combinations)}...")

            config = {
                'rsi_period': params[0],
                'rsi_overbought': params[1],
                'rsi_oversold': params[2],
                'ema_fast': params[3],
                'ema_slow': params[4],
                'volume_threshold': params[5],
                'max_position_size': 0.001,
            }

            backtester = Backtester(config, self.initial_capital)
            metrics = backtester.run(df.copy())

            # Score compuesto
            score = (
                metrics.get('total_return_pct', 0) * 0.5 +
                metrics.get('sharpe_ratio', 0) * 0.3 +
                metrics.get('win_rate', 0) * 0.2 -
                abs(metrics.get('max_drawdown_pct', 0)) * 0.3
            )

            if score > best_score:
                best_score = score
                best_params = config
                best_metrics = metrics

        return best_params, best_metrics

    def run_full_optimization(self, days: int = 30) -> Dict:
        """
        Ejecutar optimización completa.

        Args:
            days: Días de datos históricos a usar

        Returns:
            Diccionario con mejores parámetros y resultados
        """
        logger.info("=" * 50)
        logger.info("OPTIMIZACIÓN DE PARÁMETROS")
        logger.info("=" * 50)

        # Obtener datos
        logger.info(f"Obteniendo {days} días de datos históricos...")
        df = self.fetch_data(days)
        logger.info(f"Datos obtenidos: {len(df)} velas")

        # Grid search inicial
        logger.info("\n--- Grid Search ---")
        best_params, best_metrics = self.grid_search(df)

        logger.info(f"\nMejores parámetros (Grid Search):")
        for k, v in best_params.items():
            logger.info(f"  {k}: {v}")

        logger.info(f"\nMétricas:")
        logger.info(f"  Retorno: {best_metrics.get('total_return_pct', 0):.2f}%")
        logger.info(f"  Sharpe: {best_metrics.get('sharpe_ratio', 0):.2f}")
        logger.info(f"  Drawdown: {best_metrics.get('max_drawdown_pct', 0):.2f}%")
        logger.info(f"  Win Rate: {best_metrics.get('win_rate', 0):.1f}%")

        # Walk-forward validation
        logger.info("\n--- Walk-Forward Analysis ---")
        wf_params, wf_results = self.walk_forward_analysis(df)

        logger.info(f"\nMejores parámetros (Walk-Forward):")
        for k, v in wf_params.items():
            logger.info(f"  {k}: {v}")

        # Validación final con mejores parámetros
        logger.info("\n--- Validación Final ---")
        final_backtester = Backtester(wf_params, self.initial_capital)
        final_metrics = final_backtester.run(df.copy())

        logger.info(f"\nResultados Finales:")
        logger.info(f"  Capital Final: ${final_metrics.get('final_capital', 0):,.2f}")
        logger.info(f"  Retorno Total: {final_metrics.get('total_return_pct', 0):.2f}%")
        logger.info(f"  Sharpe Ratio: {final_metrics.get('sharpe_ratio', 0):.2f}")
        logger.info(f"  Max Drawdown: {final_metrics.get('max_drawdown_pct', 0):.2f}%")
        logger.info(f"  Win Rate: {final_metrics.get('win_rate', 0):.1f}%")
        logger.info(f"  Total Trades: {final_metrics.get('total_trades', 0)}")

        return {
            'best_params': wf_params,
            'final_metrics': final_metrics,
            'walk_forward_results': wf_results,
            'grid_search_metrics': best_metrics,
        }


def main():
    """Ejecutar optimización."""
    optimizer = ParameterOptimizer(
        symbol='BTCUSDT',
        timeframe='1m',
        initial_capital=10000
    )

    results = optimizer.run_full_optimization(days=14)

    # Guardar resultados
    import json
    with open('optimization_results.json', 'w') as f:
        # Convertir numpy types a Python types
        def convert(obj):
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert(i) for i in obj]
            return obj

        json.dump(convert(results), f, indent=2)

    logger.info("\n✅ Resultados guardados en optimization_results.json")

    # Mostrar configuración recomendada
    print("\n" + "=" * 50)
    print("CONFIGURACIÓN RECOMENDADA (.env)")
    print("=" * 50)
    params = results['best_params']
    print(f"RSI_PERIOD={params['rsi_period']}")
    print(f"RSI_OVERBOUGHT={params['rsi_overbought']}")
    print(f"RSI_OVERSOLD={params['rsi_oversold']}")
    print(f"EMA_FAST={params['ema_fast']}")
    print(f"EMA_SLOW={params['ema_slow']}")
    print(f"VOLUME_THRESHOLD={params['volume_threshold']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
