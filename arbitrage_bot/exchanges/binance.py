from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode

from .base import BaseExchange, OrderBook, Ticker, Order, OrderSide, OrderType


class BinanceExchange(BaseExchange):
    @property
    def name(self) -> str:
        return "binance"

    @property
    def base_url(self) -> str:
        if self.testnet:
            return "https://testnet.binance.vision"
        return "https://api.binance.com"

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
        elif "BTC" in symbol:
            return symbol.replace("BTC", "/BTC")
        return symbol

    async def get_ticker(self, symbol: str) -> Ticker:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/api/v3/ticker/bookTicker"

        async with session.get(url, params={"symbol": exchange_symbol}) as response:
            response.raise_for_status()
            data = await response.json()

        return Ticker(
            symbol=symbol,
            bid=Decimal(data["bidPrice"]),
            ask=Decimal(data["askPrice"]),
            last=Decimal(data["bidPrice"]),  # bookTicker doesn't have last price
            timestamp=self._get_timestamp(),
            exchange=self.name,
        )

    async def get_orderbook(self, symbol: str, limit: int = 10) -> OrderBook:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/api/v3/depth"

        async with session.get(
            url, params={"symbol": exchange_symbol, "limit": limit}
        ) as response:
            response.raise_for_status()
            data = await response.json()

        bids = [(Decimal(price), Decimal(qty)) for price, qty in data["bids"]]
        asks = [(Decimal(price), Decimal(qty)) for price, qty in data["asks"]]

        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=self._get_timestamp(),
            exchange=self.name,
        )

    async def get_balance(self, asset: str) -> Decimal:
        session = await self._get_session()
        url = f"{self.base_url}/api/v3/account"

        timestamp = self._get_timestamp()
        params = {"timestamp": timestamp}
        query_string = urlencode(params)
        signature = self._generate_signature(query_string)
        params["signature"] = signature

        headers = {"X-MBX-APIKEY": self.api_key}

        async with session.get(url, params=params, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        for balance in data["balances"]:
            if balance["asset"] == asset:
                return Decimal(balance["free"])

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
        url = f"{self.base_url}/api/v3/order"

        timestamp = self._get_timestamp()
        params = {
            "symbol": exchange_symbol,
            "side": side.value.upper(),
            "type": order_type.value.upper(),
            "quantity": str(quantity),
            "timestamp": timestamp,
        }

        if order_type == OrderType.LIMIT and price is not None:
            params["price"] = str(price)
            params["timeInForce"] = "GTC"

        query_string = urlencode(params)
        signature = self._generate_signature(query_string)
        params["signature"] = signature

        headers = {"X-MBX-APIKEY": self.api_key}

        async with session.post(url, params=params, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        return Order(
            order_id=str(data["orderId"]),
            symbol=symbol,
            side=side,
            order_type=order_type,
            price=Decimal(data.get("price", "0")),
            quantity=Decimal(data["origQty"]),
            filled_quantity=Decimal(data["executedQty"]),
            status=data["status"],
            timestamp=data["transactTime"],
            exchange=self.name,
        )

    async def get_order(self, symbol: str, order_id: str) -> Order:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/api/v3/order"

        timestamp = self._get_timestamp()
        params = {
            "symbol": exchange_symbol,
            "orderId": order_id,
            "timestamp": timestamp,
        }

        query_string = urlencode(params)
        signature = self._generate_signature(query_string)
        params["signature"] = signature

        headers = {"X-MBX-APIKEY": self.api_key}

        async with session.get(url, params=params, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        return Order(
            order_id=str(data["orderId"]),
            symbol=symbol,
            side=OrderSide.BUY if data["side"] == "BUY" else OrderSide.SELL,
            order_type=OrderType.MARKET if data["type"] == "MARKET" else OrderType.LIMIT,
            price=Decimal(data.get("price", "0")),
            quantity=Decimal(data["origQty"]),
            filled_quantity=Decimal(data["executedQty"]),
            status=data["status"],
            timestamp=data["time"],
            exchange=self.name,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/api/v3/order"

        timestamp = self._get_timestamp()
        params = {
            "symbol": exchange_symbol,
            "orderId": order_id,
            "timestamp": timestamp,
        }

        query_string = urlencode(params)
        signature = self._generate_signature(query_string)
        params["signature"] = signature

        headers = {"X-MBX-APIKEY": self.api_key}

        async with session.delete(url, params=params, headers=headers) as response:
            return response.status == 200
