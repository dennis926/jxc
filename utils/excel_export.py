from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from flask import Response
import io


def export_to_excel(data, headers, filename):
    """
    导出数据到Excel
    :param data: 数据列表，每个元素是一个字典
    :param headers: 表头列表 [(key, label), ...]
    :param filename: 文件名
    """
    wb = Workbook()
    ws = wb.active
    
    # 写入表头
    header_font = Font(bold=True)
    for col, (key, label) in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=label)
        cell.font = header_font
    
    # 写入数据
    for row, item in enumerate(data, 2):
        for col, (key, label) in enumerate(headers, 1):
            ws.cell(row=row, column=col, value=item.get(key, ''))
    
    # 保存到内存
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    # 处理文件名中的中文编码
    from urllib.parse import quote
    encoded_filename = quote(filename)
    
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': f'attachment; filename*=UTF-8\'\'{encoded_filename}',
            'Cache-Control': 'no-cache'
        }
    )


class ExcelExport:
    """Excel导出工具类"""
    
    @staticmethod
    def create_excel(headers, data, sheet_name='Sheet1'):
        """
        创建Excel文件
        
        Args:
            headers: 表头列表 ['列1', '列2', ...]
            data: 数据列表 [[值1, 值2, ...], ...]
            sheet_name: 工作表名称
            
        Returns:
            BytesIO对象
        """
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        
        # 样式定义
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center')
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 写入表头
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # 写入数据
        for row_idx, row_data in enumerate(data, 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = thin_border
        
        # 调整列宽
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 15
        
        # 保存到内存
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        return output
