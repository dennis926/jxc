from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from models import db
from models.bank_account import BankAccount
from models.financial_transaction import FinancialTransaction
from models.accounts import AccountsReceivable, AccountsPayable
from models.customer import Customer
from models.supplier import Supplier
from models.stock_transaction import StockTransaction
from models.purchase_order import PurchaseOrder
from models.warehouse import Warehouse
from models.product import Product
from utils.decorators import login_required
from services.log_service import LogService
from utils.excel_export import export_to_excel
from sqlalchemy import or_, func, and_
from datetime import datetime, timedelta
from decimal import Decimal

finance_bp = Blueprint('finance', __name__, url_prefix='/finance')


# ============ 账户管理 ============

@finance_bp.route('/accounts')
@login_required
def accounts():
    """账户列表"""
    accounts = BankAccount.query.filter_by(is_active=True).order_by(BankAccount.created_at.desc()).all()
    return render_template('finance/accounts/list.html', accounts=accounts)


@finance_bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
def add_account():
    """添加账户"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        acc_type = request.form.get('type', 'bank').strip()
        account_no = request.form.get('account_no', '').strip()
        opening_balance = request.form.get('opening_balance', 0)
        remark = request.form.get('remark', '').strip()

        try:
            opening_balance = Decimal(opening_balance) if opening_balance else Decimal('0')
        except:
            opening_balance = Decimal('0')

        account = BankAccount(
            name=name,
            code=code,
            type=acc_type,
            account_no=account_no,
            opening_balance=opening_balance,
            current_balance=opening_balance,
            remark=remark
        )

        db.session.add(account)
        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='create',
            module='finance',
            description=f'添加账户: {name}',
            reference_type='bank_account',
            reference_id=account.id
        )

        return jsonify({'success': True, 'message': '添加成功'})

    return render_template('finance/accounts/add.html')


@finance_bp.route('/accounts/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_account(id):
    """编辑账户"""
    account = BankAccount.query.get_or_404(id)

    if request.method == 'POST':
        account.name = request.form.get('name', '').strip()
        account.code = request.form.get('code', '').strip()
        account.type = request.form.get('type', 'bank').strip()
        account.account_no = request.form.get('account_no', '').strip()
        account.remark = request.form.get('remark', '').strip()

        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='finance',
            description=f'编辑账户: {account.name}',
            reference_type='bank_account',
            reference_id=account.id
        )

        return jsonify({'success': True, 'message': '更新成功'})

    return render_template('finance/accounts/edit.html', account=account)


@finance_bp.route('/accounts/delete/<int:id>', methods=['POST'])
@login_required
def delete_account(id):
    """删除账户"""
    account = BankAccount.query.get_or_404(id)

    account.is_active = False
    db.session.commit()

    LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='delete',
            module='finance',
            description=f'删除账户: {account.name}',
            reference_type='bank_account',
            reference_id=account.id
        )

    return jsonify({'success': True, 'message': '删除成功'})


# ============ 收支记录 ============

@finance_bp.route('/transactions')
@login_required
def transactions():
    """收支记录列表"""
    page = request.args.get('page', 1, type=int)
    tx_type = request.args.get('type', '').strip()
    category = request.args.get('category', '').strip()
    account_id = request.args.get('account_id', 0, type=int)
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip()

    query = FinancialTransaction.query

    # 类型筛选
    if tx_type:
        query = query.filter(FinancialTransaction.type == tx_type)

    # 分类筛选
    if category:
        query = query.filter(FinancialTransaction.category == category)

    # 账户筛选
    if account_id:
        query = query.filter(FinancialTransaction.account_id == account_id)

    # 日期范围筛选
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(FinancialTransaction.transaction_date >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(FinancialTransaction.transaction_date <= end_dt)
        except ValueError:
            pass

    # 搜索（单号、对方单位、备注）
    if search:
        query = query.filter(
            or_(
                FinancialTransaction.transaction_no.like(f'%{search}%'),
                FinancialTransaction.counterparty_name.like(f'%{search}%'),
                FinancialTransaction.remark.like(f'%{search}%')
            )
        )

    pagination = query.order_by(FinancialTransaction.transaction_date.desc(), FinancialTransaction.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    # 获取所有账户
    accounts = BankAccount.query.filter_by(is_active=True).all()

    # 收支分类选项
    income_categories = ['销售收入', '采购退款', '利息收入', '其他收入']
    expense_categories = ['采购支出', '运营费用', '工资支出', '税费支出', '其他支出']

    return render_template('finance/transactions/list.html',
                           transactions=pagination.items,
                           pagination=pagination,
                           accounts=accounts,
                           income_categories=income_categories,
                           expense_categories=expense_categories,
                           tx_type=tx_type,
                           category=category,
                           account_id=account_id,
                           start_date=start_date,
                           end_date=end_date,
                           search=search)


@finance_bp.route('/transactions/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    """添加收支记录"""
    if request.method == 'POST':
        tx_type = request.form.get('type', '').strip()
        category = request.form.get('category', '').strip()
        amount = request.form.get('amount', 0)
        account_id = request.form.get('account_id', type=int)
        direction = request.form.get('direction', 'in').strip()
        counterparty = request.form.get('counterparty_name', '').strip()
        payment_method = request.form.get('payment_method', '').strip()
        transaction_date = request.form.get('transaction_date', '').strip()
        remark = request.form.get('remark', '').strip()

        try:
            amount = Decimal(amount)
        except:
            return jsonify({'success': False, 'message': '金额格式错误'})

        if not category:
            return jsonify({'success': False, 'message': '请选择收支分类'})

        if not transaction_date:
            return jsonify({'success': False, 'message': '请选择交易日期'})

        try:
            tx_date = datetime.strptime(transaction_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': '日期格式错误'})

        transaction = FinancialTransaction(
            transaction_no=FinancialTransaction.generate_transaction_no(tx_type),
            type=tx_type,
            category=category,
            amount=amount,
            account_id=account_id,
            direction=direction,
            counterparty_name=counterparty,
            payment_method=payment_method,
            transaction_date=tx_date,
            operator=session.get('real_name', session.get('username', '')),
            remark=remark
        )

        # 更新账户余额
        if account_id:
            account = BankAccount.query.get(account_id)
            if account:
                if direction == 'in':
                    account.current_balance += amount
                else:
                    account.current_balance -= amount

        db.session.add(transaction)
        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='create',
            module='finance',
            description=f'添加收支记录: {transaction.transaction_no} {category} ¥{amount}',
            reference_type='financial_transaction',
            reference_id=transaction.id,
            reference_no=transaction.transaction_no
        )

        return jsonify({'success': True, 'message': '添加成功'})

    accounts = BankAccount.query.filter_by(is_active=True).all()
    return render_template('finance/transactions/add.html', accounts=accounts)


@finance_bp.route('/transactions/delete/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    """删除收支记录"""
    transaction = FinancialTransaction.query.get_or_404(id)

    # 恢复账户余额
    if transaction.account_id and transaction.status == 'completed':
        account = BankAccount.query.get(transaction.account_id)
        if account:
            if transaction.direction == 'in':
                account.current_balance -= transaction.amount
            else:
                account.current_balance += transaction.amount

    transaction.status = 'cancelled'
    db.session.commit()

    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='delete',
        module='finance',
        description=f'删除收支记录: {transaction.transaction_no}',
        reference_type='financial_transaction',
        reference_id=transaction.id,
        reference_no=transaction.transaction_no
    )

    return jsonify({'success': True, 'message': '删除成功'})


# ============ 应收管理 ============

@finance_bp.route('/receivables')
@login_required
def receivables():
    """应收款列表"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '').strip()
    customer_name = request.args.get('customer_name', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = AccountsReceivable.query

    # 状态筛选
    if status:
        query = query.filter(AccountsReceivable.status == status)

    # 客户名称搜索
    if customer_name:
        query = query.filter(
            or_(
                AccountsReceivable.customer_name.like(f'%{customer_name}%'),
                AccountsReceivable.customer_address.like(f'%{customer_name}%')
            )
        )

    # 日期范围筛选
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AccountsReceivable.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(AccountsReceivable.created_at <= end_dt)
        except ValueError:
            pass

    pagination = query.order_by(AccountsReceivable.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    # 统计数据
    total_amount = db.session.query(func.sum(AccountsReceivable.amount)).filter(
        AccountsReceivable.status != 'written_off'
    ).scalar() or Decimal('0')

    total_pending = db.session.query(func.sum(AccountsReceivable.pending_amount)).filter(
        AccountsReceivable.status.in_(['pending', 'partial'])
    ).scalar() or Decimal('0')

    return render_template('finance/receivables/list.html',
                           receivables=pagination.items,
                           pagination=pagination,
                           status=status,
                           customer_name=customer_name,
                           start_date=start_date,
                           end_date=end_date,
                           total_amount=total_amount,
                           total_pending=total_pending)


@finance_bp.route('/receivables/collect', methods=['GET', 'POST'])
@login_required
def collect_receivable():
    """收款"""
    if request.method == 'POST':
        receivable_id = request.form.get('receivable_id', type=int)
        collect_amount = request.form.get('collect_amount', 0)
        account_id = request.form.get('account_id', type=int)
        payment_method = request.form.get('payment_method', '').strip()
        remark = request.form.get('remark', '').strip()

        try:
            collect_amount = Decimal(collect_amount)
        except:
            return jsonify({'success': False, 'message': '金额格式错误'})

        receivable = AccountsReceivable.query.get(receivable_id)
        if not receivable:
            return jsonify({'success': False, 'message': '应收记录不存在'})

        if collect_amount > receivable.pending_amount:
            return jsonify({'success': False, 'message': '收款金额不能超过待收金额'})

        # 更新应收记录
        receivable.paid_amount += collect_amount
        receivable.pending_amount -= collect_amount

        if receivable.pending_amount <= 0:
            receivable.status = 'received'
        else:
            receivable.status = 'partial'

        # 生成收款记录
        transaction = FinancialTransaction(
            transaction_no=FinancialTransaction.generate_transaction_no('income'),
            type='income',
            category='销售收入',
            amount=collect_amount,
            account_id=account_id,
            direction='in',
            related_type='receivable',
            related_id=receivable.id,
            counterparty_name=receivable.customer_name,
            payment_method=payment_method,
            transaction_date=datetime.now().date(),
            operator=session.get('real_name', session.get('username', '')),
            remark=f'收款核销: {receivable.transaction_no} {remark}'
        )

        # 更新账户余额
        if account_id:
            account = BankAccount.query.get(account_id)
            if account:
                account.current_balance += collect_amount

        db.session.add(transaction)
        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='collect',
            module='finance',
            description=f'收款: {receivable.transaction_no} ¥{collect_amount}',
            reference_type='accounts_receivable',
            reference_id=receivable.id,
            reference_no=receivable.transaction_no
        )

        return jsonify({'success': True, 'message': '收款成功'})

    # GET请求显示收款页面
    receivable_id = request.args.get('id', type=int)
    receivable = AccountsReceivable.query.get(receivable_id)
    accounts = BankAccount.query.filter_by(is_active=True).all()

    return render_template('finance/receivables/collect.html',
                           receivable=receivable,
                           accounts=accounts)


# ============ 应付管理 ============

@finance_bp.route('/payables')
@login_required
def payables():
    """应付款列表"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '').strip()
    supplier_name = request.args.get('supplier_name', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = AccountsPayable.query

    # 状态筛选
    if status:
        query = query.filter(AccountsPayable.status == status)

    # 供应商搜索
    if supplier_name:
        query = query.filter(
            or_(
                AccountsPayable.supplier_name.like(f'%{supplier_name}%'),
                AccountsPayable.supplier_contact.like(f'%{supplier_name}%')
            )
        )

    # 日期范围筛选
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AccountsPayable.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(AccountsPayable.created_at <= end_dt)
        except ValueError:
            pass

    pagination = query.order_by(AccountsPayable.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    # 统计数据
    total_amount = db.session.query(func.sum(AccountsPayable.amount)).filter(
        AccountsPayable.status != 'cancelled'
    ).scalar() or Decimal('0')

    total_pending = db.session.query(func.sum(AccountsPayable.pending_amount)).filter(
        AccountsPayable.status.in_(['pending', 'partial'])
    ).scalar() or Decimal('0')

    return render_template('finance/payables/list.html',
                           payables=pagination.items,
                           pagination=pagination,
                           status=status,
                           supplier_name=supplier_name,
                           start_date=start_date,
                           end_date=end_date,
                           total_amount=total_amount,
                           total_pending=total_pending)


@finance_bp.route('/payables/pay', methods=['GET', 'POST'])
@login_required
def pay_amount():
    """付款"""
    if request.method == 'POST':
        payable_id = request.form.get('payable_id', type=int)
        pay_amount = request.form.get('pay_amount', 0)
        account_id = request.form.get('account_id', type=int)
        payment_method = request.form.get('payment_method', '').strip()
        remark = request.form.get('remark', '').strip()

        try:
            pay_amount = Decimal(pay_amount)
        except:
            return jsonify({'success': False, 'message': '金额格式错误'})

        payable = AccountsPayable.query.get(payable_id)
        if not payable:
            return jsonify({'success': False, 'message': '应付记录不存在'})

        if pay_amount > payable.pending_amount:
            return jsonify({'success': False, 'message': '付款金额不能超过待付金额'})

        # 检查账户余额
        if account_id:
            account = BankAccount.query.get(account_id)
            if account and account.current_balance < pay_amount:
                return jsonify({'success': False, 'message': f'账户余额不足，当前余额: ¥{account.current_balance}'})

        # 更新应付记录
        payable.paid_amount += pay_amount
        payable.pending_amount -= pay_amount

        if payable.pending_amount <= 0:
            payable.status = 'paid'
        else:
            payable.status = 'partial'

        # 生成付款记录
        transaction = FinancialTransaction(
            transaction_no=FinancialTransaction.generate_transaction_no('expense'),
            type='expense',
            category='采购支出',
            amount=pay_amount,
            account_id=account_id,
            direction='out',
            related_type='payable',
            related_id=payable.id,
            counterparty_name=payable.supplier_name,
            payment_method=payment_method,
            transaction_date=datetime.now().date(),
            operator=session.get('real_name', session.get('username', '')),
            remark=f'付款核销: {payable.transaction_no} {remark}'
        )

        # 更新账户余额
        if account_id:
            account = BankAccount.query.get(account_id)
            if account:
                account.current_balance -= pay_amount

        db.session.add(transaction)
        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='pay',
            module='finance',
            description=f'付款: {payable.transaction_no} ¥{pay_amount}',
            reference_type='accounts_payable',
            reference_id=payable.id,
            reference_no=payable.transaction_no
        )

        return jsonify({'success': True, 'message': '付款成功'})

    # GET请求显示付款页面
    payable_id = request.args.get('id', type=int)
    payable = AccountsPayable.query.get(payable_id)
    accounts = BankAccount.query.filter_by(is_active=True).all()

    return render_template('finance/payables/pay.html',
                           payable=payable,
                           accounts=accounts)


# ============ 财务报表 ============

@finance_bp.route('/reports/profit')
@login_required
def profit_report():
    """利润表"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)

    # 默认查询本月
    if not start_date:
        start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')

    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        start_dt = datetime.now().replace(day=1)
        end_dt = datetime.now()

    # 查询出库记录（销售收入）
    query = db.session.query(
        func.sum(StockTransaction.quantity * StockTransaction.unit_cost).label('total')
    ).filter(
        StockTransaction.type == 'stock_out',
        StockTransaction.created_at >= start_dt,
        StockTransaction.created_at <= end_dt
    )

    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)

    sales_revenue = query.scalar() or Decimal('0')

    # 查询入库记录（销售成本）
    query = db.session.query(
        func.sum(StockTransaction.quantity * StockTransaction.unit_cost).label('total')
    ).filter(
        StockTransaction.type == 'stock_in',
        StockTransaction.created_at >= start_dt,
        StockTransaction.created_at <= end_dt
    )

    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)

    purchase_cost = query.scalar() or Decimal('0')

    # 其他收入
    other_income = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.type == 'income',
        FinancialTransaction.category != '销售收入',
        FinancialTransaction.transaction_date >= start_dt.date(),
        FinancialTransaction.transaction_date <= end_dt.date(),
        FinancialTransaction.status == 'completed'
    ).scalar() or Decimal('0')

    # 其他支出
    other_expense = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.type == 'expense',
        FinancialTransaction.category != '采购支出',
        FinancialTransaction.transaction_date >= start_dt.date(),
        FinancialTransaction.transaction_date <= end_dt.date(),
        FinancialTransaction.status == 'completed'
    ).scalar() or Decimal('0')

    # 计算利润
    gross_profit = sales_revenue - purchase_cost  # 毛利润
    operating_profit = gross_profit + other_income - other_expense  # 营业利润

    warehouses = db.session.query(Warehouse).filter_by(is_active=True).all()

    return render_template('finance/reports/profit.html',
                           start_date=start_date,
                           end_date=end_date,
                           warehouse_id=warehouse_id,
                           warehouses=warehouses,
                           sales_revenue=sales_revenue,
                           purchase_cost=purchase_cost,
                           gross_profit=gross_profit,
                           other_income=other_income,
                           other_expense=other_expense,
                           operating_profit=operating_profit)


