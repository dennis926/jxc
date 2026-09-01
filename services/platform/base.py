from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class PlatformAPI(ABC):
    """
    平台API基类
    所有平台API对接类需继承此基类并实现抽象方法
    """

    def __init__(self, config: dict):
        """
        初始化平台API
        :param config: 平台配置信息，包含app_key, app_secret等
        """
        self.config = config
        self.access_token = config.get('access_token', '')

    @abstractmethod
    def authorize(self) -> str:
        """
        授权认证
        :return: access_token
        """
        pass

    @abstractmethod
    def get_orders(self, start_time: str, end_time: str, page: int = 1, page_size: int = 20) -> Dict:
        """
        获取订单列表
        :param start_time: 开始时间 (格式: YYYY-MM-DD HH:MM:SS)
        :param end_time: 结束时间
        :param page: 页码
        :param page_size: 每页数量
        :return: 订单列表数据
        """
        pass

    @abstractmethod
    def get_order_detail(self, order_no: str) -> Dict:
        """
        获取订单详情
        :param order_no: 平台订单号
        :return: 订单详情数据
        """
        pass

    def refresh_token(self) -> str:
        """
        刷新access_token（可选实现）
        :return: 新的access_token
        """
        raise NotImplementedError('Token刷新功能未实现')

    def parse_order_data(self, raw_data: Dict) -> Dict:
        """
        解析平台原始订单数据为统一格式（可选重写）
        :param raw_data: 平台原始数据
        :return: 统一格式的订单数据
        """
        return {
            'platform_order_no': raw_data.get('order_no', ''),
            'order_status': raw_data.get('status', ''),
            'buyer_info': raw_data.get('buyer', {}),
            'total_amount': raw_data.get('total_amount', 0),
            'shipping_fee': raw_data.get('shipping_fee', 0),
            'payment': raw_data.get('payment', 0),
            'order_time': raw_data.get('order_time', ''),
            'pay_time': raw_data.get('pay_time', ''),
            'items': raw_data.get('items', [])
        }
