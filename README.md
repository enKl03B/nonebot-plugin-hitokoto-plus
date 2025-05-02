# 一言+


（可能是）更好的一言插件！

一个基于 [NoneBot2](https://github.com/nonebot/nonebot2) 的一言（Hitokoto）插件，用于获取来自 [Hitokoto.cn](https://hitokoto.cn/) 的一句话。

插件名：`nonebot-plugin-hitokoto-plus`

## 特性
- ✅ 句子类型自定义
- ✅ 频率限制和黑白名单支持
- ✅ 收藏功能

## 安装

### 通过 nb-cli 安装（推荐）

```bash
nb plugin install nonebot-plugin-hitokoto-plus
```

### 通过 pip 安装

```bash
pip install nonebot-plugin-hitokoto-plus
```



## 使用方法

> [!WARNING]
> 此处示例中的"/"为 nb 默认的命令开始标志，若您设置了另外的标志，则请使用您设置的标志作为命令的开头

### 基础命令

```
/一言          # 随机获取一条一言
/一言 [类型]   # 获取指定类型的一言
```

（参数允许字母/中文，即`/一言 a` 和 `/一言 动画`均为正确命令，具体参照参数说明一节）

### 收藏功能

```
/一言收藏           # 收藏上一次获取的一言
/一言收藏列表       # 查看收藏列表
/一言收藏列表 -p 2  # 查看收藏列表 第2页
/一言查看收藏 1     # 查看序号为1的收藏详情
/一言删除收藏 1     # 删除序号为1的收藏
```

### 帮助命令

```
/一言帮助           # 获取插件总帮助
/一言帮助 基础      # 获取基础命令帮助
/一言帮助 收藏      # 获取收藏功能帮助
/一言帮助 类型      # 获取支持的一言类型列表
```


> [!NOTE]
> 获取句子后，系统会提示在指定时间内可以使用收藏命令将该句子收藏。超过这个时间后将无法收藏，需要重新获取句子。


## 参数说明

| 字母 | 中文 |
| --- | --- |
| a | 动画 |
| b | 漫画 |
| c | 游戏 |
| d | 文学 |
| e | 原创 |
| f | 网络 |
| g | 其他 |
| h | 影视 |
| i | 诗词 |
| j | 网易云 |
| k | 哲学 |
| l | 抖机灵 |



## 配置项


在 NoneBot2 全局配置文件中（通常是 `.env` 或 `.env.prod` 文件）添加以下配置：

> [!IMPORTANT]
> 所有配置项都需要加上 `hitp_` 前缀，例如 `hitp_api_url="https://v1.hitokoto.cn"`。下表中的名称已包含此前缀。

> [!WARNING]
> 指定的API地址必须支持与[一言开发者中心](https://developer.hitokoto.cn/sentence/#%E8%AF%B7%E6%B1%82%E5%8F%82%E6%95%B0)提供的请求参数和句子类型调用（返回格式化的JSON文本）
>
> 一言开发者中心提供的可选API地址如下：
> | 地址                            | 协议    | 方法  | QPS 限制 | 线路 |
> |-------------------------------|-------|-----|--------|----|
> | `v1.hitokoto.cn`              | HTTPS | Any | 2     | 全球 |
> | `international.v1.hitokoto.cn` | HTTPS | Any | 20(含缓存*)     | 海外 |

| 配置项 | 类型 | 必填 | 默认值 | 说明 | 示例 |
|:-----:|:----:|:---:|:-----:|:----:|:----:|
| hitp_api_url | str | 否 | https://v1.hitokoto.cn | 一言API地址 |  |
| hitp_default_type | str | 否 | None | 默认一言类型，为空则随机 | a |
| hitp_cd | int | 否 | 3 | 调用冷却时间（秒） |  |
| hitp_cooldown_cleanup_interval | int | 否 | 360 | 冷却记录清理间隔（秒） |  |
| hitp_user_retention_time | int | 否 | 720 | 用户记录保留时间（秒） |  |
| hitp_favorite_list_limit | int | 否 | 10 | 收藏列表每页显示数量 |  |
| hitp_favorite_timeout | int | 否 | 30 | 收藏提示超时时间（秒） |  |
| hitp_use_whitelist | bool | 否 | False | 权限控制模式，True为白名单，False为黑名单 |  |
| hitp_user_list | list | 否 | [] | 用户ID列表，格式为"platform:user_id" | ["onebot11:12345678", "kook:87654321"] |
| hitp_group_list | list | 否 | [] | 群组ID列表，格式为"platform:group_id" | ["onebot11:87654321", "kook:12345678"] |


> [!NOTE]
> `适配器名称` 参考:
> 
> | 适配器名称 | 平台/协议 |
> |:----------|:---------|
> | `onebot11` | OneBot V11  |
> | `onebot12` | OneBot V12  |
> | `console` | Console |
> | `kook`    | KOOK (开黑啦) |
> | `telegram`| Telegram |
> | `feishu`  | 飞书 |
> | `discord` | Discord |
> | `qq`      | QQ (官方) |
> | `satori`  | Satori |
> | `dodo`    | DoDo |
> | `kritor`  | Kritor |
> | `mirai`   | Mirai |
> | `mail`    | Mail |
> | `wxmp`    | 微信公众号 |
>


## 注意事项
- 该插件代码基本由AI完成，如有更好的改进建议欢迎提交pr
- 目前仅使用了`Onebot适配器+Napcat`，在Windows/Linux系统下测试通过，如有兼容性问题/其他适配器的运行情况欢迎提交issue
- 尝试进行了跨平台兼容，但运行情况未知



## 更新日志

### 0.3.5
修复一个Bug

### 0.3.1-0.3.3
优化

### 0.3.0
**完全重构**

<details>
<summary>旧版日志</summary>

### 0.2.4
修复一些已知问题，重写部分组件
> [!IMPORTANT]
> 自0.2.4版本起，依赖与配置项均发生改变，请注意查看

### 0.2.3
添加对跨平台用户的区分

### 0.2.2
修复导入，移除不必要依赖

### 0.2.1
修复配置项相关问题

### 0.2.0
插件首次发布

### 0.1.0
暂无

</details>



## 致谢

- [Hitokoto.cn](https://hitokoto.cn/) - 提供一言 API 服务，数据源 
- [NoneBot2](https://github.com/nonebot/nonebot2) - 跨平台 Python 异步机器人框架 
- [nonebot-plugin-alconna](https://github.com/nonebot/plugin-alconna) - 强大的命令解析器，实现跨平台支持 
- [noneBot-plugin-localStore](https://github.com/nonebot/plugin-localstore) - NoneBot 本地数据存储插件，实现本地数据存储 
- [nonebot-plugin-uninfo](https://github.com/RF-Tar-Railt/nonebot-plugin-uninfo) - Nonebot2 多平台的会话信息(用户、群组、频道)获取插件,实现对用户信息的获取 
- [nonebot-plugin-apscheduler](https://github.com/nonebot/plugin-apscheduler)：NoneBot APScheduler 定时任务插件，实现冷却时间记录的清理

以及所有相关项目和开发者❤ 

## 许可证
MIT