@finance_bp.route('/reports/receivable-detail')
@login_required
def receivable_detail():
    """应收款明细表"""
    status = request.args.get('status', '').strip()
    customer_name = request.args.get('customer_name', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = AccountsReceivable.query

    if status:
        query = query.filter(AccountsReceivable.status == status)

    if customer_name:
        query = query.filter(
            or_(
                AccountsReceivable.customer_name.like(f'%{customer_name}%'),
                AccountsReceivable.customer_address.like(f'%{customer_name}%')
            )
        )

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AccountsReceivable.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(AccountsReceivable.created_at <= end_dt)
        except ValueError:
            pass

    receivables = query.order_by(AccountsReceivable.created_at.desc()).all()

    # 汇总统计
    total_amount = sum(r.amount for r in receivables if r.status != 'written_off')
    total_paid = sum(r.paid_amount for r in receivables if r.status != 'written_off')
    total_pending = sum(r.pending_amount for r in receivables if r.status in ['pending', 'partial'])

    return render_template('finance/reports/receivable_detail.html',
                           receivables=receivables,
                           status=status,
                           customer_name=customer_name,
                           start_date=start_date,
                           end_date=end_date,
                           total_amount=total_amount,
                           total_paid=total_paid,
                           total_pending=total_pending)


@finance_bp.route('/reports/payable-detail')
@login_required
def payable_detail():
    """应付款明细表"""
    status = request.args.get('status', '').strip()
    supplier_name = request.args.get('supplier_name', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = AccountsPayable.query

    if status:
        query = query.filter(AccountsPayable.status == status)

    if supplier_name:
        query = query.filter(
            or_(
                AccountsPayable.supplier_name.like(f'%{supplier_name}%'),
                AccountsPayable.supplier_contact.like(f'%{supplier_name}%')
            )
        )

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AccountsPayable.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(AccountsPayable.created_at <= end_dt)
        except ValueError:
            pass

    payables = query.order_by(AccountsPayable.created_at.desc()).all()

    # 汇总统计
    total_amount = sum(p.amount for p in payables if p.status != 'cancelled')
    total_paid = sum(p.paid_amount for p in payables if p.status != 'cancelled')
    total_pending = sum(p.pending_amount for p in payables if p.status in ['pending', 'partial'])

    return render_template('finance/reports/payable_detail.html',
                           payables=payables,
                           status=status,
                           supplier_name=supplier_name,
                           start_date=start_date,
                           end_date=end_date,
                           total_amount=total_amount,
                           total_paid=total_paid,
                           total_pending=total_pending)


@finance_bp.route('/reports/balance')
@login_required
def balance_report():
    """资产负债表"""
    # 获取所有账户余额
    accounts = BankAccount.query.filter_by(is_active=True).all()
    total_cash = sum(a.current_balance for a in accounts)

    # 应收款
    total_receivable = db.session.query(func.sum(AccountsReceivable.pending_amount)).filter(
        AccountsReceivable.status.in_(['pending', 'partial'])
    ).scalar() or Decimal('0')

    # 应付款
    total_payable = db.session.query(func.sum(AccountsPayable.pending_amount)).filter(
        AccountsPayable.status.in_(['pending', 'partial'])
    ).scalar() or Decimal('0')

    # 本月收入支出
    month_start = datetime.now().replace(day=1).date()
    month_end = datetime.now().date()

    month_income = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.type == 'income',
        FinancialTransaction.transaction_date >= month_start,
        FinancialTransaction.transaction_date <= month_end,
        FinancialTransaction.status == 'completed'
    ).scalar() or Decimal('0')

    month_expense = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.type == 'expense',
        FinancialTransaction.transaction_date >= month_start,
        FinancialTransaction.transaction_date <= month_end,
        FinancialTransaction.status == 'completed'
    ).scalar() or Decimal('0')

    return render_template('finance/reports/balance.html',
                           accounts=accounts,
                           total_cash=total_cash,
                           total_receivable=total_receivable,
                           total_payable=total_payable,
                           month_income=month_income,
                           month_expense=month_expense,
                           month_profit=month_income - month_expense)


