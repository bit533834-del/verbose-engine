from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional
import aiohttp
import hashlib
import hmac
import time


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class Ticker:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    timestamp: int
    exchange: str


@dataclass
class OrderBook:
    symbol: str
    bids: list[tuple[Decimal, Decimal]]  # (price, quantity)
    asks: list[tuple[Decimal, Decimal]]  # (price, quantity)
    timestamp: int
    exchange: str


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    status: str
    timestamp: int
    exchange: str


class BaseExchange(ABC):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        pass

    @property
    @abstractmethod
    def maker_fee(self) -> Decimal:
        pass

    @property
    @abstractmethod
    def taker_fee(self) -> Decimal:
        pass

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _generate_signature(self, message: str) -> str:
        return hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000)

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 10) -> OrderBook:
        pass

    @abstractmethod
    async def get_balance(self, asset: str) -> Decimal:
        pass

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
    ) -> Order:
        pass

    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> Order:
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        pass

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """Convert standard symbol (BTC/USDT) to exchange-specific format."""
        pass

    @abstractmethod
    def denormalize_symbol(self, symbol: str) -> str:
        """Convert exchange-specific symbol to standard format (BTC/USDT)."""
        pass
