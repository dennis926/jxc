from services.platform.base import PlatformAPI
from typing import Dict


class DouyinAPI(PlatformAPI):
    """
    抖音/抖音电商 API对接类（预留框架）

    使用前需要：
    1. 在 config.py 中配置 DOUYIN_APP_KEY 和 DOUYIN_APP_SECRET
    2. 在抖音开放平台注册应用并获取授权
    3. 参考抖音电商开放平台文档
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_key = config.get('app_key', '')
        self.app_secret = config.get('app_secret', '')
        # API网关地址
        self.gateway_url = 'https://openapi-fxg.jinritemai.com'
        # 沙箱环境
        self.sandbox = config.get('sandbox', False)
        if self.sandbox:
            self.gateway_url = 'https://openapi-fxg.jinritemai.com'

    def authorize(self) -> str:
        """
        抖音授权认证
        TODO: 实现OAuth2.0授权流程，获取access_token
        """
        raise NotImplementedError(
            '抖音授权功能尚未实现。'
            '请参考抖音电商开放平台文档完成OAuth2.0授权流程。'
            '需要在config.py中配置DOUYIN_APP_KEY和DOUYIN_APP_SECRET。'
        )

    def get_orders(self, start_time: str, end_time: str, page: int = 1, page_size: int = 20) -> Dict:
        """
        获取抖音订单列表
        TODO: 调用抖音 order.list 接口
        :param start_time: 查询开始时间
        :param end_time: 查询结束时间
        :param page: 页码
        :param page_size: 每页数量
        """
        raise NotImplementedError(
            '抖音订单获取功能尚未实现。'
            '请调用抖音 order.list 接口获取订单列表。'
        )

    def get_order_detail(self, order_no: str) -> Dict:
        """
        获取抖音订单详情
        TODO: 调用抖音 order.detail 接口
        :param order_no: 抖音订单号
        """
        raise NotImplementedError(
            '抖音订单详情获取功能尚未实现。'
            '请调用抖音 order.detail 接口获取订单详情。'
        )