# ============ 对账结算 ============

@finance_bp.route('/reconciliation')
@login_required
def reconciliation():
    """对账结算页面"""
    # 获取本期应收应付汇总
    month_start = datetime.now().replace(day=1).date()
    month_end = datetime.now().date()

    # 本期新增应收
    period_receivable = db.session.query(func.sum(AccountsReceivable.amount)).filter(
        AccountsReceivable.created_at >= datetime.combine(month_start, datetime.min.time()),
        AccountsReceivable.created_at <= datetime.combine(month_end, datetime.max.time())
    ).scalar() or Decimal('0')

    # 本期新增应付
    period_payable = db.session.query(func.sum(AccountsPayable.amount)).filter(
        AccountsPayable.created_at >= datetime.combine(month_start, datetime.min.time()),
        AccountsPayable.created_at <= datetime.combine(month_end, datetime.max.time())
    ).scalar() or Decimal('0')

    # 本期收款
    period_collect = db.session.query(func.sum(AccountsReceivable.paid_amount)).filter(
        AccountsReceivable.status.in_(['received', 'partial']),
        AccountsReceivable.updated_at >= datetime.combine(month_start, datetime.min.time()),
        AccountsReceivable.updated_at <= datetime.combine(month_end, datetime.max.time())
    ).scalar() or Decimal('0')

    # 本期付款
    period_pay = db.session.query(func.sum(AccountsPayable.paid_amount)).filter(
        AccountsPayable.status.in_(['paid', 'partial']),
        AccountsPayable.updated_at >= datetime.combine(month_start, datetime.min.time()),
        AccountsPayable.updated_at <= datetime.combine(month_end, datetime.max.time())
    ).scalar() or Decimal('0')

    # 账户总余额
    total_balance = db.session.query(func.sum(BankAccount.current_balance)).filter(
        BankAccount.is_active == True
    ).scalar() or Decimal('0')

    return render_template('finance/reconciliation.html',
                           month_start=month_start,
                           month_end=month_end,
                           period_receivable=period_receivable,
                           period_payable=period_payable,
                           period_collect=period_collect,
                           period_pay=period_pay,
                           total_balance=total_balance,
                           net_receivable=period_receivable - period_collect,
                           net_payable=period_payable - period_pay)


