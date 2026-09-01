from flask import Blueprint, render_template, jsonify
from models import db
from models.product import Product
from models.warehouse import Warehouse
from models.stock_transaction import StockTransaction
from models.inventory import Inventory
from models.bank_account import BankAccount
from models.financial_transaction import FinancialTransaction
from models.accounts import AccountsReceivable, AccountsPayable
from models.product_batch import ProductBatch
from services.inventory_service import InventoryService
from utils.decorators import login_required
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    """仪表盘首页"""
    # 统计数据
    total_products = Product.query.count()
    total_inventory = db.session.query(db.func.sum(Inventory.quantity)).scalar() or 0

    # 低库存预警商品数
    low_stock_products = InventoryService.get_low_stock_products()
    low_stock_count = len(low_stock_products)

    # ======== 过期预警商品 ========
    # 查询180天内即将过期的批次
    today = datetime.now().date()
    expiry_warning_days = 180  # 从180天开始提醒
    expiry_date_threshold = today + timedelta(days=expiry_warning_days)

    expiring_batches = db.session.query(
        ProductBatch,
        Product.name.label('product_name'),
        Product.sku,
        Warehouse.name.label('warehouse_name')
    ).join(
        Product, ProductBatch.product_id == Product.id
    ).join(
        Warehouse, ProductBatch.warehouse_id == Warehouse.id
    ).filter(
        ProductBatch.expire_date.isnot(None),
        ProductBatch.expire_date <= expiry_date_threshold,
        ProductBatch.expire_date >= today,
        ProductBatch.remaining_quantity > 0,
        ProductBatch.status.in_(['active', 'partial'])
    ).order_by(
        ProductBatch.expire_date.asc()
    ).all()

    # 计算每个批次的剩余天数
    expiring_items = []
    for batch, product_name, sku, warehouse_name in expiring_batches:
        days_remaining = (batch.expire_date - today).days
        expiring_items.append({
            'batch': batch,
            'product_name': product_name,
            'sku': sku,
            'warehouse_name': warehouse_name,
            'days_remaining': days_remaining,
            'remaining_quantity': batch.remaining_quantity
        })

    # 按紧急程度分类
    urgent_expiring = [e for e in expiring_items if e['days_remaining'] <= 30]
    warning_expiring = [e for e in expiring_items if 30 < e['days_remaining'] <= 90]
    notice_expiring = [e for e in expiring_items if 90 < e['days_remaining'] <= 180]

    # 今日入库/出库数量
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_stock_in = db.session.query(db.func.sum(StockTransaction.quantity)).filter(
        StockTransaction.type == 'stock_in',
        StockTransaction.created_at >= today_start
    ).scalar() or 0

    today_stock_out = db.session.query(db.func.sum(StockTransaction.quantity)).filter(
        StockTransaction.type == 'stock_out',
        StockTransaction.created_at >= today_start
    ).scalar() or 0

    # ======== 财务统计 ========
    # 账户总余额
    total_balance = db.session.query(db.func.sum(BankAccount.current_balance)).filter(
        BankAccount.is_active == True
    ).scalar() or 0

    # 应收款总额
    total_receivable = db.session.query(db.func.sum(AccountsReceivable.pending_amount)).filter(
        AccountsReceivable.status.in_(['pending', 'partial'])
    ).scalar() or 0

    # 应付款总额
    total_payable = db.session.query(db.func.sum(AccountsPayable.pending_amount)).filter(
        AccountsPayable.status.in_(['pending', 'partial'])
    ).scalar() or 0

    # 本月收入/支出
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    
    month_income = db.session.query(db.func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.type == 'income',
        FinancialTransaction.transaction_date >= start_of_month.date(),
        FinancialTransaction.status == 'completed'
    ).scalar() or 0

    month_expense = db.session.query(db.func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.type == 'expense',
        FinancialTransaction.transaction_date >= start_of_month.date(),
        FinancialTransaction.status == 'completed'
    ).scalar() or 0

    # 最近10条出入库记录（使用 joinedload 预加载关联数据，避免 N+1 查询）
    recent_transactions = StockTransaction.query.options(
        joinedload(StockTransaction.product),
        joinedload(StockTransaction.warehouse)
    ).order_by(
        StockTransaction.created_at.desc()
    ).limit(10).all()

    # 近7天出入库趋势数据
    trend_labels = []
    trend_in_data = []
    trend_out_data = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        trend_labels.append(date.strftime('%m-%d'))

        day_in = db.session.query(db.func.sum(StockTransaction.quantity)).filter(
            StockTransaction.type == 'stock_in',
            StockTransaction.created_at >= date_start,
            StockTransaction.created_at <= date_end
        ).scalar() or 0
        trend_in_data.append(day_in)

        day_out = db.session.query(db.func.sum(StockTransaction.quantity)).filter(
            StockTransaction.type == 'stock_out',
            StockTransaction.created_at >= date_start,
            StockTransaction.created_at <= date_end
        ).scalar() or 0
        trend_out_data.append(day_out)

    # 仓库库存分布数据
    warehouse_stats = db.session.query(
        Warehouse.name,
        db.func.sum(Inventory.quantity)
    ).join(Inventory, Warehouse.id == Inventory.warehouse_id).group_by(
        Warehouse.id, Warehouse.name
    ).all()
    warehouse_labels = [ws[0] for ws in warehouse_stats]
    warehouse_data = [int(ws[1] or 0) for ws in warehouse_stats]

    return render_template('dashboard.html',
                           total_products=total_products,
                           total_inventory=total_inventory,
                           low_stock_count=low_stock_count,
                           today_stock_in=today_stock_in,
                           today_stock_out=today_stock_out,
                           recent_transactions=recent_transactions,
                           low_stock_products=low_stock_products,
                           expiring_items=expiring_items,
                           urgent_expiring=urgent_expiring,
                           warning_expiring=warning_expiring,
                           notice_expiring=notice_expiring,
                           expiry_warning_days=expiry_warning_days,
                           trend_labels=trend_labels,
                           trend_in_data=trend_in_data,
                           trend_out_data=trend_out_data,
                           warehouse_labels=warehouse_labels,
                           warehouse_data=warehouse_data,
                           total_balance=total_balance,
                           total_receivable=total_receivable,
                           total_payable=total_payable,
                           month_income=month_income,
                           month_expense=month_expense,
                           current_time=datetime.now().strftime('%Y年%m月%d日 %H:%M'))


