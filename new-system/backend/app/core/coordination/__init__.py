"""协同检测模块（CooRTweet Python 重写）。

将 CooRTweet R 包的核心算法用 pandas + networkx 重新实现：
- detector: detect_groups / flag_speed_share
- network:  generate_coordinated_network
- stats:    account_stats / group_stats
"""

from app.core.coordination.detector import detect_groups, flag_speed_share
from app.core.coordination.network import generate_coordinated_network
from app.core.coordination.stats import account_stats, group_stats

__all__ = [
    "detect_groups",
    "flag_speed_share",
    "generate_coordinated_network",
    "account_stats",
    "group_stats",
]