# ============ 导出功能 ============

@finance_bp.route('/transactions/export')
@login_required
def export_transactions():
    """导出收支记录到Excel"""
    tx_type = request.args.get('type', '').strip()
    account_id = request.args.get('account_id', '0')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip()
    
    query = FinancialTransaction.query
    
    # 类型筛选
    if tx_type:
        query = query.filter(FinancialTransaction.type == tx_type)
    
    # 账户筛选
    if account_id and account_id != '0':
        query = query.filter(FinancialTransaction.account_id == int(account_id))
    
    # 日期范围筛选
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(FinancialTransaction.transaction_date >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(FinancialTransaction.transaction_date <= end_dt)
        except ValueError:
            pass
    
    # 搜索
    if search:
        query = query.filter(
            or_(
                FinancialTransaction.transaction_no.like(f'%{search}%'),
                FinancialTransaction.counterparty_name.like(f'%{search}%'),
                FinancialTransaction.remark.like(f'%{search}%')
            )
        )
    
    transactions = query.order_by(FinancialTransaction.transaction_date.desc()).all()
    
    type_map = {
        'income': '收入',
        'expense': '支出'
    }
    
    data = []
    for tx in transactions:
        data.append({
            'transaction_no': tx.transaction_no,
            'transaction_date': tx.transaction_date.strftime('%Y-%m-%d') if tx.transaction_date else '',
            'type': type_map.get(tx.type, tx.type),
            'category': tx.category or '',
            'amount': tx.amount,
            'account_name': tx.account.name if tx.account else '',
            'direction': '流入' if tx.direction == 'in' else '流出',
            'counterparty_name': tx.counterparty_name or '',
            'operator': tx.operator or '',
            'status': '已完成' if tx.status == 'completed' else '待确认' if tx.status == 'pending' else '已取消',
            'remark': tx.remark or ''
        })
    
    headers = [
        ('transaction_no', '单号'),
        ('transaction_date', '日期'),
        ('type', '类型'),
        ('category', '分类'),
        ('amount', '金额'),
        ('account_name', '账户'),
        ('direction', '方向'),
        ('counterparty_name', '对方单位'),
        ('operator', '操作人'),
        ('status', '状态'),
        ('remark', '备注')
    ]
    
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='finance',
        description='导出收支记录'
    )
    
    return export_to_excel(data, headers, '收支记录.xlsx')


