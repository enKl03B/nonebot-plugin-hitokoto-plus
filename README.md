# 一言+

> [!IMPORTANT]
> 项目正在重构，新版将**完全不兼容**0.2.4及以下版本

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

### 基本命令

- `/一言` 或 `/hitokoto` - 获取随机一言
- `/一言 --help` - 显示帮助信息

### 高级用法

指定句子类型：

- `/一言 a` - 获取一条动画类型的一言
- `/一言 b` - 获取一条漫画类型的一言
- `/一言 c` - 获取一条游戏类型的一言
- 更多类型见下方"参数说明"

### 收藏功能

- `/一言收藏` - 收藏上一次获取的句子
- `/一言收藏列表 [页码]` - 查看已收藏的句子，可选参数：页码
- `/一言收藏删除 <序号>` - 删除指定序号的收藏
- `/一言收藏详情 <序号>` - 查看指定序号收藏的详细信息
- `/一言收藏 --help` - 显示收藏功能帮助信息

> [!NOTE]
> 收藏列表支持分页显示，每页显示固定数量的句子，防止单条消息过长。使用 `/一言收藏列表 [页码]` 可以查看指定页码的收藏列表。
> 
> 获取句子后，系统会提示在指定时间内可以使用收藏命令将该句子收藏。超过这个时间后将无法收藏，需要重新获取句子。
>
> 收藏详情和删除命令支持批量操作，例如 `/一言收藏详情 1 2 3` 可以查看多个收藏的详细信息，`/一言收藏删除 1 2 3` 可以删除多个收藏。

### 参数说明

句子类型（字母）：

| 参数 | 说明 |
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


可参考仓库根目录的[.env.example](./.env.example)文件进行配置

在 NoneBot2 全局配置文件中（通常是 `.env` 或 `.env.prod` 文件）添加以下配置：

> [!IMPORTANT]
> 所有配置项都需要加上 `HITP_` 前缀，例如 `HITP_API_URL="https://v1.hitokoto.cn"`。下表中的名称已包含此前缀。

### 基础配置

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:---:|:-----:|:----:|
| HITP_DEFAULT_TYPE | str | 否 | None | 默认句子类型，不设置则随机 | 
| HITP_API_URL | str | 否 | "https://v1.hitokoto.cn" | API地址 |
> [!WARNING]
> 指定的API地址必须支持与[一言开发者中心](https://developer.hitokoto.cn/sentence/#%E8%AF%B7%E6%B1%82%E5%8F%82%E6%95%B0)提供的请求参数和句子类型调用（返回格式化的JSON文本）
>
> 一言开发者中心提供的可选API地址如下：
> | 地址                            | 协议    | 方法  | QPS 限制 | 线路 |
> |-------------------------------|-------|-----|--------|----|
> | `v1.hitokoto.cn`              | HTTPS | Any | 2     | 全球 |
> | `international.v1.hitokoto.cn` | HTTPS | Any | 20(含缓存*)     | 海外 |


### 收藏配置

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:---:|:-----:|:----:|
| HITP_MAX_FAVORITES_PER_USER | int | 否 | 100 | 每个用户最大收藏数量 |
| HITP_FAVORITES_PER_PAGE | int | 否 | 5 | 收藏列表每页显示的句子数量 |
| HITP_FAVORITE_TIMEOUT | int | 否 | 60 | 收藏超时时间（秒），在获取句子后多长时间内可以收藏 |
| HITP_MAX_DETAILS_PER_REQUEST | int | 否 | 3 | 单次查看收藏句子详情的最大数量，超过则被拦截 |


### 权限、频率配置

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:---:|:-----:|:----:|
| HITP_ENABLE_PRIVATE_CHAT | bool | 否 | True | 是否允许私聊使用 |
| HITP_ENABLE_GROUP_CHAT | bool | 否 | True | 是否允许群聊使用 |
| HITP_RATE_LIMIT_PRIVATE | int | 否 | 5 | 私聊频率限制（秒） |
| HITP_RATE_LIMIT_GROUP | int | 否 | 10 | 群聊频率限制（秒） |


### 黑白名单设置

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:---:|:-----:|:----:|
| HITP_ENABLE_WHITELIST | bool | 否 | False | 是否启用白名单 |
| HITP_ENABLE_BLACKLIST | bool | 否 | False | 是否启用黑名单 |
| HITP_WHITELIST_USERS | list | 否 | [] | 白名单用户列表，格式为 `适配器名称:用户ID`，例如 `["onebot11:12345", "discord:98765"]` |
| HITP_BLACKLIST_USERS | list | 否 | [] | 黑名单用户列表，格式为 `适配器名称:用户ID`，例如 `["onebot11:54321", "kook:112233"]` |
| HITP_WHITELIST_GROUPS | list | 否 | [] | 白名单群组列表，格式为 `适配器名称:群组ID`，例如 `["onebot11:10001", "discord:20002"]` |
| HITP_BLACKLIST_GROUPS | list | 否 | [] | 黑名单群组列表，格式为 `适配器名称:群组ID`，例如 `["onebot11:10003", "kook:20004"]` |

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



## 鸣谢

- [Hitokoto.cn](https://hitokoto.cn/) - 提供一言 API 服务，数据源 
- [NoneBot2](https://github.com/nonebot/nonebot2) - 跨平台 Python 异步机器人框架 
- [nonebot-plugin-alconna](https://github.com/nonebot/plugin-alconna) - 强大的命令解析器，实现跨平台支持 
- [noneBot-plugin-localStore](https://github.com/nonebot/plugin-localstore) - NoneBot 本地数据存储插件，实现本地数据存储 
- [nonebot-plugin-uninfo](https://github.com/RF-Tar-Railt/nonebot-plugin-uninfo) - Nonebot2 多平台的会话信息(用户、群组、频道)获取插件,实现对用户信息的获取 

以及所有相关项目❤ 

## 许可证
MIT