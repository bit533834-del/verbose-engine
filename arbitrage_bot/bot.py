import asyncio
from decimal import Decimal
from typing import Optional
import structlog

from .exchanges.base import BaseExchange, Ticker
from .utils.spread_calculator import SpreadCalculator, ArbitrageOpportunity
from .trade_executor import TradeExecutor


logger = structlog.get_logger()


class ArbitrageBot:
    def __init__(
        self,
        exchanges: dict[str, BaseExchange],
        trading_pairs: list[str],
        min_spread_percent: Decimal = Decimal("0.5"),
        trade_amount_usdt: Decimal = Decimal("100"),
        scan_interval_seconds: int = 5,
        dry_run: bool = True,
    ):
        self.exchanges = exchanges
        self.trading_pairs = trading_pairs
        self.min_spread_percent = min_spread_percent
        self.trade_amount_usdt = trade_amount_usdt
        self.scan_interval_seconds = scan_interval_seconds
        self.dry_run = dry_run

        self.spread_calculator = SpreadCalculator(min_spread_percent)
        self.trade_executor = TradeExecutor(exchanges, dry_run)

        self._running = False
        self._stats = {
            "scans": 0,
            "opportunities_found": 0,
            "trades_executed": 0,
            "total_profit": Decimal("0"),
        }

    async def fetch_all_tickers(self, symbol: str) -> list[Ticker]:
        """Fetch tickers from all exchanges concurrently."""
        tasks = []
        exchange_names = []

        for name, exchange in self.exchanges.items():
            tasks.append(exchange.get_ticker(symbol))
            exchange_names.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        tickers = []
        for name, result in zip(exchange_names, results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to fetch ticker",
                    exchange=name,
                    symbol=symbol,
                    error=str(result),
                )
            else:
                tickers.append(result)

        return tickers

    async def scan_for_opportunities(self) -> list[ArbitrageOpportunity]:
        """Scan all trading pairs for arbitrage opportunities."""
        opportunities = []

        for symbol in self.trading_pairs:
            tickers = await self.fetch_all_tickers(symbol)

            if len(tickers) < 2:
                continue

            opportunity = self.spread_calculator.find_best_opportunity(
                tickers,
                self.exchanges,
                self.trade_amount_usdt,
            )

            if opportunity:
                opportunities.append(opportunity)

        return opportunities

    async def process_opportunity(
        self, opportunity: ArbitrageOpportunity
    ) -> bool:
        """Process a single arbitrage opportunity."""
        log = logger.bind(
            symbol=opportunity.symbol,
            buy_exchange=opportunity.buy_exchange,
            sell_exchange=opportunity.sell_exchange,
            spread=f"{opportunity.spread_percent:.4f}%",
            net_profit=f"{opportunity.net_profit_percent:.4f}%",
            potential_profit=f"${opportunity.potential_profit_usdt:.2f}",
        )

        log.info("Arbitrage opportunity found")

        # Check balances before executing
        if not self.dry_run:
            has_balance = await self.trade_executor.has_sufficient_balance(
                opportunity,
                self.trade_amount_usdt,
            )

            if not has_balance:
                log.warning("Insufficient balance to execute trade")
                return False

        # Execute the trade
        buy_order, sell_order = await self.trade_executor.execute_arbitrage(
            opportunity,
            self.trade_amount_usdt,
        )

        if buy_order and sell_order:
            self._stats["trades_executed"] += 1
            self._stats["total_profit"] += opportunity.potential_profit_usdt
            log.info("Trade executed successfully")
            return True

        return False

    async def run_scan_cycle(self) -> None:
        """Run a single scan cycle."""
        self._stats["scans"] += 1

        logger.debug(
            "Starting scan cycle",
            scan_number=self._stats["scans"],
            pairs=self.trading_pairs,
        )

        opportunities = await self.scan_for_opportunities()

        for opportunity in opportunities:
            self._stats["opportunities_found"] += 1
            await self.process_opportunity(opportunity)

    async def start(self) -> None:
        """Start the arbitrage bot."""
        self._running = True

        logger.info(
            "Starting arbitrage bot",
            exchanges=list(self.exchanges.keys()),
            trading_pairs=self.trading_pairs,
            min_spread=f"{self.min_spread_percent}%",
            trade_amount=f"${self.trade_amount_usdt}",
            scan_interval=f"{self.scan_interval_seconds}s",
            dry_run=self.dry_run,
        )

        while self._running:
            try:
                await self.run_scan_cycle()
            except Exception as e:
                logger.error("Error in scan cycle", error=str(e))

            await asyncio.sleep(self.scan_interval_seconds)

    async def stop(self) -> None:
        """Stop the arbitrage bot."""
        self._running = False
        logger.info(
            "Stopping arbitrage bot",
            stats=self._stats,
        )

        # Close all exchange sessions
        for exchange in self.exchanges.values():
            await exchange.close()

    def get_stats(self) -> dict:
        """Get current bot statistics."""
        return self._stats.copy()