@finance_bp.route('/receivables/export')
@login_required
def export_receivables():
    """导出应收款到Excel"""
    status = request.args.get('status', '').strip()
    customer_name = request.args.get('customer_name', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    query = AccountsReceivable.query
    
    if status:
        query = query.filter(AccountsReceivable.status == status)
    
    if customer_name:
        query = query.filter(
            or_(
                AccountsReceivable.customer_name.like(f'%{customer_name}%'),
                AccountsReceivable.customer_address.like(f'%{customer_name}%')
            )
        )
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AccountsReceivable.created_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(AccountsReceivable.created_at <= end_dt)
        except ValueError:
            pass
    
    receivables = query.order_by(AccountsReceivable.created_at.desc()).all()
    
    status_map = {
        'pending': '待收款',
        'partial': '部分收款',
        'received': '已收清',
        'written_off': '已核销'
    }
    
    data = []
    for ar in receivables:
        data.append({
            'transaction_no': ar.transaction_no,
            'customer_name': ar.customer_name,
            'customer_address': ar.customer_address or '',
            'amount': ar.amount,
            'paid_amount': ar.paid_amount,
            'pending_amount': ar.pending_amount,
            'due_date': ar.due_date.strftime('%Y-%m-%d') if ar.due_date else '',
            'status': status_map.get(ar.status, ar.status),
            'related_no': ar.related_no or '',
            'remark': ar.remark or ''
        })
    
    headers = [
        ('transaction_no', '单号'),
        ('customer_name', '客户名称'),
        ('customer_address', '收货地址'),
        ('amount', '应收金额'),
        ('paid_amount', '已收金额'),
        ('pending_amount', '待收金额'),
        ('due_date', '到期日'),
        ('status', '状态'),
        ('related_no', '关联单号'),
        ('remark', '备注')
    ]
    
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='finance',
        description='导出应收款记录'
    )
    
    return export_to_excel(data, headers, '应收款记录.xlsx')


