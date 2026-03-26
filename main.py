import base64
import mimetypes
import os
import random
import time
from typing import Optional, List

import httpx

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp


@register("astrbot_plugin_memos", "liting", "将消息内容同步到 Memos 笔记系统", "1.0.0", "https://github.com/liting/astrbot_plugin_memos")
class MemosPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 从配置中读取
        self.memos_url: str = config.get("memos_url", "").rstrip("/")
        self.memos_access_token: str = config.get("memos_access_token", "")
        self.default_tags: list = config.get("default_tags", [])
        self.default_visibility: str = config.get("default_visibility", "PRIVATE")
        self.allowed_user_ids: list = config.get("allowed_user_ids", [])
        self.allowed_group_ids: list = config.get("allowed_group_ids", [])
        self.bot_uin: str = config.get("bot_uin", "")
        self.bot_name: str = config.get("bot_name", "Memos 助手")
        self.memos_page_size: int = max(1, min(config.get("memos_page_size", 20), 50))

        # 资源临时存储目录
        self.resource_dir = os.path.join(os.path.dirname(__file__), "memos_resources")

    async def initialize(self):
        """插件初始化"""
        if not self.memos_url or not self.memos_access_token:
            logger.warning("[Memos] 插件配置不完整，请在管理面板中配置 Memos 地址和访问令牌。")
        else:
            logger.info(f"[Memos] 插件已加载，Memos 地址: {self.memos_url}")

    # ========================
    # 权限校验
    # ========================

    def _is_authorized(self, event: AstrMessageEvent) -> bool:
        """检查用户是否有权限使用本插件。
        
        规则：
        - 如果 allowed_user_ids 和 allowed_group_ids 都为空，则不限制（所有人可用）
        - 如果用户ID在 allowed_user_ids 中，允许
        - 如果群组ID在 allowed_group_ids 中，允许
        - 否则拒绝
        """
        # 两个列表都为空，不做限制
        if not self.allowed_user_ids and not self.allowed_group_ids:
            return True

        sender_id = str(event.get_sender_id())
        
        # 检查用户ID白名单
        if self.allowed_user_ids:
            if sender_id in [str(uid) for uid in self.allowed_user_ids]:
                return True

        # 检查群组ID白名单
        if self.allowed_group_ids:
            # AstrBot 中群消息的 session_id 通常包含群组标识
            session_id = str(event.session_id) if hasattr(event, "session_id") else ""
            for gid in self.allowed_group_ids:
                if str(gid) in session_id:
                    return True

        return False

    # ========================
    # Memos API 相关方法
    # ========================

    def _get_headers(self) -> dict:
        """获取 API 请求头"""
        return {
            "Authorization": f"Bearer {self.memos_access_token}",
            "Content-Type": "application/json",
        }

    def _build_content(self, text: str) -> str:
        """构建带默认标签的内容"""
        tags_text = " ".join([f"#{tag}" for tag in self.default_tags])
        if text and tags_text:
            return f"{text}\n{tags_text}"
        elif text:
            return text
        elif tags_text:
            return tags_text
        return ""

    async def _post_memo_text(self, content: str) -> Optional[str]:
        """发送纯文本内容到 Memos，返回 memo_id"""
        url = f"{self.memos_url}/api/v1/memos"
        payload = {
            "content": self._build_content(content),
            "visibility": self.default_visibility,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                memo_name = result.get("name")
                if memo_name:
                    memo_id = memo_name.split("/")[-1]
                    logger.info(f"[Memos] 成功创建 Memo，ID: {memo_id}")
                    return memo_id
                else:
                    logger.error("[Memos] API 响应中未找到 name 字段")
                    return None
        except Exception as e:
            logger.error(f"[Memos] 发送文本失败: {e}")
            return None

    async def _upload_file(self, file_path: str, file_name: str) -> Optional[str]:
        """上传文件到 Memos，返回 attachment name（如 attachments/xxx）"""
        url = f"{self.memos_url}/api/v1/attachments"
        try:
            with open(file_path, "rb") as fh:
                file_bytes = fh.read()

            b64_content = base64.urlsafe_b64encode(file_bytes).decode()
            payload = {
                "filename": file_name,
                "content": b64_content,
                "type": mimetypes.guess_type(file_name)[0] or "application/octet-stream",
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                attachment_name = result.get("name")
                if attachment_name:
                    logger.info(f"[Memos] 成功上传文件，attachment: {attachment_name}")
                    return attachment_name
                else:
                    logger.error("[Memos] 文件上传响应中未找到 name 字段")
                    return None
        except Exception as e:
            logger.error(f"[Memos] 上传文件失败: {e}")
            return None

    async def _post_memo_with_attachments(self, content: str, attachment_names: List[str]) -> Optional[str]:
        """发送带附件的内容到 Memos"""
        url = f"{self.memos_url}/api/v1/memos"
        payload = {
            "content": self._build_content(content),
            "visibility": self.default_visibility,
            "attachments": [{"name": name} for name in attachment_names],
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                memo_name = result.get("name")
                if memo_name:
                    memo_id = memo_name.split("/")[-1]
                    logger.info(f"[Memos] 成功创建带附件的 Memo，ID: {memo_id}")
                    return memo_id
                else:
                    logger.error("[Memos] API 响应中未找到 name 字段")
                    return None
        except Exception as e:
            logger.error(f"[Memos] 发送带附件内容失败: {e}")
            return None

    async def _list_memos_by_filter(self, filter_expr: str, page_size: int = 20) -> List[dict]:
        """根据过滤条件查询 Memos 列表，支持分页获取全部结果"""
        url = f"{self.memos_url}/api/v1/memos"
        all_memos: List[dict] = []
        page_token = None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while True:
                    params = {
                        "filter": filter_expr,
                        "orderBy": "display_time desc",
                        "pageSize": page_size,
                    }
                    if page_token:
                        params["pageToken"] = page_token

                    response = await client.get(url, headers=self._get_headers(), params=params)
                    response.raise_for_status()
                    result = response.json()

                    memos = result.get("memos", [])
                    all_memos.extend(memos)

                    page_token = result.get("nextPageToken")
                    if not page_token or len(all_memos) >= page_size:
                        break

            return all_memos[:page_size]
        except Exception as e:
            logger.error(f"[Memos] 查询 Memos 失败 (filter={filter_expr}): {e}")
            return []

    async def _search_memos_by_tag(self, tag: str) -> List[dict]:
        """按标签搜索 Memos（使用 CEL 表达式 tags contains）"""
        filter_expr = f"tags contains '{tag}'"
        return await self._list_memos_by_filter(filter_expr, self.memos_page_size)

    async def _search_memos_by_content(self, keyword: str) -> List[dict]:
        """按内容关键词搜索 Memos"""
        filter_expr = f"content.contains('{keyword}')"
        return await self._list_memos_by_filter(filter_expr, self.memos_page_size)

    async def _get_random_memo(self) -> Optional[dict]:
        """获取随机一条笔记"""
        url = f"{self.memos_url}/api/v1/memos"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 先获取较大范围的笔记
                params = {"pageSize": 50, "orderBy": "display_time desc"}
                response = await client.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                result = response.json()
                memos = result.get("memos", [])
                if memos:
                    return random.choice(memos)
                return None
        except Exception as e:
            logger.error(f"[Memos] 获取随机笔记失败: {e}")
            return None

    async def _update_memo(self, memo_id: str, update_fields: dict, update_paths: List[str]) -> bool:
        """更新 Memo 的指定字段"""
        url = f"{self.memos_url}/api/v1/memos/{memo_id}"
        payload = {
            "memo": {
                "name": f"memos/{memo_id}",
                **update_fields,
            },
            "updateMask": {
                "paths": update_paths,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"[Memos] 更新 Memo 失败 (ID={memo_id}): {e}")
            return False

    async def _get_user_stats(self) -> Optional[dict]:
        """获取用户统计数据"""
        # 先尝试获取当前用户信息
        url = f"{self.memos_url}/api/v1/users/me"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                user_info = response.json()
                user_name = user_info.get("name", "")
                # user_name 格式为 "users/1"，提取 user_id
                user_id = user_name.split("/")[-1] if user_name else "me"

                # 获取统计数据
                stats_url = f"{self.memos_url}/api/v1/users/{user_id}:getStats"
                stats_resp = await client.get(stats_url, headers=self._get_headers())
                stats_resp.raise_for_status()
                return stats_resp.json()
        except Exception as e:
            logger.error(f"[Memos] 获取用户统计失败: {e}")
            return None

    # ========================
    # 消息构建辅助方法
    # ========================

    def _build_memo_node(self, memo: dict, index: int = 0) -> "Comp.Node":
        """将单条 Memo 数据构建为合并转发 Node 消息"""
        content = memo.get("content", "（无内容）")
        memo_name = memo.get("name", "")
        memo_id = memo_name.split("/")[-1] if memo_name else "?"
        create_time = memo.get("createTime", "未知时间")
        if "T" in create_time:
            create_time = create_time.split("T")[0]
        pinned = "📌 " if memo.get("pinned") else ""
        visibility = memo.get("visibility", "PRIVATE")
        vis_icon = {"PUBLIC": "🌐", "PROTECTED": "🔓", "PRIVATE": "🔒"}.get(visibility, "")

        text = f"{pinned}{vis_icon} [{create_time}] ID:{memo_id}\n\n{content}"

        uin = int(self.bot_uin) if self.bot_uin.isdigit() else 0
        return Comp.Node(
            uin=uin,
            name=self.bot_name,
            content=[Comp.Plain(text)],
        )

    # ========================
    # 图片处理相关方法
    # ========================

    async def _download_image(self, url: str, filename: str) -> Optional[str]:
        """下载图片到本地临时目录"""
        if not os.path.exists(self.resource_dir):
            os.makedirs(self.resource_dir)
        file_path = os.path.join(self.resource_dir, filename)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                with open(file_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"[Memos] 成功下载图片: {file_path}")
                return file_path
        except Exception as e:
            logger.error(f"[Memos] 下载图片失败: {e}")
            return None

    def _cleanup_file(self, file_path: str):
        """清理临时文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"[Memos] 已清理临时文件: {file_path}")
        except Exception as e:
            logger.error(f"[Memos] 清理文件失败: {e}")

    # ========================
    # 指令处理
    # ========================

    @filter.command("note")
    async def note_handler(self, event: AstrMessageEvent):
        """将消息同步到 Memos 笔记系统。用法：/note 你的笔记内容（可附带图片）"""

        # 权限校验
        if not self._is_authorized(event):
            yield event.plain_result("❌ 你没有权限使用此功能。")
            return

        # 检查配置
        if not self.memos_url or not self.memos_access_token:
            yield event.plain_result("❌ Memos 插件未配置，请在管理面板中设置 Memos 地址和访问令牌。")
            return

        # 获取文本内容
        # event.message_str 包含完整的消息文本（含指令名），需要去除 "note" 前缀
        raw_text = event.message_str.strip()
        if raw_text.startswith("note"):
            text_content = raw_text[4:].strip()
        else:
            text_content = raw_text

        # 获取消息链中的图片
        message_chain = event.get_messages()
        image_urls: List[str] = []
        for comp in message_chain:
            if isinstance(comp, Comp.Image):
                if comp.file and (comp.file.startswith("http://") or comp.file.startswith("https://")):
                    image_urls.append(comp.file)
                elif comp.url:
                    image_urls.append(comp.url)

        # 校验内容
        if not text_content and not image_urls:
            yield event.plain_result("❌ 请提供要同步的内容，例如：/note 今天的学习笔记")
            return

        yield event.plain_result("⏳ 正在同步内容到 Memos...")

        try:
            if image_urls:
                # 处理带图片的消息
                attachment_names: List[str] = []
                downloaded_files: List[str] = []

                for i, img_url in enumerate(image_urls):
                    filename = f"memo_img_{int(time.time())}_{i}.jpg"
                    file_path = await self._download_image(img_url, filename)
                    if file_path:
                        downloaded_files.append(file_path)
                        attachment_name = await self._upload_file(file_path, filename)
                        if attachment_name:
                            attachment_names.append(attachment_name)

                # 清理所有临时文件
                for fp in downloaded_files:
                    self._cleanup_file(fp)

                if attachment_names:
                    memo_id = await self._post_memo_with_attachments(text_content, attachment_names)
                    if memo_id:
                        yield event.plain_result(
                            f"✅ 成功同步内容和 {len(attachment_names)} 张图片到 Memos！\n"
                            f"📝 Memo ID: {memo_id}"
                        )
                    else:
                        yield event.plain_result("❌ 同步失败，请检查配置或稍后重试。")
                else:
                    yield event.plain_result("❌ 图片上传失败，请稍后重试。")
            else:
                # 纯文字内容
                memo_id = await self._post_memo_text(text_content)
                if memo_id:
                    yield event.plain_result(
                        f"✅ 成功同步文字内容到 Memos！\n"
                        f"📝 Memo ID: {memo_id}"
                    )
                else:
                    yield event.plain_result("❌ 同步失败，请检查配置或稍后重试。")

        except Exception as e:
            logger.error(f"[Memos] 同步过程中发生错误: {e}")
            yield event.plain_result("❌ 同步过程中发生错误，请稍后重试。")

    @filter.command("note_list")
    async def note_list_handler(self, event: AstrMessageEvent):
        """查看最近的 Memos 笔记。用法：/note_list [数量]"""

        # 权限校验
        if not self._is_authorized(event):
            yield event.plain_result("❌ 你没有权限使用此功能。")
            return

        if not self.memos_url or not self.memos_access_token:
            yield event.plain_result("❌ Memos 插件未配置，请在管理面板中设置 Memos 地址和访问令牌。")
            return

        # 解析数量参数，默认5条
        raw_text = event.message_str.strip()
        # 去除指令名前缀
        if raw_text.startswith("note_list"):
            count_str = raw_text[9:].strip()
        else:
            count_str = raw_text
        try:
            count = int(count_str) if count_str else 5
            count = max(1, min(count, 20))  # 限制 1~20
        except ValueError:
            count = 5

        url = f"{self.memos_url}/api/v1/memos"
        params = {
            "pageSize": count,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._get_headers(), params=params)
                response.raise_for_status()
                result = response.json()

            memos = result.get("memos", [])
            if not memos:
                yield event.plain_result("📭 暂无 Memos 笔记。")
                return

            lines = [f"📋 最近 {len(memos)} 条 Memos 笔记：\n"]
            for i, memo in enumerate(memos, 1):
                content = memo.get("content", "（无内容）")
                # 截取前80个字符
                if len(content) > 80:
                    content = content[:80] + "..."
                memo_name = memo.get("name", "")
                memo_id = memo_name.split("/")[-1] if memo_name else "?"
                create_time = memo.get("createTime", "未知时间")
                # 只取日期部分
                if "T" in create_time:
                    create_time = create_time.split("T")[0]
                lines.append(f"{i}. [{create_time}] (ID:{memo_id})\n{content}\n")

            yield event.plain_result("\n".join(lines))

        except Exception as e:
            logger.error(f"[Memos] 获取笔记列表失败: {e}")
            yield event.plain_result("❌ 获取笔记列表失败，请稍后重试。")

    @filter.command("note_delete")
    async def note_delete_handler(self, event: AstrMessageEvent):
        """删除指定的 Memos 笔记。用法：/note_delete <Memo ID>"""

        # 权限校验
        if not self._is_authorized(event):
            yield event.plain_result("❌ 你没有权限使用此功能。")
            return

        if not self.memos_url or not self.memos_access_token:
            yield event.plain_result("❌ Memos 插件未配置，请在管理面板中设置 Memos 地址和访问令牌。")
            return

        # 去除指令名前缀获取 memo_id
        raw_text = event.message_str.strip()
        if raw_text.startswith("note_delete"):
            memo_id = raw_text[11:].strip()
        else:
            memo_id = raw_text
        if not memo_id:
            yield event.plain_result("❌ 请提供要删除的 Memo ID，例如：/note_delete 123")
            return

        url = f"{self.memos_url}/api/v1/memos/{memo_id}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(url, headers=self._get_headers())
                response.raise_for_status()

            yield event.plain_result(f"✅ 成功删除 Memo（ID: {memo_id}）")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                yield event.plain_result(f"❌ 未找到 ID 为 {memo_id} 的 Memo。")
            else:
                logger.error(f"[Memos] 删除笔记失败: {e}")
                yield event.plain_result("❌ 删除失败，请稍后重试。")
        except Exception as e:
            logger.error(f"[Memos] 删除笔记失败: {e}")
            yield event.plain_result("❌ 删除失败，请稍后重试。")

    @filter.command("note_tag")
    async def note_tag_handler(self, event: AstrMessageEvent):
        """按标签搜索笔记，以合并转发消息展示。用法：/note_tag <标签名>"""

        # 权限校验
        if not self._is_authorized(event):
            yield event.plain_result("❌ 你没有权限使用此功能。")
            return

        if not self.memos_url or not self.memos_access_token:
            yield event.plain_result("❌ Memos 插件未配置，请在管理面板中设置 Memos 地址和访问令牌。")
            return

        # 解析标签参数
        raw_text = event.message_str.strip()
        if raw_text.startswith("note_tag"):
            tag = raw_text[8:].strip()
        else:
            tag = raw_text
        # 去掉 # 前缀（用户可能输入 #标签）
        tag = tag.lstrip("#").strip()

        if not tag:
            yield event.plain_result("❌ 请提供要搜索的标签，例如：/note_tag 日记\n💡 也可以使用 /note_tag #日记")
            return

        yield event.plain_result(f"🔍 正在搜索标签 #{tag} 下的笔记...")

        memos = await self._search_memos_by_tag(tag)

        if not memos:
            yield event.plain_result(f"📭 没有找到包含标签 #{tag} 的笔记。")
            return

        # 使用合并转发消息发送完整内容
        if self.bot_uin:
            nodes = []
            # 添加一个头部说明 Node
            uin = int(self.bot_uin) if self.bot_uin.isdigit() else 0
            header_node = Comp.Node(
                uin=uin,
                name=self.bot_name,
                content=[Comp.Plain(f"🏷️ 标签 #{tag} 下共 {len(memos)} 条笔记")],
            )
            nodes.append(header_node)

            for i, memo in enumerate(memos):
                nodes.append(self._build_memo_node(memo, i))

            yield event.chain_result(nodes)
        else:
            # 无 bot_uin 降级：逐条发送完整笔记内容
            yield event.plain_result(f"🏷️ 标签 #{tag} 下共 {len(memos)} 条笔记：")
            for i, memo in enumerate(memos, 1):
                content = memo.get("content", "（无内容）")
                memo_name = memo.get("name", "")
                memo_id = memo_name.split("/")[-1] if memo_name else "?"
                create_time = memo.get("createTime", "未知时间")
                if "T" in create_time:
                    create_time = create_time.split("T")[0]
                pinned = "📌 " if memo.get("pinned") else ""
                visibility = memo.get("visibility", "PRIVATE")
                vis_icon = {"PUBLIC": "🌐", "PROTECTED": "🔓", "PRIVATE": "🔒"}.get(visibility, "")
                text = (
                    f"━━ {i}/{len(memos)} ━━\n"
                    f"{pinned}{vis_icon} [{create_time}] ID:{memo_id}\n\n"
                    f"{content}"
                )
                yield event.plain_result(text)

    @filter.command("note_search")
    async def note_search_handler(self, event: AstrMessageEvent):
        """按关键词搜索笔记内容，以合并转发消息展示。用法：/note_search <关键词>"""

        # 权限校验
        if not self._is_authorized(event):
            yield event.plain_result("❌ 你没有权限使用此功能。")
            return

        if not self.memos_url or not self.memos_access_token:
            yield event.plain_result("❌ Memos 插件未配置，请在管理面板中设置 Memos 地址和访问令牌。")
            return

        # 解析关键词参数
        raw_text = event.message_str.strip()
        if raw_text.startswith("note_search"):
            keyword = raw_text[11:].strip()
        else:
            keyword = raw_text

        if not keyword:
            yield event.plain_result("❌ 请提供搜索关键词，例如：/note_search 学习笔记")
            return

        yield event.plain_result(f"🔍 正在搜索包含「{keyword}」的笔记...")

        memos = await self._search_memos_by_content(keyword)

        if not memos:
            yield event.plain_result(f"📭 没有找到包含「{keyword}」的笔记。")
            return

        # 使用合并转发消息发送完整内容
        if self.bot_uin:
            nodes = []
            uin = int(self.bot_uin) if self.bot_uin.isdigit() else 0
            header_node = Comp.Node(
                uin=uin,
                name=self.bot_name,
                content=[Comp.Plain(f"🔎 搜索「{keyword}」共找到 {len(memos)} 条笔记")],
            )
            nodes.append(header_node)

            for i, memo in enumerate(memos):
                nodes.append(self._build_memo_node(memo, i))

            yield event.chain_result(nodes)
        else:
            # 无 bot_uin 降级：逐条发送完整笔记内容
            yield event.plain_result(f"🔎 搜索「{keyword}」共找到 {len(memos)} 条笔记：")
            for i, memo in enumerate(memos, 1):
                content = memo.get("content", "（无内容）")
                memo_name = memo.get("name", "")
                memo_id = memo_name.split("/")[-1] if memo_name else "?"
                create_time = memo.get("createTime", "未知时间")
                if "T" in create_time:
                    create_time = create_time.split("T")[0]
                pinned = "📌 " if memo.get("pinned") else ""
                visibility = memo.get("visibility", "PRIVATE")
                vis_icon = {"PUBLIC": "🌐", "PROTECTED": "🔓", "PRIVATE": "🔒"}.get(visibility, "")
                text = (
                    f"━━ {i}/{len(memos)} ━━\n"
                    f"{pinned}{vis_icon} [{create_time}] ID:{memo_id}\n\n"
                    f"{content}"
                )
                yield event.plain_result(text)

    @filter.command("note_pin")
    async def note_pin_handler(self, event: AstrMessageEvent):
        """置顶或取消置顶笔记。用法：/note_pin <Memo ID>"""

        # 权限校验
        if not self._is_authorized(event):
            yield event.plain_result("❌ 你没有权限使用此功能。")
            return

        if not self.memos_url or not self.memos_access_token:
            yield event.plain_result("❌ Memos 插件未配置，请在管理面板中设置 Memos 地址和访问令牌。")
            return

        # 解析 memo_id
        raw_text = event.message_str.strip()
        if raw_text.startswith("note_pin"):
            memo_id = raw_text[8:].strip()
        else:
            memo_id = raw_text

        if not memo_id:
            yield event.plain_result("❌ 请提供 Memo ID，例如：/note_pin 123")
            return

        # 先获取当前 memo 的置顶状态
        url = f"{self.memos_url}/api/v1/memos/{memo_id}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                memo = response.json()

            current_pinned = memo.get("pinned", False)
            new_pinned = not current_pinned

            success = await self._update_memo(memo_id, {"pinned": new_pinned}, ["pinned"])
            if success:
                action = "📌 已置顶" if new_pinned else "📌 已取消置顶"
                yield event.plain_result(f"{action} Memo（ID: {memo_id}）")
            else:
                yield event.plain_result("❌ 操作失败，请稍后重试。")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                yield event.plain_result(f"❌ 未找到 ID 为 {memo_id} 的 Memo。")
            else:
                logger.error(f"[Memos] 置顶操作失败: {e}")
                yield event.plain_result("❌ 操作失败，请稍后重试。")
        except Exception as e:
            logger.error(f"[Memos] 置顶操作失败: {e}")
            yield event.plain_result("❌ 操作失败，请稍后重试。")

    @filter.command("note_stats")
    async def note_stats_handler(self, event: AstrMessageEvent):
        """查看 Memos 统计数据。用法：/note_stats"""

        # 权限校验
        if not self._is_authorized(event):
            yield event.plain_result("❌ 你没有权限使用此功能。")
            return

        if not self.memos_url or not self.memos_access_token:
            yield event.plain_result("❌ Memos 插件未配置，请在管理面板中设置 Memos 地址和访问令牌。")
            return

        yield event.plain_result("📊 正在获取统计数据...")

        stats = await self._get_user_stats()
        if not stats:
            yield event.plain_result("❌ 获取统计数据失败，请稍后重试。")
            return

        # 构建统计信息
        total_count = stats.get("totalMemoCount", 0)
        tag_count: dict = stats.get("tagCount", {})
        memo_type_stats: dict = stats.get("memoTypeStats", {})
        pinned_memos: list = stats.get("pinnedMemos", [])

        lines = ["📊 Memos 统计数据\n"]
        lines.append(f"📝 笔记总数：{total_count}")
        lines.append(f"📌 置顶笔记：{len(pinned_memos)} 条")

        # 内容类型统计
        link_count = memo_type_stats.get("linkCount", 0)
        code_count = memo_type_stats.get("codeCount", 0)
        todo_count = memo_type_stats.get("incompleteTodoCount", 0)
        if link_count or code_count or todo_count:
            lines.append(f"\n📈 内容类型：")
            if link_count:
                lines.append(f"  🔗 含链接：{link_count} 条")
            if code_count:
                lines.append(f"  💻 含代码：{code_count} 条")
            if todo_count:
                lines.append(f"  ☑️ 待办事项：{todo_count} 条未完成")

        # 标签统计（按数量排序，最多显示15个）
        if tag_count:
            sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)[:15]
            lines.append(f"\n🏷️ 标签统计（Top {len(sorted_tags)}）：")
            for tag_name, count in sorted_tags:
                lines.append(f"  #{tag_name}  ×{count}")

        yield event.plain_result("\n".join(lines))

    @filter.command("note_random")
    async def note_random_handler(self, event: AstrMessageEvent):
        """随机回顾一条历史笔记。用法：/note_random"""

        # 权限校验
        if not self._is_authorized(event):
            yield event.plain_result("❌ 你没有权限使用此功能。")
            return

        if not self.memos_url or not self.memos_access_token:
            yield event.plain_result("❌ Memos 插件未配置，请在管理面板中设置 Memos 地址和访问令牌。")
            return

        memo = await self._get_random_memo()
        if not memo:
            yield event.plain_result("📭 暂无笔记可供回顾。")
            return

        content = memo.get("content", "（无内容）")
        memo_name = memo.get("name", "")
        memo_id = memo_name.split("/")[-1] if memo_name else "?"
        create_time = memo.get("createTime", "未知时间")
        if "T" in create_time:
            create_time = create_time.split("T")[0]
        pinned = "📌 " if memo.get("pinned") else ""
        visibility = memo.get("visibility", "PRIVATE")
        vis_icon = {"PUBLIC": "🌐", "PROTECTED": "🔓", "PRIVATE": "🔒"}.get(visibility, "")

        text = (
            f"🎲 随机回顾\n"
            f"━━━━━━━━━━━━\n"
            f"{pinned}{vis_icon} [{create_time}] ID:{memo_id}\n\n"
            f"{content}"
        )

        yield event.plain_result(text)

    async def terminate(self):
        """插件销毁时清理资源目录"""
        if os.path.exists(self.resource_dir):
            try:
                for f in os.listdir(self.resource_dir):
                    fp = os.path.join(self.resource_dir, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                os.rmdir(self.resource_dir)
                logger.info("[Memos] 已清理资源目录")
            except Exception as e:
                logger.error(f"[Memos] 清理资源目录失败: {e}")
