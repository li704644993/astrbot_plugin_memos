# 📝 AstrBot Plugin - Memos 笔记同步

一个 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 插件，可将聊天消息（文字、图片）快速同步到 [Memos](https://github.com/usememos/memos) 笔记系统。

## ✨ 功能特性

- 📄 **文字同步** — 将文字消息一键保存到 Memos
- 🖼️ **图片同步** — 支持下载聊天图片并作为附件上传到 Memos
- 🏷️ **自动标签** — 创建笔记时自动添加预设标签
- 📋 **查看笔记** — 查看最近的 Memos 笔记列表
- 🗑️ **删除笔记** — 通过 ID 删除指定笔记
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
| `default_visibility` | string | ❌ | `"PRIVATE"` | Memo 的默认可见性：`PRIVATE`（私有）、`PROTECTED`（受保护）、`PUBLIC`（公开） |
| `allowed_user_ids` | list | ❌ | `[]` | 允许使用的用户 ID 列表，为空则不限制 |
| `allowed_group_ids` | list | ❌ | `[]` | 允许使用的群组 ID 列表，为空则不限制 |

### 获取 Memos Access Token

1. 登录你的 Memos 实例
2. 进入 **设置** → **Access Tokens**
3. 点击 **Create** 创建一个新令牌
4. 将生成的令牌复制到插件配置中

## 🎯 指令说明

| 指令 | 说明 | 示例 |
|------|------|------|
| `/note <内容>` | 将文字/图片同步到 Memos | `/note 今天学习了 Python` |
| `/note_list [数量]` | 查看最近的笔记，默认 5 条，最多 20 条 | `/note_list 10` |
| `/note_delete <ID>` | 删除指定 ID 的笔记 | `/note_delete 123` |

### 使用示例

**同步文字：**

```
/note 今天的学习笔记：完成了 AstrBot 插件开发
```

**同步图片：**

发送 `/note 这是一张风景照` 并附带图片，插件会自动下载图片并上传到 Memos 作为附件。

**查看笔记：**

```
/note_list       # 查看最近 5 条
/note_list 10    # 查看最近 10 条
```

**删除笔记：**

```
/note_delete 42  # 删除 ID 为 42 的笔记
```

## 🔒 权限控制

插件支持通过白名单方式控制使用权限：

- **两个列表都为空** → 所有人均可使用（不做限制）
- **设置了 `allowed_user_ids`** → 仅列表中的用户可使用
- **设置了 `allowed_group_ids`** → 仅在列表中的群组内可使用
- 用户白名单和群组白名单是 **或** 的关系，满足其一即可

## 🛠️ 依赖

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) >= 3.0
- [Memos](https://github.com/usememos/memos) 实例（需要 API v1 支持）
- Python 依赖：`httpx`（AstrBot 内置，无需额外安装）

## 📄 许可证

[MIT License](LICENSE)
