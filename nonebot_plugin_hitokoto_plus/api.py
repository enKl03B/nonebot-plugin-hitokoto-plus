from typing import Optional, Dict, Any
import httpx
from pydantic import BaseModel, Field
import asyncio
from nonebot import logger
from nonebot.compat import model_dump

class HitokotoSentence(BaseModel):
    """一言句子模型
    
    用于存储和处理从一言API获取的句子数据的Pydantic模型
    包含句子的所有属性，例如内容、来源、作者等
    """
    id: int                # 句子ID
    uuid: str              # 句子UUID
    hitokoto: str          # 句子内容
    type: str              # 句子类型
    from_: str = Field(..., alias="from")  # 句子来源，使用别名适配API返回
    from_who: Optional[str] = None  # 句子作者，可能为空
    creator: str           # 创建者
    creator_uid: int       # 创建者UID
    reviewer: int          # 审核者ID
    commit_from: str       # 提交来源
    created_at: str        # 创建时间
    length: int            # 句子长度

    def model_dump(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return model_dump(self)

    def dict(self) -> Dict[str, Any]:
        """兼容Pydantic v1的字典转换方法"""
        return self.model_dump()

class APIError(Exception):
    """API调用相关错误的基类"""
    pass

class RequestError(APIError):
    """请求发送失败的错误"""
    pass

class ResponseError(APIError):
    """响应解析失败的错误"""
    pass

class HitokotoAPI:
    """一言API客户端
    
    负责与一言API通信，获取句子并进行格式化处理
    """
    
    def __init__(self, api_url: str = "https://v1.hitokoto.cn"):
        """初始化API客户端
        
        Args:
            api_url: 一言API的基础URL，默认为官方API
        """
        self.api_url = api_url
        # 设置较短的超时时间，避免请求卡住
        self.client = httpx.AsyncClient(timeout=10.0)
        # 重试相关设置
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 1  # 重试延迟（秒）
        
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
        
    async def get_hitokoto(self, 
                           sentence_type: Optional[str] = None) -> HitokotoSentence:
        """
        获取一言句子
        
        Args:
            sentence_type: 句子类型，可选 a~l，对应不同分类
            
        Returns:
            HitokotoSentence: 一言句子对象
        """
        # 确保类型参数有效
        if sentence_type:
            # 确保类型是单个字母
            if len(sentence_type) > 1:
                logger.warning(f"类型参数过长，只取第一个字符: {sentence_type[0]}")
                sentence_type = sentence_type[0]
            
            # 确保类型在有效范围内
            valid_types = "abcdefghijkl"
            if sentence_type not in valid_types:
                logger.warning(f"无效的类型参数: {sentence_type}，使用默认类型")
                sentence_type = None
            else:
                pass # 类型有效
        
        # 构建参数
        params = {}
        if sentence_type:
            # API参数c对应句子类型
            params["c"] = sentence_type
        else:
            pass # 无需特定参数
            
        # 发送请求，带重试机制
        for retry in range(self.max_retries):
            try:
                # 发起请求
                response = await self.client.get(self.api_url, params=params)
                response.raise_for_status()  # 检查HTTP状态码
                
                # 解析JSON数据
                try:
                    data = response.json()
                except Exception as e:
                    raise ResponseError(f"解析API响应JSON失败: {e}")
                
                # 检查返回数据是否包含必要字段
                if "hitokoto" not in data:
                    raise ResponseError("API返回的数据缺少必要的字段")
                
                # 转换为模型对象并返回
                try:
                    return HitokotoSentence(**data)
                except Exception as e:
                    raise ResponseError(f"转换句子数据为模型失败: {e}")
                
            except httpx.RequestError as e:
                # 网络请求错误
                logger.warning(f"请求一言API失败 (尝试 {retry+1}/{self.max_retries}): {e}")
                if retry == self.max_retries - 1:
                    # 最后一次重试仍失败
                    raise RequestError(f"请求一言API失败，网络错误: {str(e)}")
                # 等待后重试
                await asyncio.sleep(self.retry_delay)
                
            except httpx.HTTPStatusError as e:
                # HTTP状态码错误
                logger.warning(f"API返回错误状态码 (尝试 {retry+1}/{self.max_retries}): {e}")
                if retry == self.max_retries - 1:
                    # 最后一次重试仍失败
                    raise RequestError(f"API返回错误: HTTP {e.response.status_code}")
                # 等待后重试
                await asyncio.sleep(self.retry_delay)
                
            except ResponseError as e:
                # 响应处理错误，直接抛出
                logger.error(f"处理API响应失败: {e}")
                raise
                
            except Exception as e:
                # 其他未预期的错误
                logger.error(f"获取一言时发生未知错误: {e}")
                if retry == self.max_retries - 1:
                    # 最后一次重试仍失败
                    raise ResponseError(f"处理一言API请求时发生未知错误: {str(e)}")
                # 等待后重试
                await asyncio.sleep(self.retry_delay)
    
    def format_sentence(self, sentence: HitokotoSentence, 
                         with_source: bool = True, 
                         with_author: bool = True) -> str:
        """
        格式化一言句子，生成用于展示的文本
        
        Args:
            sentence: 一言句子对象
            with_source: 是否包含来源
            with_author: 是否包含作者
            
        Returns:
            str: 格式化后的句子文本
        """
        # 句子内容必须包含
        result = sentence.hitokoto
        
        # 添加分割线
        result += "\n-------------------"
        
        # 添加来源信息（如果有且需要显示）
        if with_source and sentence.from_ and sentence.from_.strip():
            result += f"\n来源：{sentence.from_}"
            
        # 添加作者信息（如果有且需要显示）
        if with_author and sentence.from_who and sentence.from_who.strip():
            result += f"\n作者：{sentence.from_who}"
            
        return result 