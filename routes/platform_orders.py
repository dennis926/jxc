from flask import Blueprint, render_template
from utils.decorators import login_required

platform_orders_bp = Blueprint('platform_orders', __name__, url_prefix='/platform-orders')


@platform_orders_bp.route('/')
@login_required
def list():
    """平台订单列表（预留）"""
    return render_template('platform_orders/list.html')
