from decimal import Decimal
from typing import Optional
import json
import time

from .base import BaseExchange, OrderBook, Ticker, Order, OrderSide, OrderType


class BybitExchange(BaseExchange):
    @property
    def name(self) -> str:
        return "bybit"

    @property
    def base_url(self) -> str:
        if self.testnet:
            return "https://api-testnet.bybit.com"
        return "https://api.bybit.com"

    @property
    def maker_fee(self) -> Decimal:
        return Decimal("0.001")  # 0.1%

    @property
    def taker_fee(self) -> Decimal:
        return Decimal("0.001")  # 0.1%

    def normalize_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT to BTCUSDT."""
        return symbol.replace("/", "")

    def denormalize_symbol(self, symbol: str) -> str:
        """Convert BTCUSDT to BTC/USDT."""
        if "USDT" in symbol:
            return symbol.replace("USDT", "/USDT")
        return symbol

    def _generate_signature(self, timestamp: int, params: dict) -> str:
        param_str = str(timestamp) + self.api_key + "5000"
        if params:
            param_str += json.dumps(params, separators=(",", ":"))
        return super()._generate_signature(param_str)

    def _get_auth_headers(self, timestamp: int, params: dict = None) -> dict:
        signature = self._generate_signature(timestamp, params or {})
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": str(timestamp),
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": "5000",
            "Content-Type": "application/json",
        }

    async def get_ticker(self, symbol: str) -> Ticker:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/v5/market/tickers"

        params = {"category": "spot", "symbol": exchange_symbol}

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        if data["retCode"] != 0:
            raise Exception(f"Bybit API error: {data['retMsg']}")

        ticker_data = data["result"]["list"][0]

        return Ticker(
            symbol=symbol,
            bid=Decimal(ticker_data["bid1Price"]),
            ask=Decimal(ticker_data["ask1Price"]),
            last=Decimal(ticker_data["lastPrice"]),
            timestamp=self._get_timestamp(),
            exchange=self.name,
        )

    async def get_orderbook(self, symbol: str, limit: int = 10) -> OrderBook:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/v5/market/orderbook"

        params = {"category": "spot", "symbol": exchange_symbol, "limit": limit}

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        if data["retCode"] != 0:
            raise Exception(f"Bybit API error: {data['retMsg']}")

        orderbook = data["result"]
        bids = [(Decimal(price), Decimal(qty)) for price, qty in orderbook["b"]]
        asks = [(Decimal(price), Decimal(qty)) for price, qty in orderbook["a"]]

        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=int(orderbook["ts"]),
            exchange=self.name,
        )

    async def get_balance(self, asset: str) -> Decimal:
        session = await self._get_session()
        url = f"{self.base_url}/v5/account/wallet-balance"

        timestamp = self._get_timestamp()
        headers = self._get_auth_headers(timestamp)

        params = {"accountType": "UNIFIED", "coin": asset}

        async with session.get(url, params=params, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        if data["retCode"] != 0:
            raise Exception(f"Bybit API error: {data['retMsg']}")

        for account in data["result"]["list"]:
            for coin in account.get("coin", []):
                if coin["coin"] == asset:
                    return Decimal(coin["walletBalance"])

        return Decimal("0")

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
    ) -> Order:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/v5/order/create"

        timestamp = self._get_timestamp()

        body = {
            "category": "spot",
            "symbol": exchange_symbol,
            "side": "Buy" if side == OrderSide.BUY else "Sell",
            "orderType": "Market" if order_type == OrderType.MARKET else "Limit",
            "qty": str(quantity),
        }

        if order_type == OrderType.LIMIT and price is not None:
            body["price"] = str(price)
            body["timeInForce"] = "GTC"

        headers = self._get_auth_headers(timestamp, body)

        async with session.post(url, json=body, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        if data["retCode"] != 0:
            raise Exception(f"Bybit API error: {data['retMsg']}")

        result = data["result"]

        return Order(
            order_id=result["orderId"],
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=price,
            quantity=quantity,
            filled_quantity=Decimal("0"),
            status="NEW",
            timestamp=self._get_timestamp(),
            exchange=self.name,
        )

    async def get_order(self, symbol: str, order_id: str) -> Order:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/v5/order/realtime"

        timestamp = self._get_timestamp()
        headers = self._get_auth_headers(timestamp)

        params = {
            "category": "spot",
            "symbol": exchange_symbol,
            "orderId": order_id,
        }

        async with session.get(url, params=params, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        if data["retCode"] != 0:
            raise Exception(f"Bybit API error: {data['retMsg']}")

        order_data = data["result"]["list"][0]

        return Order(
            order_id=order_data["orderId"],
            symbol=symbol,
            side=OrderSide.BUY if order_data["side"] == "Buy" else OrderSide.SELL,
            order_type=OrderType.MARKET if order_data["orderType"] == "Market" else OrderType.LIMIT,
            price=Decimal(order_data["price"]) if order_data["price"] else None,
            quantity=Decimal(order_data["qty"]),
            filled_quantity=Decimal(order_data["cumExecQty"]),
            status=order_data["orderStatus"],
            timestamp=int(order_data["createdTime"]),
            exchange=self.name,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/v5/order/cancel"

        timestamp = self._get_timestamp()

        body = {
            "category": "spot",
            "symbol": exchange_symbol,
            "orderId": order_id,
        }

        headers = self._get_auth_headers(timestamp, body)

        async with session.post(url, json=body, headers=headers) as response:
            data = await response.json()
            return data["retCode"] == 0
