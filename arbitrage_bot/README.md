# Crypto Arbitrage Bot

Арбитражный бот для криптовалютных бирж. Сканирует цены на нескольких биржах и автоматически исполняет сделки при обнаружении выгодного спреда.

## Поддерживаемые биржи

- **Binance** (включая testnet)
- **Bybit** (включая testnet)
- **KuCoin** (включая sandbox)

## Установка

```bash
cd arbitrage_bot
pip install -r requirements.txt
```

## Настройка

1. Скопируйте файл `.env.example` в `.env`:

```bash
cp .env.example .env
```

2. Отредактируйте `.env` файл, добавив ваши API ключи:

```env
# Binance API Keys
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
BINANCE_TESTNET=true  # Использовать testnet

# Bybit API Keys
BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret
BYBIT_TESTNET=true

# KuCoin API Keys
KUCOIN_API_KEY=your_kucoin_api_key
KUCOIN_API_SECRET=your_kucoin_api_secret
KUCOIN_API_PASSPHRASE=your_kucoin_passphrase
KUCOIN_TESTNET=true

# Bot Configuration
MIN_SPREAD_PERCENT=0.5       # Минимальный спред для исполнения сделки
TRADE_AMOUNT_USDT=100        # Сумма сделки в USDT
TRADING_PAIRS=BTC/USDT,ETH/USDT  # Торговые пары
SCAN_INTERVAL_SECONDS=5      # Интервал сканирования
DRY_RUN=true                 # Режим симуляции (без реальных сделок)
LOG_LEVEL=INFO               # Уровень логирования
```

## Запуск

### Режим симуляции (рекомендуется для начала)

```bash
python -m arbitrage_bot
```

По умолчанию `DRY_RUN=true`, бот будет только логировать найденные возможности без исполнения реальных сделок.

### Боевой режим

```bash
DRY_RUN=false python -m arbitrage_bot
```

**ВНИМАНИЕ:** В боевом режиме бот будет исполнять реальные сделки!

## Архитектура

```
arbitrage_bot/
├── __init__.py          # Экспорт модулей
├── __main__.py          # Точка входа
├── bot.py               # Основной класс бота
├── trade_executor.py    # Исполнение сделок
├── exchanges/
│   ├── __init__.py
│   ├── base.py          # Базовый класс биржи
│   ├── binance.py       # Binance API
│   ├── bybit.py         # Bybit API
│   └── kucoin.py        # KuCoin API
└── utils/
    ├── __init__.py
    ├── config.py        # Конфигурация
    ├── logger.py        # Настройка логирования
    └── spread_calculator.py  # Расчёт спреда
```

## Алгоритм работы

1. **Сканирование цен** — Бот асинхронно запрашивает цены со всех бирж для указанных торговых пар.

2. **Расчёт спреда** — Для каждой пары бирж рассчитывается спред с учётом комиссий:
   - Находится биржа с минимальной ценой ask (покупка)
   - Находится биржа с максимальной ценой bid (продажа)
   - Вычисляется чистая прибыль после комиссий

3. **Исполнение сделки** — Если спред превышает порог:
   - Проверяется достаточность баланса
   - Одновременно отправляются ордера на покупку и продажу

4. **Мониторинг** — Цикл повторяется каждые N секунд.

## Тестирование

Рекомендуется начать тестирование с:

1. **Testnet/Sandbox** — Используйте тестовые сети бирж
2. **Режим DRY_RUN** — Запустите в режиме симуляции
3. **Малые суммы** — Начните с минимальных сумм сделок

## Ограничения и риски

- **Slippage** — Цена может измениться между получением котировки и исполнением ордера
- **Ликвидность** — На низколиквидных парах может не хватить объёма
- **Задержки API** — Сетевые задержки могут влиять на прибыльность
- **Комиссии** — Учитываются только торговые комиссии, не учитываются комиссии за вывод

## API Ключи

### Binance
1. Войдите в [Binance](https://www.binance.com/)
2. Перейдите в API Management
3. Создайте новый API ключ с разрешениями на торговлю

### Bybit
1. Войдите в [Bybit](https://www.bybit.com/)
2. Перейдите в API Management
3. Создайте новый API ключ

### KuCoin
1. Войдите в [KuCoin](https://www.kucoin.com/)
2. Перейдите в API Management
3. Создайте API ключ (запомните passphrase!)

## Лицензия

MIT
