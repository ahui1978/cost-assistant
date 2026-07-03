# -*- coding: utf-8 -*-
"""
工具函数模块 - 提供 Function Calling 可用的工具
包含：管线迁改指标查询、造价指标查询
"""
import json
import os
from difflib import SequenceMatcher

# ========== 数据加载 ==========
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')


def load_pipeline_data():
    """加载管线迁改指标结构化数据"""
    # 优先用结构化 JS 数据，否则用原始 JSON
    js_path = os.path.join(DATA_DIR, 'js', 'pipeline-data.js')
    raw_path = os.path.join(DATA_DIR, 'pipeline_raw.json')

    if os.path.exists(js_path):
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 提取 window.PIPELINE_DATA = {...}; 中的 JSON
        start = content.find('{')
        end = content.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])

    if os.path.exists(raw_path):
        with open(raw_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    return {}


def load_cost_index_data():
    """加载造价指标数据（目前用 mock 数据，后续可扩展）"""
    return {
        '建筑类型': [
            {'name': '高层住宅', 'unit': '元/m²', 'range': '2800-6800', 'note': '含土建、安装、装饰，不含土地'},
            {'name': '多层住宅', 'unit': '元/m²', 'range': '2200-4500', 'note': '6层及以下砖混/框架结构'},
            {'name': '办公楼', 'unit': '元/m²', 'range': '3500-8000', 'note': '含幕墙、机电、弱电系统'},
            {'name': '商业综合体', 'unit': '元/m²', 'range': '5000-12000', 'note': '含装修、机电、智能化'},
            {'name': '学校', 'unit': '元/m²', 'range': '3000-5500', 'note': '教学楼、实验楼等'},
            {'name': '医院', 'unit': '元/m²', 'range': '4500-9000', 'note': '含特殊医疗气体、净化系统'},
            {'name': '工业厂房', 'unit': '元/m²', 'range': '1800-4000', 'note': '钢结构/混凝土排架结构'}
        ],
        '费用构成': {
            '人工费占比': '25-30%',
            '材料费占比': '50-60%',
            '机械费占比': '8-12%',
            '管理费占比': '5-8%',
            '利润占比': '5-10%'
        },
        '地区系数': {
            '一线城市': '1.1-1.3',
            '二线城市': '1.0-1.1',
            '三线城市': '0.85-1.0',
            '四线及以下': '0.7-0.85'
        }
    }


# 全局缓存
_pipeline_data = None
_cost_index_data = None


def get_pipeline_data():
    global _pipeline_data
    if _pipeline_data is None:
        _pipeline_data = load_pipeline_data()
    return _pipeline_data


def get_cost_index_data():
    global _cost_index_data
    if _cost_index_data is None:
        _cost_index_data = load_cost_index_data()
    return _cost_index_data


# ========== 工具函数定义（OpenAI Function Calling 格式） ==========
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_pipeline_indicator",
            "description": "查询管线迁改工程预算限额指标，支持电力、通信、燃气、给水、排水、热力六大专业，以及通用工程、换算系数、费用取费标准等数据。适用于市政工程管线迁改造价估算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "profession": {
                        "type": "string",
                        "description": "专业类别，可选值：electric(电力)、communication(通信)、gas(燃气)、water(给水)、drainage(排水)、thermal(热力)、general(通用工程)、conversion(换算系数)、fee(费用取费标准)、intro(总说明)",
                        "enum": ["electric", "communication", "gas", "water", "drainage", "thermal", "general", "conversion", "fee", "intro"]
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如管径、材料、敷设方式、项目名称等，用于模糊匹配具体条目。不填则返回该专业全部数据。"
                    }
                },
                "required": ["profession"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_cost_index",
            "description": "查询建筑工程造价指标，包括各类建筑单方造价、费用构成比例、地区调价系数等。适用于建筑工程投资估算、方案比选、造价审核参考。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "description": "查询类型，可选值：building_type(按建筑类型查询单方造价)、cost_composition(费用构成比例)、region_factor(地区调价系数)",
                        "enum": ["building_type", "cost_composition", "region_factor"]
                    },
                    "keyword": {
                        "type": "string",
                        "description": "建筑类型关键词，如住宅、办公楼、商业、学校、医院、厂房等。当 query_type 为 building_type 时使用。"
                    }
                },
                "required": ["query_type"]
            }
        }
    }
]


# ========== 工具函数实现 ==========

