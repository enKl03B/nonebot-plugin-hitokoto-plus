import httpx
import json
import asyncio
from typing import Dict, Optional, Any, Union, List, TypedDict

from nonebot.log import logger

from .config import Config, plugin_config

# 固定的请求超时时间（10秒）
TIMEOUT = 10


class HitokotoResponse(TypedDict, total=False):
    """一言API响应数据类型定义"""
    hitokoto: str  # 一言内容
    from_: str  # 来源，使用from_避免与Python关键字冲突
    from_who: Optional[str]  # 作者
    from_who_plain: str  # 格式化后的作者
    type: str  # 类型代码
    type_name: str  # 类型名称
    uuid: str  # 唯一标识


class APIError(Exception):
    """API调用异常"""
    pass


async def get_hitokoto(
    hitokoto_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取一条一言
    
    参数:
        hitokoto_type: 一言类型，可以是中文名称或类型代码
        
    返回:
        Dict[str, Any]: 一言数据，包含 hitokoto, from, from_who 等字段
    
    异常:
        APIError: API调用失败
    """
    params: Dict[str, str] = {}
    
    # 处理类型参数
    if hitokoto_type:
        # 清理字符串，去除前后空格
        hitokoto_type = hitokoto_type.strip()
        logger.debug(f"处理类型参数: {hitokoto_type}, 类型映射表: {plugin_config.hitp_type_map}")
        
        # 如果提供的是中文类型名称，转换为对应的类型代码
        if hitokoto_type in plugin_config.hitp_type_map:
            params["c"] = plugin_config.hitp_type_map[hitokoto_type]
            logger.debug(f"找到类型映射: {hitokoto_type} -> {params['c']}")
        else:
            # 尝试进行不区分大小写的匹配
            matched = False
            for name, code in plugin_config.hitp_type_map.items():
                if name.lower() == hitokoto_type.lower():
                    params["c"] = code
                    logger.debug(f"不区分大小写匹配到类型: {name} -> {code}")
                    matched = True
                    break
            
            # 如果仍然没有匹配，则假设提供的直接是类型代码
            if not matched:
                params["c"] = hitokoto_type
            logger.debug(f"使用原始类型代码: {hitokoto_type}")
    elif plugin_config.hitp_default_type:
        params["c"] = plugin_config.hitp_default_type
        
    # 添加JSON格式参数
    params["encode"] = "json"
    
    try:
        async with httpx.AsyncClient() as client:
            logger.debug(f"正在请求一言API: {plugin_config.hitp_api_url}，参数: {params}")
            response = await client.get(
                str(plugin_config.hitp_api_url), 
                params=params,
                timeout=TIMEOUT  # 使用固定超时时间
            )
            
            # 记录完整请求URL
            logger.debug(f"完整请求URL: {response.request.url}")
            
            # 检查HTTP状态码
            response.raise_for_status()
            
            # 解析JSON响应
            data: Dict[str, Any] = response.json()
            logger.debug(f"API返回数据: {data}")
            
            # 对返回数据进行处理，确保某些字段存在
            if "hitokoto" not in data:
                raise APIError("API返回数据格式不正确，缺少hitokoto字段")
                
            # 对可能不存在的字段进行处理，避免格式化时出错
            if "from" not in data or not data["from"]:
                data["from"] = "未知来源"
                
            if "from_who" not in data or not data["from_who"]:
                data["from_who"] = ""
                data["from_who_plain"] = "无"
            else:
                data["from_who"] = f"「{data['from_who']}」"
                data["from_who_plain"] = data["from_who"].strip("「」")
                
            # 添加类型的中文名称
            if "type" in data:
                # 反向查找类型映射表，获取中文名称
                type_code = data["type"]
                type_name = "未知类型"
                # 使用next()函数替代for循环查找匹配的类型名称
                try:
                    type_name = next(name for name, code in plugin_config.hitp_type_map.items() if code == type_code)
                except StopIteration:
                    pass
                data["type_name"] = type_name
                logger.debug(f"API返回类型代码: {type_code}, 映射为类型名称: {type_name}")
            else:
                data["type_name"] = "未知类型"
                
            return data
            
    except httpx.TimeoutException as e:
        logger.error("请求一言API超时")
        raise APIError("请求一言API超时，请稍后再试") from e
    except httpx.HTTPStatusError as e:
        logger.error(f"请求一言API失败: HTTP {e.response.status_code}")
        raise APIError(f"请求一言API失败: HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        logger.error(f"请求一言API网络错误: {str(e)}")
        raise APIError(f"请求一言API网络错误: {str(e)}") from e
    except json.JSONDecodeError as e:
        logger.error("一言API返回非JSON数据")
        raise APIError("一言API返回数据解析失败") from e
    except Exception as e:
        logger.exception("获取一言时发生未知错误")
        raise APIError(f"获取一言时发生未知错误: {str(e)}") from e


def format_hitokoto(data: Dict[str, Any]) -> str:
    """
    使用模板格式化一言数据
    
    参数:
        data: 一言数据
        
    返回:
        str: 格式化后的一言文本
    """
    try:
        return plugin_config.hitp_template.format(**data)
    except KeyError as e:
        logger.warning(f"格式化一言时缺少字段: {e}")
        # 使用一个简单的备用模板
        return f"{data['hitokoto']}"
    except Exception as e:
        logger.exception("格式化一言时发生错误")
        return f"{data['hitokoto']}" 