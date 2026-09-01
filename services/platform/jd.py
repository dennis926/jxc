from services.platform.base import PlatformAPI
from typing import Dict


class JDAPI(PlatformAPI):
    """
    京东 API对接类（预留框架）

    使用前需要：
    1. 在 config.py 中配置 JD_APP_KEY 和 JD_APP_SECRET
    2. 在京东开放平台注册应用并获取授权
    3. 参考京东宙斯开放平台文档
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_key = config.get('app_key', '')
        self.app_secret = config.get('app_secret', '')
        # API网关地址
        self.gateway_url = 'https://api.jd.com/routerjson'
        # 沙箱环境
        self.sandbox = config.get('sandbox', False)
        if self.sandbox:
            self.gateway_url = 'https://api.jd.com/routerjson'

    def authorize(self) -> str:
        """
        京东授权认证
        TODO: 实现OAuth2.0授权流程，获取access_token
        """
        raise NotImplementedError(
            '京东授权功能尚未实现。'
            '请参考京东宙斯开放平台文档完成OAuth2.0授权流程。'
            '需要在config.py中配置JD_APP_KEY和JD_APP_SECRET。'
        )

    def get_orders(self, start_time: str, end_time: str, page: int = 1, page_size: int = 20) -> Dict:
        """
        获取京东订单列表
        TODO: 调用京东 jd.order.search 接口
        :param start_time: 查询开始时间
        :param end_time: 查询结束时间
        :param page: 页码
        :param page_size: 每页数量
        """
        raise NotImplementedError(
            '京东订单获取功能尚未实现。'
            '请调用京东 jd.order.search 接口获取订单列表。'
        )

    def get_order_detail(self, order_no: str) -> Dict:
        """
        获取京东订单详情
        TODO: 调用京东 jd.order.detail 接口
        :param order_no: 京东订单号
        """
        raise NotImplementedError(
            '京东订单详情获取功能尚未实现。'
            '请调用京东 jd.order.detail 接口获取订单详情。'
        )
