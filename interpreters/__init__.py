"""解释器模块 - 将结构化指标数据转换为自然语言"""
from interpreters.base import BaseInterpreter, InterpreterOutput, InterpreterRegistry, DefaultInterpreter

# 导出常用类
__all__ = [
    'BaseInterpreter',
    'InterpreterOutput',
    'InterpreterRegistry',
    'DefaultInterpreter',
]

# 自动初始化所有解释器
def _init_interpreters():
    from interpreters.rsi_interpreter import RSIInterpreter
    from interpreters.macd_interpreter import MACDInterpreter
    from interpreters.bollinger_interpreter import BollingerInterpreter
    from interpreters.ma_interpreter import MAInterpreter
    from interpreters.atr_interpreter import ATRInterpreter
    from interpreters.mfi_interpreter import MFIInterpreter
    from interpreters.alpha_trend_interpreter import AlphaTrendInterpreter
    from interpreters.volume_interpreter import VolumeInterpreter
    
    # 注册所有解释器
    InterpreterRegistry.register(RSIInterpreter())
    InterpreterRegistry.register(MACDInterpreter())
    InterpreterRegistry.register(BollingerInterpreter())
    InterpreterRegistry.register(MAInterpreter())
    InterpreterRegistry.register(ATRInterpreter())
    InterpreterRegistry.register(MFIInterpreter())
    InterpreterRegistry.register(AlphaTrendInterpreter())
    InterpreterRegistry.register(VolumeInterpreter())
    
    # 注册默认解释器
    InterpreterRegistry.register(DefaultInterpreter())


# 按需初始化
_init_interpreters()
