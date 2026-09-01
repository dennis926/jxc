from services.platform.base import PlatformAPI
from typing import Dict


class TaobaoAPI(PlatformAPI):
    """
    淘宝/天猫 API对接类（预留框架）

    使用前需要：
    1. 在 config.py 中配置 TAOBAO_APP_KEY 和 TAOBAO_APP_SECRET
    2. 在淘宝开放平台注册应用并获取授权
    3. 安装淘宝SDK: pip install top-sdk
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.app_key = config.get('app_key', '')
        self.app_secret = config.get('app_secret', '')
        self.session = config.get('session', '')
        # API网关地址
        self.gateway_url = 'https://eco.taobao.com/router/rest'
        # 沙箱环境
        self.sandbox = config.get('sandbox', False)
        if self.sandbox:
            self.gateway_url = 'https://eco.taobao.com/router/rest'

    def authorize(self) -> str:
        """
        淘宝授权认证
        TODO: 实现OAuth2.0授权流程，获取access_token
        """
        raise NotImplementedError(
            '淘宝授权功能尚未实现。'
            '请参考淘宝开放平台文档完成OAuth2.0授权流程。'
            '需要在config.py中配置TAOBAO_APP_KEY和TAOBAO_APP_SECRET。'
        )

    def get_orders(self, start_time: str, end_time: str, page: int = 1, page_size: int = 20) -> Dict:
        """
        获取淘宝订单列表
        TODO: 调用淘宝 taobao.trades.sold.get 接口
        :param start_time: 查询开始时间
        :param end_time: 查询结束时间
        :param page: 页码
        :param page_size: 每页数量（最大100）
        """
        raise NotImplementedError(
            '淘宝订单获取功能尚未实现。'
            '请使用淘宝SDK调用 taobao.trades.sold.get 接口获取订单列表。'
        )

    def get_order_detail(self, order_no: str) -> Dict:
        """
        获取淘宝订单详情
        TODO: 调用淘宝 taobao.trade.fullinfo.get 接口
        :param order_no: 淘宝订单号
        """
        raise NotImplementedError(
            '淘宝订单详情获取功能尚未实现。'
            '请使用淘宝SDK调用 taobao.trade.fullinfo.get 接口获取订单详情。'
        )
