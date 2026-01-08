import os
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class ExchangeConfig(BaseModel):
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""  # Only for KuCoin
    enabled: bool = True
    testnet: bool = False


class Config(BaseModel):
    # Exchange configurations
    binance: ExchangeConfig = Field(default_factory=ExchangeConfig)
    bybit: ExchangeConfig = Field(default_factory=ExchangeConfig)
    kucoin: ExchangeConfig = Field(default_factory=ExchangeConfig)

    # Trading configuration
    min_spread_percent: Decimal = Decimal("0.5")
    trade_amount_usdt: Decimal = Decimal("100")
    trading_pairs: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    scan_interval_seconds: int = 5

    # Bot settings
    dry_run: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "Config":
        """Load configuration from environment variables."""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        trading_pairs_str = os.getenv("TRADING_PAIRS", "BTC/USDT,ETH/USDT")
        trading_pairs = [p.strip() for p in trading_pairs_str.split(",")]

        return cls(
            binance=ExchangeConfig(
                api_key=os.getenv("BINANCE_API_KEY", ""),
                api_secret=os.getenv("BINANCE_API_SECRET", ""),
                enabled=os.getenv("BINANCE_ENABLED", "true").lower() == "true",
                testnet=os.getenv("BINANCE_TESTNET", "false").lower() == "true",
            ),
            bybit=ExchangeConfig(
                api_key=os.getenv("BYBIT_API_KEY", ""),
                api_secret=os.getenv("BYBIT_API_SECRET", ""),
                enabled=os.getenv("BYBIT_ENABLED", "true").lower() == "true",
                testnet=os.getenv("BYBIT_TESTNET", "false").lower() == "true",
            ),
            kucoin=ExchangeConfig(
                api_key=os.getenv("KUCOIN_API_KEY", ""),
                api_secret=os.getenv("KUCOIN_API_SECRET", ""),
                passphrase=os.getenv("KUCOIN_API_PASSPHRASE", ""),
                enabled=os.getenv("KUCOIN_ENABLED", "true").lower() == "true",
                testnet=os.getenv("KUCOIN_TESTNET", "false").lower() == "true",
            ),
            min_spread_percent=Decimal(os.getenv("MIN_SPREAD_PERCENT", "0.5")),
            trade_amount_usdt=Decimal(os.getenv("TRADE_AMOUNT_USDT", "100")),
            trading_pairs=trading_pairs,
            scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "5")),
            dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def get_enabled_exchanges(self) -> list[str]:
        """Get list of enabled exchange names."""
        enabled = []
        if self.binance.enabled and self.binance.api_key:
            enabled.append("binance")
        if self.bybit.enabled and self.bybit.api_key:
            enabled.append("bybit")
        if self.kucoin.enabled and self.kucoin.api_key:
            enabled.append("kucoin")
        return enabled
