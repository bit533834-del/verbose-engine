import asyncio
from decimal import Decimal
from typing import Optional
import structlog

from .exchanges.base import BaseExchange, Order, OrderSide, OrderType
from .utils.spread_calculator import ArbitrageOpportunity


logger = structlog.get_logger()


class TradeExecutor:
    def __init__(
        self,
        exchanges: dict[str, BaseExchange],
        dry_run: bool = True,
    ):
        self.exchanges = exchanges
        self.dry_run = dry_run

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        trade_amount_usdt: Decimal,
    ) -> tuple[Optional[Order], Optional[Order]]:
        """
        Execute arbitrage trade: buy on cheaper exchange, sell on expensive one.

        Returns tuple of (buy_order, sell_order) or (None, None) if execution fails.
        """
        buy_exchange = self.exchanges.get(opportunity.buy_exchange)
        sell_exchange = self.exchanges.get(opportunity.sell_exchange)

        if not buy_exchange or not sell_exchange:
            logger.error(
                "Exchange not found",
                buy_exchange=opportunity.buy_exchange,
                sell_exchange=opportunity.sell_exchange,
            )
            return None, None

        # Calculate quantity to buy
        quantity = trade_amount_usdt / opportunity.buy_price

        log = logger.bind(
            symbol=opportunity.symbol,
            buy_exchange=opportunity.buy_exchange,
            sell_exchange=opportunity.sell_exchange,
            buy_price=str(opportunity.buy_price),
            sell_price=str(opportunity.sell_price),
            quantity=str(quantity),
            spread_percent=str(opportunity.spread_percent),
            net_profit=str(opportunity.potential_profit_usdt),
        )

        if self.dry_run:
            log.info("DRY RUN: Would execute arbitrage trade")
            return None, None

        try:
            # Execute both orders simultaneously
            log.info("Executing arbitrage trade")

            buy_order, sell_order = await asyncio.gather(
                buy_exchange.create_order(
                    symbol=opportunity.symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                ),
                sell_exchange.create_order(
                    symbol=opportunity.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                ),
            )

            log.info(
                "Arbitrage trade executed",
                buy_order_id=buy_order.order_id,
                sell_order_id=sell_order.order_id,
            )

            return buy_order, sell_order

        except Exception as e:
            log.error("Failed to execute arbitrage trade", error=str(e))
            return None, None

    async def check_balances(
        self,
        symbol: str,
        trade_amount_usdt: Decimal,
    ) -> dict[str, dict[str, Decimal]]:
        """
        Check balances on all exchanges for the given trading pair.
        """
        base, quote = symbol.split("/")
        balances = {}

        for name, exchange in self.exchanges.items():
            try:
                base_balance = await exchange.get_balance(base)
                quote_balance = await exchange.get_balance(quote)
                balances[name] = {
                    base: base_balance,
                    quote: quote_balance,
                }
            except Exception as e:
                logger.error(
                    "Failed to get balance",
                    exchange=name,
                    error=str(e),
                )
                balances[name] = {base: Decimal("0"), quote: Decimal("0")}

        return balances

    async def has_sufficient_balance(
        self,
        opportunity: ArbitrageOpportunity,
        trade_amount_usdt: Decimal,
    ) -> bool:
        """
        Check if there's sufficient balance to execute the arbitrage.
        """
        base, quote = opportunity.symbol.split("/")

        buy_exchange = self.exchanges.get(opportunity.buy_exchange)
        sell_exchange = self.exchanges.get(opportunity.sell_exchange)

        if not buy_exchange or not sell_exchange:
            return False

        try:
            # Need quote currency on buy exchange
            buy_balance = await buy_exchange.get_balance(quote)
            # Need base currency on sell exchange
            sell_quantity = trade_amount_usdt / opportunity.buy_price
            sell_balance = await sell_exchange.get_balance(base)

            has_buy_balance = buy_balance >= trade_amount_usdt
            has_sell_balance = sell_balance >= sell_quantity

            if not has_buy_balance:
                logger.warning(
                    "Insufficient balance for buy",
                    exchange=opportunity.buy_exchange,
                    required=str(trade_amount_usdt),
                    available=str(buy_balance),
                )

            if not has_sell_balance:
                logger.warning(
                    "Insufficient balance for sell",
                    exchange=opportunity.sell_exchange,
                    required=str(sell_quantity),
                    available=str(sell_balance),
                )

            return has_buy_balance and has_sell_balance

        except Exception as e:
            logger.error("Failed to check balances", error=str(e))
            return False
