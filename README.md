card-content-box

post-url 、 post-content
div.feed-content-text>a

评论按钮
.footer-function-grid .comments-icon svg



docker run -d \
--name mariadb \
--restart unless-stopped \
-p 3306:3306 \
-v mariadb_data:/var/lib/mysql \
-e MARIADB_ROOT_PASSWORD='YourStrongRootPassword!' \
-e MARIADB_DATABASE=crypto_market_db \
-e MARIADB_USER=trader \
-e MARIADB_PASSWORD='YourStrongUserPassword!trader' \
--memory="1g" \
--cpus="1" \
mariadb:12

```sql
CREATE TABLE top_gainers (
                             id BIGINT AUTO_INCREMENT PRIMARY KEY,
                             fetched_at_utc DATETIME NOT NULL COMMENT '抓取时间（UTC，整点）',
                             rank TINYINT NOT NULL COMMENT '排名 1-100',
                             symbol VARCHAR(20) NOT NULL COMMENT '交易对 symbol',
                             base VARCHAR(10) NOT NULL COMMENT '基础币种',
                             quote VARCHAR(10) NOT NULL COMMENT '计价币种',
                             change_percent DECIMAL(10,4) NOT NULL COMMENT '涨跌幅百分比',
                             last_price DECIMAL(20,8) NOT NULL COMMENT '最新价格',
                             open_price DECIMAL(20,8) NOT NULL COMMENT '开盘价',
                             high_price DECIMAL(20,8) NOT NULL COMMENT '最高价',
                             low_price DECIMAL(20,8) NOT NULL COMMENT '最低价',
                             volume DECIMAL(20,8) NOT NULL COMMENT '成交量（基础币）',
                             quote_volume DECIMAL(20,8) NOT NULL COMMENT '成交额（计价币）',
                             trade_count BIGINT NOT NULL DEFAULT 0 COMMENT '交易次数',
                             updated_at_ms BIGINT NOT NULL COMMENT 'ticker 更新时间戳（毫秒）',
                             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                             INDEX idx_fetched_at (fetched_at_utc),
                             INDEX idx_symbol (symbol),
                             INDEX idx_quote (quote),
                             INDEX idx_rank (rank),
                             INDEX idx_fetched_quote (fetched_at_utc, quote)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='涨幅榜数据';
```