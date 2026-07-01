"""传播监控子包：趋势预测、源头追溯、范围估计。"""

# 保留旧模块的公共接口
from app.core.propagation_legacy import build_propagation_graph

__all__ = ["build_propagation_graph"]
