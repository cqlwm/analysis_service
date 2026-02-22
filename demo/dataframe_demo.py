import pandas as pd

# 模拟你的变量和数据（方便测试）
_ALPHA_TREND = 'alpha_trend'
_CLOSE = 'close'
df = pd.DataFrame({
    _ALPHA_TREND: [1.2, 3.4, 5.6],
    _CLOSE: [10.1, 20.2, 30.3]
})

# 修正后的代码
current = df.iloc[-1]  # 获取最后一行的Series
at_val = float(df.at[len(df) - 1, _ALPHA_TREND])  # 用.loc明确按标签索引
close = float(current.loc[_CLOSE])

print(f"alpha_trend值: {at_val}")
print(f"close值: {close}")