@finance_bp.route('/payables/export')
@login_required
def export_payables():
    """导出应付款到Excel"""
    status = request.args.get('status', '').strip()
    supplier_name = request.args.get('supplier_name', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    query = AccountsPayable.query
    
    if status:
        query = query.filter(AccountsPayable.status == status)
    
    if supplier_name:
        query = query.filter(
            or_(
                AccountsPayable.supplier_name.like(f'%{supplier_name}%'),
                AccountsPayable.supplier_contact.like(f'%{supplier_name}%')
            )
        )
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AccountsPayable.created_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(AccountsPayable.created_at <= end_dt)
        except ValueError:
            pass
    
    payables = query.order_by(AccountsPayable.created_at.desc()).all()
    
    status_map = {
        'pending': '待付款',
        'partial': '部分付款',
        'paid': '已付清',
        'cancelled': '已取消'
    }
    
    data = []
    for ap in payables:
        data.append({
            'transaction_no': ap.transaction_no,
            'supplier_name': ap.supplier_name,
            'supplier_contact': ap.supplier_contact or '',
            'amount': ap.amount,
            'paid_amount': ap.paid_amount,
            'pending_amount': ap.pending_amount,
            'due_date': ap.due_date.strftime('%Y-%m-%d') if ap.due_date else '',
            'status': status_map.get(ap.status, ap.status),
            'related_no': ap.related_no or '',
            'remark': ap.remark or ''
        })
    
    headers = [
        ('transaction_no', '单号'),
        ('supplier_name', '供应商名称'),
        ('supplier_contact', '联系人'),
        ('amount', '应付金额'),
        ('paid_amount', '已付金额'),
        ('pending_amount', '待付金额'),
        ('due_date', '到期日'),
        ('status', '状态'),
        ('related_no', '关联单号'),
        ('remark', '备注')
    ]
    
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='finance',
        description='导出应付款记录'
    )
    
    return export_to_excel(data, headers, '应付款记录.xlsx')


