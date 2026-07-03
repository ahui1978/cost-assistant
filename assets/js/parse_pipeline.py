# -*- coding: utf-8 -*-
"""
解析管线切改指标 Excel 原始数据，生成结构化 JS 数据文件
"""
import json

# 读取原始 JSON
with open(r'd:\TRAE SOLO CN\mydata\cost-assistant\assets\pipeline_raw.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

# ========== 解析列表型 sheet（电力/通信/燃气/通用工程）==========
def parse_list_sheet(rows):
    """解析列表型表格：分类标题行 + 表头 + 数据行"""
    categories = []
    current_category = None

    for row in rows:
        # 跳过空行
        if all(v == '' or v is None for v in row):
            continue
        # 跳过标题行（第一列是 sheet 名称）
        if row[0] and isinstance(row[0], str) and ('迁改指标' in str(row[0]) or '通用工程指标' in str(row[0])):
            continue
        # 跳过表头行（第一列是"序号"）
        if row[0] == '序号':
            continue

        # 判断是否为分类标题行：第一列有值但不是数字，或者整行只有第一列有值
        first_val = row[0]
        is_category = False
        if first_val and isinstance(first_val, str):
            # 非数字开头，且其他列基本为空 -> 分类标题
            non_empty = [v for v in row if v != '' and v is not None]
            if len(non_empty) <= 1 and not str(first_val).isdigit():
                is_category = True

        if is_category:
            current_category = {
                'category': str(first_val).strip(),
                'items': []
            }
            categories.append(current_category)
        else:
            # 数据行：若无当前分类，自动创建默认分类（通用工程无分类标题行）
            if current_category is None:
                current_category = {'category': '通用项目', 'items': []}
                categories.append(current_category)
            if current_category is not None:
                item = {
                    'seq': row[0] if row[0] != '' else '',
                    'name': str(row[1]).strip() if len(row) > 1 and row[1] != '' else '',
                    'unit': str(row[2]).strip() if len(row) > 2 and row[2] != '' else '',
                    'price': row[3] if len(row) > 3 and row[3] != '' else '',
                    'note': str(row[4]).strip() if len(row) > 4 and row[4] != '' else ''
                }
                # 只要名称不为空就保留
                if item['name']:
                    current_category['items'].append(item)

    return categories


# ========== 解析矩阵型 sheet（给水/排水/热力）==========
def parse_matrix_sheet(rows):
    """解析矩阵型表格：管径 × 埋深 交叉矩阵"""
    headers = []
    data = []

    for i, row in enumerate(rows):
        if all(v == '' or v is None for v in row):
            continue
        # 跳过标题行
        if row[0] and isinstance(row[0], str) and '迁改指标' in str(row[0]):
            continue

        # 表头行（第一列是"管径"）
        if row[0] == '管径':
            headers = [str(v).strip() if v != '' else '' for v in row]
            continue

        # 数据行
        if headers and row[0]:
            entry = {'diameter': str(row[0]).strip()}
            for j in range(1, len(headers)):
                col_name = headers[j]
                if col_name:
                    val = row[j] if j < len(row) and row[j] != '' else ''
                    entry[col_name] = val
            data.append(entry)

    return {'headers': headers, 'data': data}


# ========== 解析换算系数 ==========
def parse_conversion_sheet(rows):
    items = []
    for row in rows:
        if all(v == '' or v is None for v in row):
            continue
        if row[0] == '序号' or (row[0] and '换算系数' in str(row[0])):
            continue
        if row[0] and str(row[0]).isdigit():
            items.append({
                'seq': row[0],
                'scene': str(row[1]).strip() if len(row) > 1 else '',
                'profession': str(row[2]).strip() if len(row) > 2 else '',
                'rule': str(row[3]).strip() if len(row) > 3 else '',
                'note': str(row[4]).strip() if len(row) > 4 else ''
            })
    return items


# ========== 解析费用取费标准 ==========
def parse_fee_sheet(rows):
    items = []
    for row in rows:
        if all(v == '' or v is None for v in row):
            continue
        if row[0] == '序号' or (row[0] and '费用取费' in str(row[0])):
            continue
        if row[0] and str(row[0]).isdigit():
            items.append({
                'seq': row[0],
                'name': str(row[1]).strip() if len(row) > 1 else '',
                'profession': str(row[2]).strip() if len(row) > 2 else '',
                'rate': str(row[3]).strip() if len(row) > 3 else '',
                'base': str(row[4]).strip() if len(row) > 4 else '',
                'note': str(row[5]).strip() if len(row) > 5 else ''
            })
    return items


# ========== 解析总说明 ==========
def parse_intro_sheet(rows):
    items = []
    for row in rows:
        if all(v == '' or v is None for v in row):
            continue
        if row[0] and '总说明' in str(row[0]):
            continue
        if row[0] == '序号':
            continue
        if row[0] and str(row[0]).isdigit():
            items.append({
                'seq': row[0],
                'name': str(row[1]).strip() if len(row) > 1 else '',
                'content': str(row[2]).strip() if len(row) > 2 else ''
            })
    return items


# ========== 组装结构化数据 ==========
structured = {
    'intro': parse_intro_sheet(raw.get('总说明', [])),
    'electric': parse_list_sheet(raw.get('电力迁改指标', [])),
    'communication': parse_list_sheet(raw.get('通信迁改指标', [])),
    'gas': parse_list_sheet(raw.get('燃气迁改指标', [])),
    'general': parse_list_sheet(raw.get('通用工程指标', [])),
    'water': parse_matrix_sheet(raw.get('给水迁改指标', [])),
    'drainage': parse_matrix_sheet(raw.get('排水迁改指标', [])),
    'thermal': parse_matrix_sheet(raw.get('热力迁改指标', [])),
    'conversion': parse_conversion_sheet(raw.get('换算系数', [])),
    'fee': parse_fee_sheet(raw.get('费用取费标准', []))
}

# 输出统计
for k, v in structured.items():
    if isinstance(v, list):
        if v and isinstance(v[0], dict) and 'category' in v[0]:
            total = sum(len(c['items']) for c in v)
            print(f'{k}: {len(v)} categories, {total} items')
        else:
            print(f'{k}: {len(v)} items')
    else:
        print(f'{k}: {len(v.get("data", []))} rows, {len(v.get("headers", []))} cols')

# 生成 JS 文件
js_content = '/* 管线迁改工程预算限额指标 - 结构化数据 */\n'
js_content += '/* 数据来源：管线切改指标成果.xlsx，基于广州、雄安、天津、乌海四地资料编制 */\n'
js_content += 'window.PIPELINE_DATA = ' + json.dumps(structured, ensure_ascii=False, indent=2) + ';\n'

with open(r'd:\TRAE SOLO CN\mydata\cost-assistant\assets\js\pipeline-data.js', 'w', encoding='utf-8') as f:
    f.write(js_content)

import os
print(f'\nGenerated: pipeline-data.js ({os.path.getsize(r"d:\TRAE SOLO CN\mydata\cost-assistant\assets\js\pipeline-data.js")} bytes)')
