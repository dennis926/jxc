# 订单同步服务（预留）
# 后续对接各平台API后，在此实现订单自动同步逻辑


class OrderSyncService:
    """订单同步服务（预留框架）"""

    @staticmethod
    def sync_orders(platform: str):
        """
        同步指定平台的订单
        :param platform: 平台名称 (taobao/jd/douyin/pdd)
        """
        raise NotImplementedError(f'平台 {platform} 的订单同步功能尚未实现')

    @staticmethod
    def sync_all_platforms():
        """同步所有平台的订单"""
        raise NotImplementedError('订单同步功能尚未实现')
