import math

def get_decimal_places(num: int | float) -> int:
    """
    获取数字的小数位数
    :param num: 输入的数字（int/float）
    :return: 小数位数（int），整数返回0
    """
    num_str = str(float(num))
    if '.' in num_str:
        decimal_part = num_str.split('.')[1].rstrip('0')
        return len(decimal_part) if decimal_part else 0
    return 0


def truncate_decimal(num: int | float, decimals: int = 6) -> float:
    """
    截断数值到指定小数位数（不四舍五入）
    :param num: 原始数值
    :param decimals: 保留的小数位数，默认6位
    :return: 截断后的数值
    """
    if not isinstance(num, (int, float)):
        raise TypeError("输入必须是整数或浮点数")
    factor = 10 ** decimals
    return math.trunc(num * factor) / factor
