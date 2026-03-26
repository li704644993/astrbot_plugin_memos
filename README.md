# 📝 AstrBot Plugin - Memos 笔记同步

一个 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 插件，可将聊天消息（文字、图片）快速同步到 [Memos](https://github.com/usememos/memos) 笔记系统，并支持搜索、统计、管理等丰富功能。

## ✨ 功能特性

- 📄 **文字同步** — 将文字消息一键保存到 Memos
- 🖼️ **图片同步** — 支持下载聊天图片并作为附件上传到 Memos
- 🏷️ **标签搜索** — 按标签搜索笔记，支持合并转发消息展示（OneBot v11）
- 🔎 **关键词搜索** — 按内容关键词搜索笔记，结果以合并转发消息展示
- 📌 **笔记置顶** — 置顶/取消置顶重要笔记
- 📊 **统计数据** — 查看笔记总数、标签分布、内容类型等统计信息
- 🎲 **随机回顾** — 随机展示一条历史笔记，帮助复习
- 📋 **笔记列表** — 查看最近的笔记
- 🗑️ **删除笔记** — 通过 ID 删除指定笔记
- 🏷️ **自动标签** — 创建笔记时自动添加预设标签
- 🔒 **权限控制** — 支持限制允许使用的用户和群组

## 📦 安装

在 AstrBot 管理面板中搜索 `astrbot_plugin_memos` 安装，或手动克隆到插件目录：

```bash
cd /path/to/astrbot/data/plugins
git clone https://github.com/li704644993/astrbot_plugin_memos.git
```

## ⚙️ 配置

安装后在 AstrBot 管理面板的插件配置页面中设置以下参数：

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `memos_url` | string | ✅ | `""` | Memos 实例地址，例如 `https://note.example.com` |
| `memos_access_token` | string | ✅ | `""` | 在 Memos 设置中生成的 Access Token |
| `default_tags` | list | ❌ | `[]` | 创建 Memo 时自动添加的标签，例如 `["日记", "笔记"]` |
| `default_visibility` | string | ❌ | `"PRIVATE"` | Memo 默认可见性：`PRIVATE` / `PROTECTED` / `PUBLIC` |
| `allowed_user_ids` | list | ❌ | `[]` | 允许使用的用户 ID 列表，为空则不限制 |
| `allowed_group_ids` | list | ❌ | `[]` | 允许使用的群组 ID 列表，为空则不限制 |
| `bot_uin` | string | ❌ | `""` | 机器人 QQ 号，用于合并转发消息的发送者身份（OneBot v11） |
| `bot_name` | string | ❌ | `"Memos 助手"` | 合并转发消息中显示的发送者名称 |
| `memos_page_size` | int | ❌ | `20` | 按标签/关键词搜索时每次最多返回的笔记数量（1~50） |

### 获取 Memos Access Token

1. 登录你的 Memos 实例
2. 进入 **设置** → **Access Tokens**
3. 点击 **Create** 创建一个新令牌
4. 将生成的令牌复制到插件配置中

### 合并转发消息（OneBot v11）

如果你使用 OneBot v11 协议（如 go-cqhttp / Lagrange 等），配置 `bot_uin`（机器人 QQ 号）后，`/note_tag` 和 `/note_search` 的搜索结果将以 **合并转发消息** 的形式发送，避免刷屏。

未配置 `bot_uin` 时，将以普通文本消息发送搜索结果。

## 🎯 指令说明

### 基础功能

| 指令 | 说明 | 示例 |
|------|------|------|
| `/note <内容>` | 将文字/图片同步到 Memos | `/note 今天学习了 Python` |
| `/note_list [数量]` | 查看最近的笔记，默认 5 条，最多 20 条 | `/note_list 10` |
| `/note_delete <ID>` | 删除指定 ID 的笔记 | `/note_delete 123` |

### 搜索功能

| 指令 | 说明 | 示例 |
|------|------|------|
| `/note_tag <标签>` | 按标签搜索笔记（支持合并转发消息） | `/note_tag 日记` 或 `/note_tag #日记` |
| `/note_search <关键词>` | 按内容关键词搜索笔记 | `/note_search 学习笔记` |

### 管理功能

| 指令 | 说明 | 示例 |
|------|------|------|
| `/note_pin <ID>` | 置顶/取消置顶笔记（切换状态） | `/note_pin 123` |
| `/note_stats` | 查看统计数据（笔记总数、标签分布等） | `/note_stats` |
| `/note_random` | 随机回顾一条历史笔记 | `/note_random` |

### 使用示例

**同步文字：**

```
/note 今天的学习笔记：完成了 AstrBot 插件开发
```

**同步图片：**

发送 `/note 这是一张风景照` 并附带图片，插件会自动下载图片并上传到 Memos 作为附件。

**按标签搜索（合并转发消息）：**

```
/note_tag 日记       # 搜索包含 #日记 标签的所有笔记
/note_tag #工作      # 也支持带 # 前缀
```

> 💡 搜索结果将以合并转发消息发送（需配置 `bot_uin`），每条笔记包含完整内容、日期、ID 和可见性标识。

**查看统计：**

```
/note_stats
```

输出示例：

```
📊 Memos 统计数据

📝 笔记总数：156
📌 置顶笔记：2 条

📈 内容类型：
  🔗 含链接：45 条
  💻 含代码：23 条
  ☑️ 待办事项：8 条未完成

🏷️ 标签统计（Top 15）：
  #工作  ×52
  #个人  ×28
  #学习  ×15
```

**随机回顾：**

```
/note_random
```

## 🔒 权限控制

插件支持通过白名单方式控制使用权限：

- **两个列表都为空** → 所有人均可使用（不做限制）
- **设置了 `allowed_user_ids`** → 仅列表中的用户可使用
- **设置了 `allowed_group_ids`** → 仅在列表中的群组内可使用
- 用户白名单和群组白名单是 **或** 的关系，满足其一即可

所有指令均受权限控制。

## 🛠️ 依赖

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) >= 3.0
- [Memos](https://github.com/usememos/memos) 实例（需要 API v1 支持）
- Python 依赖：`httpx`（AstrBot 内置，无需额外安装）
- 合并转发消息功能需要 OneBot v11 协议适配器（如 aiocqhttp）

## 📄 许可证

[MIT License](LICENSE)
