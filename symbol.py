from dataclasses import dataclass


QUOTE_CURRENCIES = ('USDT', 'USDC', 'BUSD', 'USD', 'EUR', 'GBP', 'BTC', 'ETH', 'BNB')


@dataclass(frozen=True)
class Symbol:
    """交易对符号类，统一处理各种格式的 symbol 字符串"""
    base: str
    quote: str

    @classmethod
    def parse(cls, s: str) -> "Symbol":
        """
        从各种格式解析 Symbol:
        - BTCUSDT -> base=BTC, quote=USDT
        - BTCUSDC -> base=BTC, quote=USDC
        - BTC/USDT -> base=BTC, quote=USDT
        - BTC/USDT:USDT -> base=BTC, quote=USDT
        - BTC -> base=BTC, quote=USDT (默认)
        """
        s = s.upper().strip()
        
        if '/' in s:
            parts = s.split('/')
            base = parts[0]
            quote = parts[1].split(':')[0]
        else:
            for quote in QUOTE_CURRENCIES:
                if s.endswith(quote):
                    base = s[:-len(quote)]
                    break
            else:
                base = s
                quote = 'USDT'
        
        return cls(base=base, quote=quote)

    @property
    def clean(self) -> str:
        """清理后的基础币种: BTC"""
        return self.base

    @property
    def full(self) -> str:
        """完整交易对: BTCUSDT"""
        return f"{self.base}{self.quote}"

    @property
    def ccxt(self) -> str:
        """ccxt 格式: BTC/USDT"""
        return f"{self.base}/{self.quote}"

    @property
    def with_prefix(self) -> str:
        """带前缀格式: $BTC"""
        return f"${self.base}"

    def __str__(self) -> str:
        return self.full

    def __repr__(self) -> str:
        return f"Symbol(base={self.base!r}, quote={self.quote!r})"
