#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时区校正脚本：将历史数据中以 UTC 存储的时间统一修正为北京时间（Asia/Shanghai）。

背景
----
项目历史上曾在「美国/UTC 时区」的进程下写入数据，导致数据库里的 created_at /
updated_at 比实际北京时间慢 8 小时。本脚本用于一次性校正历史数据。

校正策略（智能、可逆、可审计）
---------------------------------
逐行判断：对带时分秒的时间字段，
  - 若「原始值当作 UTC 解读」对应的北京时间 = 原始值 + 8 小时，落在 08:00–22:00
    这个正常业务时段；
  - 且「原始值直接当作北京时间」却落在 00:00–07:59 的凌晨异常时段；
  → 判定该记录原为 UTC，需要 +8 小时。

这样既能把明显是 UTC 的凌晨记录修正为北京，又不会把本就是北京白天发生的
记录（如 10:40）错误地再加 8 小时。

使用
----
  python scripts/fix_timezone_cst.py --dry-run      # 预览，不改动数据库
  python scripts/fix_timezone_cst.py                # 实际执行校正
  python scripts/fix_timezone_cst.py --all-utc      # 强制全部 +8h（谨慎使用）

执行前会自动备份 inventory.db 到 backups/ 目录。
"""
import os
import sys
import sqlite3
import shutil
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'inventory.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')

# (表名, 时间字段列表)
TIME_FIELDS = [
    ('operation_logs', ['created_at']),
    ('stock_transactions', ['created_at']),
    ('batch_codes', ['created_at', 'sold_at', 'transferred_at']),
    ('backup_history', ['created_at']),
    ('inventory', ['updated_at']),
    ('products', ['created_at', 'updated_at']),
    ('product_batches', ['created_at', 'updated_at', 'production_date', 'expire_date']),
    ('customers', ['created_at', 'updated_at']),
    ('suppliers', ['created_at', 'updated_at']),
    ('warehouses', ['created_at']),
    ('users', ['created_at', 'updated_at', 'password_changed_at']),
    ('roles', ['created_at', 'updated_at']),
    ('system_configs', ['updated_at']),
    ('email_configs', ['created_at', 'updated_at']),
    ('email_templates', ['created_at', 'updated_at']),
    ('bank_accounts', ['created_at', 'updated_at']),
    ('accounts_receivable', ['created_at', 'due_date']),
    ('accounts_payable', ['created_at', 'due_date']),
    ('financial_transactions', ['created_at', 'transaction_date']),
    ('purchase_orders', ['created_at', 'updated_at', 'order_date']),
    ('purchase_order_items', []),
    ('platform_orders', ['created_at']),
    ('platform_order_items', []),
    ('form_config', ['created_at', 'updated_at']),
    ('form_field_config', []),
]


def parse_dt(v):
    """解析 SQLite 存储的 TEXT/时间戳为 datetime，失败返回 None"""
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        # 可能是 UNIX 时间戳
        try:
            return datetime.fromtimestamp(v)
        except Exception:
            return None
    s = str(v).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S',
               '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S.%f',
               '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def fmt_db(dt):
    """格式化回数据库存储格式，保持6位微秒（SQLAlchemy DATE/DATETIME 兼容）"""
    # 注意：不能截断为3位毫秒，否则 SQLAlchemy C扩展 str_to_date 会报错
    return dt.strftime('%Y-%m-%d %H:%M:%S.%f')


def is_utc_record(orig):
    """
    判断原始值是否更像 UTC：
    原始值若当作 UTC，+8h 后落在 08:00–22:00 白天，且原值本身落在 00:00–07:59 凌晨。
    注意：纯日期（无时间部分，如 2025-11-17 00:00:00）不参与校正，直接跳过。
    """
    # 纯日期（午夜 00:00:00 且原始字符串不含时间部分）不校正
    if orig.hour == 0 and orig.minute == 0 and orig.second == 0 and orig.microsecond == 0:
        return False
    bj_if_utc = orig + timedelta(hours=8)
    return (0 <= orig.hour <= 7) and (8 <= bj_if_utc.hour <= 22)


def main():
    import argparse
    ap = argparse.ArgumentParser(description='历史数据时区校正（UTC → 北京时间）')
    ap.add_argument('--dry-run', action='store_true', help='只预览，不写库')
    ap.add_argument('--all-utc', action='store_true', help='强制把所有记录都 +8h（谨慎）')
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 校验所有字段存在
    changes = []  # (table, pk_id, field, old_val, new_val)
    for table, fields in TIME_FIELDS:
        # 检查表是否存在
        try:
            cur.execute(f"SELECT name FROM pragma_table_info('{table}')")
            cols = {r[0] for r in cur.fetchall()}
        except sqlite3.OperationalError:
            continue
        fields = [f for f in fields if f in cols]
        if not fields:
            continue
        # 找主键列（优先 id）
        pk = 'id' if 'id' in cols else list(cols)[0]
        for field in fields:
            cur.execute(f"SELECT {pk}, {field} FROM {table}")
            for row_id, val in cur.fetchall():
                orig = parse_dt(val)
                if orig is None:
                    continue
                if args.all_utc:
                    new = orig + timedelta(hours=8)
                    changes.append((table, row_id, field, val, fmt_db(new)))
                else:
                    if is_utc_record(orig):
                        changes.append((table, row_id, field, val, fmt_db(orig + timedelta(hours=8))))

    # 汇总
    by_table = {}
    for t, _, _, _, _ in changes:
        by_table[t] = by_table.get(t, 0) + 1

    print(f"{'【预览模式】' if args.dry_run else '【执行模式】'} 待校正记录数: {len(changes)}")
    for t, n in sorted(by_table.items(), key=lambda x: -x[1]):
        print(f"  - {t}: {n} 条字段")

    if not changes:
        print('没有需要校正的时间字段。')
        con.close()
        return

    if args.dry_run:
        print('\n--- 前 20 条样本 ---')
        for t, rid, f, old, new in changes[:20]:
            print(f'  {t}#{rid}.{f}: {old}  ->  {new}')
        con.close()
        return

    # 执行前备份
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = os.path.join(BACKUP_DIR, f'inventory_before_tzfix_{ts}.db')
    shutil.copy2(DB_PATH, bak)
    print(f'\n已备份数据库到: {bak}')

    # 执行更新
    updated = 0
    for table, rid, field, old, new in changes:
        cur.execute(f"UPDATE {table} SET {field}=? WHERE id=?", (new, rid))
        updated += 1
    con.commit()
    con.close()
    print(f'校正完成，共更新 {updated} 个时间字段。')
    print('如需回滚：将备份文件覆盖回 inventory.db 即可。')


if __name__ == '__main__':
    main()
