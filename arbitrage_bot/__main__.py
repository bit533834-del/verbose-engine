import asyncio
import signal
import sys

import structlog

from .bot import ArbitrageBot
from .exchanges import BinanceExchange, BybitExchange, KuCoinExchange
from .utils import Config, setup_logging


logger = structlog.get_logger()


def create_exchanges(config: Config) -> dict:
    """Create exchange instances from configuration."""
    exchanges = {}

    if config.binance.enabled and config.binance.api_key:
        exchanges["binance"] = BinanceExchange(
            api_key=config.binance.api_key,
            api_secret=config.binance.api_secret,
            testnet=config.binance.testnet,
        )
        logger.info("Binance exchange initialized", testnet=config.binance.testnet)

    if config.bybit.enabled and config.bybit.api_key:
        exchanges["bybit"] = BybitExchange(
            api_key=config.bybit.api_key,
            api_secret=config.bybit.api_secret,
            testnet=config.bybit.testnet,
        )
        logger.info("Bybit exchange initialized", testnet=config.bybit.testnet)

    if config.kucoin.enabled and config.kucoin.api_key:
        exchanges["kucoin"] = KuCoinExchange(
            api_key=config.kucoin.api_key,
            api_secret=config.kucoin.api_secret,
            passphrase=config.kucoin.passphrase,
            testnet=config.kucoin.testnet,
        )
        logger.info("KuCoin exchange initialized", testnet=config.kucoin.testnet)

    return exchanges


async def main():
    """Main entry point for the arbitrage bot."""
    # Load configuration
    config = Config.from_env()

    # Setup logging
    setup_logging(config.log_level)

    logger.info("Starting Crypto Arbitrage Bot", version="1.0.0")

    # Create exchanges
    exchanges = create_exchanges(config)

    if len(exchanges) < 2:
        logger.error(
            "At least 2 exchanges must be configured",
            configured=list(exchanges.keys()),
        )
        sys.exit(1)

    # Create and start the bot
    bot = ArbitrageBot(
        exchanges=exchanges,
        trading_pairs=config.trading_pairs,
        min_spread_percent=config.min_spread_percent,
        trade_amount_usdt=config.trade_amount_usdt,
        scan_interval_seconds=config.scan_interval_seconds,
        dry_run=config.dry_run,
    )

    # Setup graceful shutdown
    loop = asyncio.get_event_loop()

    def shutdown_handler():
        logger.info("Shutdown signal received")
        asyncio.create_task(bot.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)

    try:
        await bot.start()
    except Exception as e:
        logger.error("Bot crashed", error=str(e))
        await bot.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
