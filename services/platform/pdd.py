from services.platform.base import PlatformAPI
from typing import Dict


class PDDAPI(PlatformAPI):
    """
    拼多多 API对接类（预留框架）

    使用前需要：
    1. 在 config.py 中配置 PDD_CLIENT_ID 和 PDD_CLIENT_SECRET
    2. 在拼多多开放平台注册应用并获取授权
    3. 参考拼多多开放平台文档
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.client_id = config.get('client_id', '')
        self.client_secret = config.get('client_secret', '')
        # API网关地址
        self.gateway_url = 'https://gw-api.pinduoduo.com/api/router'
        # 沙箱环境
        self.sandbox = config.get('sandbox', False)
        if self.sandbox:
            self.gateway_url = 'https://gw-api.pinduoduo.com/api/router'

    def authorize(self) -> str:
        """
        拼多多授权认证
        TODO: 实现OAuth2.0授权流程，获取access_token
        """
        raise NotImplementedError(
            '拼多多授权功能尚未实现。'
            '请参考拼多多开放平台文档完成OAuth2.0授权流程。'
            '需要在config.py中配置PDD_CLIENT_ID和PDD_CLIENT_SECRET。'
        )

    def get_orders(self, start_time: str, end_time: str, page: int = 1, page_size: int = 20) -> Dict:
        """
        获取拼多多订单列表
        TODO: 调用拼多多 pdd.ddz.order.list.get 接口
        :param start_time: 查询开始时间
        :param end_time: 查询结束时间
        :param page: 页码
        :param page_size: 每页数量
        """
        raise NotImplementedError(
            '拼多多订单获取功能尚未实现。'
            '请调用拼多多 pdd.ddz.order.list.get 接口获取订单列表。'
        )

    def get_order_detail(self, order_no: str) -> Dict:
        """
        获取拼多多订单详情
        TODO: 调用拼多多 pdd.ddz.order.detail.get 接口
        :param order_no: 拼多多订单号
        """
        raise NotImplementedError(
            '拼多多订单详情获取功能尚未实现。'
            '请调用拼多多 pdd.ddz.order.detail.get 接口获取订单详情。'
        )