@finance_bp.route('/reports/profit/export')
@login_required
def export_profit_report():
    """导出利润报表到Excel"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    warehouse_id = request.args.get('warehouse_id', '0')
    
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        start_dt = (datetime.now() - timedelta(days=30))
        end_dt = datetime.now()
    
    # 销售收入
    sales_revenue = db.session.query(func.sum(StockTransaction.quantity * StockTransaction.unit_cost)).filter(
        StockTransaction.type == 'stock_out',
        StockTransaction.created_at >= start_dt,
        StockTransaction.created_at <= end_dt
    ).scalar() or Decimal('0')
    
    # 销售成本 (采购入库)
    purchase_cost = db.session.query(func.sum(StockTransaction.quantity * StockTransaction.unit_cost)).filter(
        StockTransaction.type == 'stock_in',
        StockTransaction.created_at >= start_dt,
        StockTransaction.created_at <= end_dt
    ).scalar() or Decimal('0')
    
    # 其他收入
    other_income = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.type == 'income',
        FinancialTransaction.category != '销售收入',
        FinancialTransaction.transaction_date >= start_dt.date(),
        FinancialTransaction.transaction_date <= end_dt.date()
    ).scalar() or Decimal('0')
    
    # 其他支出
    other_expense = db.session.query(func.sum(FinancialTransaction.amount)).filter(
        FinancialTransaction.type == 'expense',
        FinancialTransaction.transaction_date >= start_dt.date(),
        FinancialTransaction.transaction_date <= end_dt.date()
    ).scalar() or Decimal('0')
    
    gross_profit = sales_revenue - purchase_cost
    operating_profit = gross_profit + other_income - other_expense
    
    data = [
        {
            'item': '一、主营业务',
            'current': '',
            'cumulative': ''
        },
        {
            'item': '  销售收入',
            'current': float(sales_revenue),
            'cumulative': ''
        },
        {
            'item': '  减：销售成本',
            'current': float(purchase_cost),
            'cumulative': ''
        },
        {
            'item': '  毛利润',
            'current': float(gross_profit),
            'cumulative': ''
        },
        {
            'item': '二、其他业务',
            'current': '',
            'cumulative': ''
        },
        {
            'item': '  其他收入',
            'current': float(other_income),
            'cumulative': ''
        },
        {
            'item': '  减：其他支出',
            'current': float(other_expense),
            'cumulative': ''
        },
        {
            'item': '三、营业利润',
            'current': float(operating_profit),
            'cumulative': ''
        }
    ]
    
    headers = [
        ('item', '项目'),
        ('current', '本期金额'),
        ('cumulative', '累计金额')
    ]
    
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='finance',
        description=f'导出利润报表 {start_date} 至 {end_date}'
    )
    
    return export_to_excel(data, headers, f'利润报表_{start_date}_至_{end_date}.xlsx')
