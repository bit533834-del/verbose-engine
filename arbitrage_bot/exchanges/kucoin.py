from decimal import Decimal
from typing import Optional
import base64
import json
import time

from .base import BaseExchange, OrderBook, Ticker, Order, OrderSide, OrderType


class KuCoinExchange(BaseExchange):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str = "",
        testnet: bool = False,
    ):
        super().__init__(api_key, api_secret, testnet)
        self.passphrase = passphrase

    @property
    def name(self) -> str:
        return "kucoin"

    @property
    def base_url(self) -> str:
        if self.testnet:
            return "https://openapi-sandbox.kucoin.com"
        return "https://api.kucoin.com"

    @property
    def maker_fee(self) -> Decimal:
        return Decimal("0.001")  # 0.1%

    @property
    def taker_fee(self) -> Decimal:
        return Decimal("0.001")  # 0.1%

    def normalize_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT to BTC-USDT."""
        return symbol.replace("/", "-")

    def denormalize_symbol(self, symbol: str) -> str:
        """Convert BTC-USDT to BTC/USDT."""
        return symbol.replace("-", "/")

    def _generate_signature(self, timestamp: str, method: str, endpoint: str, body: str = "") -> str:
        message = timestamp + method + endpoint + body
        return base64.b64encode(
            super()._generate_signature(message).encode("utf-8")
        ).decode("utf-8")

    def _get_auth_headers(self, method: str, endpoint: str, body: str = "") -> dict:
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, method, endpoint, body)

        passphrase_signature = base64.b64encode(
            super()._generate_signature(self.passphrase).encode("utf-8")
        ).decode("utf-8")

        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-PASSPHRASE": passphrase_signature,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        }

    async def get_ticker(self, symbol: str) -> Ticker:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/api/v1/market/orderbook/level1"

        params = {"symbol": exchange_symbol}

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        if data["code"] != "200000":
            raise Exception(f"KuCoin API error: {data.get('msg', 'Unknown error')}")

        ticker_data = data["data"]

        return Ticker(
            symbol=symbol,
            bid=Decimal(ticker_data["bestBid"]),
            ask=Decimal(ticker_data["bestAsk"]),
            last=Decimal(ticker_data["price"]),
            timestamp=int(ticker_data["time"]),
            exchange=self.name,
        )

    async def get_orderbook(self, symbol: str, limit: int = 10) -> OrderBook:
        session = await self._get_session()
        exchange_symbol = self.normalize_symbol(symbol)
        url = f"{self.base_url}/api/v1/market/orderbook/level2_20"

        params = {"symbol": exchange_symbol}

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        if data["code"] != "200000":
            raise Exception(f"KuCoin API error: {data.get('msg', 'Unknown error')}")

        orderbook = data["data"]
        bids = [(Decimal(price), Decimal(qty)) for price, qty in orderbook["bids"][:limit]]
        asks = [(Decimal(price), Decimal(qty)) for price, qty in orderbook["asks"][:limit]]

        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=int(orderbook["time"]),
            exchange=self.name,
        )

    async def get_balance(self, asset: str) -> Decimal:
        session = await self._get_session()
        endpoint = f"/api/v1/accounts?currency={asset}&type=trade"
        url = f"{self.base_url}{endpoint}"

        headers = self._get_auth_headers("GET", endpoint)

        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        if data["code"] != "200000":
            raise Exception(f"KuCoin API error: {data.get('msg', 'Unknown error')}")

        for account in data["data"]:
            if account["currency"] == asset:
                return Decimal(account["available"])

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
        endpoint = "/api/v1/orders"
        url = f"{self.base_url}{endpoint}"

        import uuid
        client_oid = str(uuid.uuid4())

        body = {
            "clientOid": client_oid,
            "symbol": exchange_symbol,
            "side": side.value,
            "type": order_type.value,
            "size": str(quantity),
        }

        if order_type == OrderType.LIMIT and price is not None:
            body["price"] = str(price)
            body["timeInForce"] = "GTC"

        body_str = json.dumps(body)
        headers = self._get_auth_headers("POST", endpoint, body_str)

        async with session.post(url, data=body_str, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        if data["code"] != "200000":
            raise Exception(f"KuCoin API error: {data.get('msg', 'Unknown error')}")

        return Order(
            order_id=data["data"]["orderId"],
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
        endpoint = f"/api/v1/orders/{order_id}"
        url = f"{self.base_url}{endpoint}"

        headers = self._get_auth_headers("GET", endpoint)

        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()

        if data["code"] != "200000":
            raise Exception(f"KuCoin API error: {data.get('msg', 'Unknown error')}")

        order_data = data["data"]

        return Order(
            order_id=order_data["id"],
            symbol=symbol,
            side=OrderSide.BUY if order_data["side"] == "buy" else OrderSide.SELL,
            order_type=OrderType.MARKET if order_data["type"] == "market" else OrderType.LIMIT,
            price=Decimal(order_data["price"]) if order_data["price"] else None,
            quantity=Decimal(order_data["size"]),
            filled_quantity=Decimal(order_data["dealSize"]),
            status="FILLED" if order_data["isActive"] is False else "ACTIVE",
            timestamp=int(order_data["createdAt"]),
            exchange=self.name,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        session = await self._get_session()
        endpoint = f"/api/v1/orders/{order_id}"
        url = f"{self.base_url}{endpoint}"

        headers = self._get_auth_headers("DELETE", endpoint)

        async with session.delete(url, headers=headers) as response:
            data = await response.json()
            return data["code"] == "200000"