def fuzzy_match_score(a, b):
    """计算两个字符串的模糊匹配得分（0-1）"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def query_pipeline_indicator(profession, keyword=None):
    """查询管线迁改指标"""
    data = get_pipeline_data()
    result = data.get(profession, [])

    if not result:
        return json.dumps({"error": f"未找到专业类别: {profession}"}, ensure_ascii=False)

    # 如果有关键词，进行模糊搜索
    if keyword and keyword.strip():
        kw = keyword.strip()
        matched = []

        # 列表型数据（electric, communication, gas, general）
        if isinstance(result, list) and result and isinstance(result[0], dict) and 'items' in result[0]:
            for category in result:
                cat_name = category.get('category', '')
                for item in category.get('items', []):
                    name = item.get('name', '')
                    note = item.get('note', '')
                    # 计算匹配度
                    score = max(
                        fuzzy_match_score(kw, name),
                        fuzzy_match_score(kw, cat_name),
                        fuzzy_match_score(kw, note) if note else 0
                    )
                    # 关键词包含匹配
                    if kw in name or kw in cat_name or (note and kw in note):
                        score = max(score, 0.8)
                    if score > 0.4:
                        matched.append({
                            'category': cat_name,
                            'name': name,
                            'unit': item.get('unit', ''),
                            'price': item.get('price', ''),
                            'note': note,
                            'score': round(score, 3)
                        })
            # 按匹配度排序
            matched.sort(key=lambda x: x['score'], reverse=True)
            return json.dumps({
                "profession": profession,
                "keyword": kw,
                "total_matches": len(matched),
                "results": matched[:30]  # 最多返回30条
            }, ensure_ascii=False)

        # 矩阵型数据（water, drainage, thermal）
        if isinstance(result, dict) and 'data' in result:
            matched_rows = []
            for row in result.get('data', []):
                diameter = row.get('diameter', '')
                score = fuzzy_match_score(kw, diameter)
                if kw in diameter:
                    score = max(score, 0.9)
                if score > 0.3:
                    row_copy = dict(row)
                    row_copy['score'] = round(score, 3)
                    matched_rows.append(row_copy)
            matched_rows.sort(key=lambda x: x.get('score', 0), reverse=True)
            return json.dumps({
                "profession": profession,
                "keyword": kw,
                "headers": result.get('headers', []),
                "total_matches": len(matched_rows),
                "results": matched_rows[:20]
            }, ensure_ascii=False)

        # 其他类型（conversion, fee, intro）
        if isinstance(result, list):
            for item in result:
                text = ' '.join(str(v) for v in item.values() if v)
                score = fuzzy_match_score(kw, text)
                if kw in text:
                    score = max(score, 0.9)
                if score > 0.4:
                    item['score'] = round(score, 3)
                    matched.append(item)
            matched.sort(key=lambda x: x.get('score', 0), reverse=True)
            return json.dumps({
                "profession": profession,
                "keyword": kw,
                "total_matches": len(matched),
                "results": matched[:30]
            }, ensure_ascii=False)

    # 无关键词，返回全部数据（精简版，避免 token 过大）
    if isinstance(result, list) and result and isinstance(result[0], dict) and 'items' in result[0]:
        summary = []
        for category in result:
            items = category.get('items', [])
            summary.append({
                'category': category.get('category', ''),
                'item_count': len(items),
                'sample_items': items[:5]  # 每类前5条作为样例
            })
        return json.dumps({
            "profession": profession,
            "total_categories": len(result),
            "categories": summary
        }, ensure_ascii=False)

    if isinstance(result, dict) and 'data' in result:
        return json.dumps({
            "profession": profession,
            "headers": result.get('headers', []),
            "row_count": len(result.get('data', [])),
            "sample_rows": result.get('data', [])[:10]
        }, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False)


def query_cost_index(query_type, keyword=None):
    """查询造价指标"""
    data = get_cost_index_data()

    if query_type == 'cost_composition':
        return json.dumps({
            "type": "费用构成比例",
            "data": data.get('费用构成', {})
        }, ensure_ascii=False)

    if query_type == 'region_factor':
        return json.dumps({
            "type": "地区调价系数",
            "data": data.get('地区系数', {})
        }, ensure_ascii=False)

    if query_type == 'building_type':
        buildings = data.get('建筑类型', [])
        if keyword and keyword.strip():
            kw = keyword.strip()
            matched = []
            for b in buildings:
                name = b.get('name', '')
                score = fuzzy_match_score(kw, name)
                if kw in name:
                    score = max(score, 0.9)
                if score > 0.4:
                    b_copy = dict(b)
                    b_copy['score'] = round(score, 3)
                    matched.append(b_copy)
            matched.sort(key=lambda x: x.get('score', 0), reverse=True)
            return json.dumps({
                "type": "建筑类型单方造价",
                "keyword": kw,
                "total_matches": len(matched),
                "results": matched
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "type": "建筑类型单方造价",
                "total": len(buildings),
                "results": buildings
            }, ensure_ascii=False)

    return json.dumps({"error": f"未知查询类型: {query_type}"}, ensure_ascii=False)


# ========== 工具分发 ==========
TOOL_FUNCTIONS = {
    "query_pipeline_indicator": query_pipeline_indicator,
    "query_cost_index": query_cost_index
}


def execute_tool(name, arguments):
    """执行工具函数"""
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        return func(**args)
    except Exception as e:
        return json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)