@dashboard_bp.route('/reports')
@login_required
def reports():
    """数据报表页面"""
    # 库存统计
    total_products = Product.query.count()
    total_inventory = db.session.query(db.func.sum(Inventory.quantity)).scalar() or 0

    # 本月出入库统计
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)

    month_in = db.session.query(db.func.sum(StockTransaction.quantity)).filter(
        StockTransaction.type == 'stock_in',
        StockTransaction.created_at >= start_of_month
    ).scalar() or 0

    month_out = db.session.query(db.func.sum(StockTransaction.quantity)).filter(
        StockTransaction.type == 'stock_out',
        StockTransaction.created_at >= start_of_month
    ).scalar() or 0

    # 按分类统计商品数量
    category_stats = db.session.query(
        Product.category,
        db.func.count(Product.id)
    ).group_by(Product.category).all()

    # 近30天出入库趋势
    trend_labels = []
    trend_in_data = []
    trend_out_data = []
    for i in range(29, -1, -1):
        date = datetime.now() - timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        trend_labels.append(date.strftime('%m-%d'))

        day_in = db.session.query(db.func.sum(StockTransaction.quantity)).filter(
            StockTransaction.type == 'stock_in',
            StockTransaction.created_at >= date_start,
            StockTransaction.created_at <= date_end
        ).scalar() or 0
        trend_in_data.append(day_in)

        day_out = db.session.query(db.func.sum(StockTransaction.quantity)).filter(
            StockTransaction.type == 'stock_out',
            StockTransaction.created_at >= date_start,
            StockTransaction.created_at <= date_end
        ).scalar() or 0
        trend_out_data.append(day_out)

    # 商品分类饼图数据
    category_labels = [cs[0] or '未分类' for cs in category_stats]
    category_data = [cs[1] for cs in category_stats]

    # 仓库库存分布
    warehouse_stats = db.session.query(
        Warehouse.name,
        db.func.sum(Inventory.quantity)
    ).join(Inventory, Warehouse.id == Inventory.warehouse_id).group_by(
        Warehouse.id, Warehouse.name
    ).all()
    warehouse_labels = [ws[0] for ws in warehouse_stats]
    warehouse_data = [int(ws[1] or 0) for ws in warehouse_stats]

    # 出入库类型分布
    type_stats = db.session.query(
        StockTransaction.type,
        db.func.count(StockTransaction.id),
        db.func.sum(StockTransaction.quantity)
    ).filter(
        StockTransaction.created_at >= start_of_month
    ).group_by(StockTransaction.type).all()

    type_map = {
        'stock_in': '入库', 'stock_out': '出库',
        'transfer_in': '调入', 'transfer_out': '调出', 'adjustment': '盘点调整'
    }
    type_labels = [type_map.get(ts[0], ts[0]) for ts in type_stats]
    type_count_data = [ts[1] for ts in type_stats]
    type_qty_data = [int(ts[2] or 0) for ts in type_stats]

    return render_template('dashboard/reports.html',
                         total_products=total_products,
                         total_inventory=total_inventory,
                         month_in=month_in,
                         month_out=month_out,
                         category_stats=category_stats,
                         trend_labels=trend_labels,
                         trend_in_data=trend_in_data,
                         trend_out_data=trend_out_data,
                         category_labels=category_labels,
                         category_data=category_data,
                         warehouse_labels=warehouse_labels,
                         warehouse_data=warehouse_data,
                         type_labels=type_labels,
                         type_count_data=type_count_data,
                         type_qty_data=type_qty_data)
