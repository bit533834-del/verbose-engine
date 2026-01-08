from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ..exchanges.base import Ticker, BaseExchange


@dataclass
class ArbitrageOpportunity:
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    spread_percent: Decimal
    net_profit_percent: Decimal
    potential_profit_usdt: Decimal
    timestamp: int


class SpreadCalculator:
    def __init__(self, min_spread_percent: Decimal = Decimal("0.5")):
        self.min_spread_percent = min_spread_percent

    def calculate_spread(
        self,
        ticker1: Ticker,
        ticker2: Ticker,
        exchange1_taker_fee: Decimal,
        exchange2_taker_fee: Decimal,
        trade_amount_usdt: Decimal = Decimal("100"),
    ) -> Optional[ArbitrageOpportunity]:
        """
        Calculate arbitrage opportunity between two exchanges.

        Returns ArbitrageOpportunity if the spread exceeds minimum threshold
        after accounting for fees, otherwise returns None.
        """
        # Determine which exchange to buy from (lower ask) and sell to (higher bid)
        if ticker1.ask < ticker2.bid:
            buy_ticker = ticker1
            sell_ticker = ticker2
            buy_fee = exchange1_taker_fee
            sell_fee = exchange2_taker_fee
        elif ticker2.ask < ticker1.bid:
            buy_ticker = ticker2
            sell_ticker = ticker1
            buy_fee = exchange2_taker_fee
            sell_fee = exchange1_taker_fee
        else:
            return None

        # Calculate raw spread
        raw_spread = sell_ticker.bid - buy_ticker.ask
        raw_spread_percent = (raw_spread / buy_ticker.ask) * Decimal("100")

        # Calculate net spread after fees
        total_fees_percent = (buy_fee + sell_fee) * Decimal("100")
        net_spread_percent = raw_spread_percent - total_fees_percent

        if net_spread_percent < self.min_spread_percent:
            return None

        # Calculate potential profit
        quantity = trade_amount_usdt / buy_ticker.ask
        buy_cost = trade_amount_usdt * (Decimal("1") + buy_fee)
        sell_revenue = quantity * sell_ticker.bid * (Decimal("1") - sell_fee)
        potential_profit = sell_revenue - buy_cost

        return ArbitrageOpportunity(
            symbol=ticker1.symbol,
            buy_exchange=buy_ticker.exchange,
            sell_exchange=sell_ticker.exchange,
            buy_price=buy_ticker.ask,
            sell_price=sell_ticker.bid,
            spread_percent=raw_spread_percent,
            net_profit_percent=net_spread_percent,
            potential_profit_usdt=potential_profit,
            timestamp=max(ticker1.timestamp, ticker2.timestamp),
        )

    def find_best_opportunity(
        self,
        tickers: list[Ticker],
        exchanges: dict[str, BaseExchange],
        trade_amount_usdt: Decimal = Decimal("100"),
    ) -> Optional[ArbitrageOpportunity]:
        """
        Find the best arbitrage opportunity among multiple exchanges.
        """
        best_opportunity: Optional[ArbitrageOpportunity] = None

        for i, ticker1 in enumerate(tickers):
            for ticker2 in tickers[i + 1:]:
                if ticker1.symbol != ticker2.symbol:
                    continue

                exchange1 = exchanges.get(ticker1.exchange)
                exchange2 = exchanges.get(ticker2.exchange)

                if not exchange1 or not exchange2:
                    continue

                opportunity = self.calculate_spread(
                    ticker1,
                    ticker2,
                    exchange1.taker_fee,
                    exchange2.taker_fee,
                    trade_amount_usdt,
                )

                if opportunity and (
                    best_opportunity is None
                    or opportunity.net_profit_percent > best_opportunity.net_profit_percent
                ):
                    best_opportunity = opportunity

        return best_opportunity
