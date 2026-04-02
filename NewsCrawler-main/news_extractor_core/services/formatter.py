# -*- coding: utf-8 -*-
"""
格式化服务 - 将 NewsItem 转换为 Markdown
"""
from typing import Dict, Optional

from ..models import NewsItem
from .image_service import ImageService, ImageResult


def to_markdown(
    news_item: NewsItem,
    embed_images: bool = False,
    save_images_locally: bool = False,
    images_dir: str = "",
    platform: str = "default",
    image_results: Optional[Dict[str, ImageResult]] = None,
    local_image_paths: Optional[Dict[str, Optional[str]]] = None,
) -> str:
    """
    将 NewsItem 转换为 Markdown 格式

    Args:
        news_item: 新闻数据
        embed_images: 是否将图片嵌入为 Base64
        save_images_locally: 是否将图片保存到本地
        images_dir: 图片保存目录（save_images_locally=True 时必须提供）
        platform: 平台名称（用于选择图片下载策略）
        image_results: 预先下载的图片结果（用于 embed_images）
        local_image_paths: 预先下载的本地路径映射（用于 save_images_locally）

    Returns:
        Markdown 格式的字符串
    """
    # 优先处理本地保存模式
    if save_images_locally and local_image_paths is None:
        image_urls = news_item.images
        if image_urls and images_dir:
            service = ImageService(platform=platform)
            local_image_paths = service.download_to_local(image_urls, images_dir)

    # 其次处理 base64 嵌入模式
    if embed_images and not save_images_locally and image_results is None:
        image_urls = news_item.images
        if image_urls:
            service = ImageService(platform=platform)
            image_results = service.download_images(image_urls)

    md_lines = []

    # 标题
    md_lines.append(f"# {news_item.title}\n")

    # 元信息
    meta = news_item.meta_info
    md_lines.append("## 文章信息\n")
    if meta.get("author_name"):
        md_lines.append(f"**作者**: {meta['author_name']}  ")
    if meta.get("publish_time"):
        md_lines.append(f"**发布时间**: {meta['publish_time']}  ")
    md_lines.append(f"**原文链接**: [{news_item.news_url}]({news_item.news_url})\n")
    md_lines.append("---\n")

    # 正文内容
    md_lines.append("## 正文内容\n")
    for content in news_item.contents:
        content_type = content.get("type", "text")
        content_text = content.get("content", "")

        if content_type == "text":
            md_lines.append(f"{content_text}\n")
        elif content_type == "image":
            # 优先使用本地路径
            if save_images_locally and local_image_paths:
                local_path = local_image_paths.get(content_text)
                if local_path:
                    md_lines.append(f"![图片]({local_path})\n")
                else:
                    md_lines.append(f"![图片]({content_text})\n")
                    md_lines.append("<!-- 图片下载失败 -->\n")
            # 其次使用 base64 嵌入
            elif embed_images and image_results:
                result = image_results.get(content_text)
                if result and result.success:
                    data_url = result.to_data_url()
                    md_lines.append(f"![图片]({data_url})\n")
                else:
                    md_lines.append(f"![图片]({content_text})\n")
                    if result and result.error:
                        md_lines.append(f"<!-- 图片加载失败: {result.error} -->\n")
            else:
                md_lines.append(f"![图片]({content_text})\n")
        elif content_type == "video":
            md_lines.append(f"[视频]({content_text})\n")

    # 媒体资源统计（仅在不处理图片时显示 URL 列表）
    if not save_images_locally and not embed_images and (news_item.images or news_item.videos):
        md_lines.append("\n---\n")
        md_lines.append("## 媒体资源\n")

        if news_item.images:
            md_lines.append(f"\n### 图片 ({len(news_item.images)})\n")
            for idx, img_url in enumerate(news_item.images, 1):
                md_lines.append(f"{idx}. {img_url}\n")

        if news_item.videos:
            md_lines.append(f"\n### 视频 ({len(news_item.videos)})\n")
            for idx, video_url in enumerate(news_item.videos, 1):
                md_lines.append(f"{idx}. {video_url}\n")

    return "\n".join(md_lines)
