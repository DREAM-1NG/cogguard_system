# -*- coding: utf-8 -*-
"""
鏍煎紡鍖栨湇鍔?- 灏?NewsItem 杞崲涓?Markdown
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
    灏?NewsItem 杞崲涓?Markdown 鏍煎紡

    Args:
        news_item: 鏂伴椈鏁版嵁
        embed_images: 鏄惁灏嗗浘鐗囧祵鍏ヤ负 Base64
        save_images_locally: 鏄惁灏嗗浘鐗囦繚瀛樺埌鏈湴
        images_dir: 鍥剧墖淇濆瓨鐩綍锛坰ave_images_locally=True 鏃跺繀椤绘彁渚涳級
        platform: 骞冲彴鍚嶇О锛堢敤浜庨€夋嫨鍥剧墖涓嬭浇绛栫暐锛?        image_results: 棰勫厛涓嬭浇鐨勫浘鐗囩粨鏋滐紙鐢ㄤ簬 embed_images锛?        local_image_paths: 棰勫厛涓嬭浇鐨勬湰鍦拌矾寰勬槧灏勶紙鐢ㄤ簬 save_images_locally锛?
    Returns:
        Markdown 鏍煎紡鐨勫瓧绗︿覆
    """
    # 浼樺厛澶勭悊鏈湴淇濆瓨妯″紡
    if save_images_locally and local_image_paths is None:
        image_urls = news_item.images
        if image_urls and images_dir:
            service = ImageService(platform=platform)
            local_image_paths = service.download_to_local(image_urls, images_dir)

    # 鍏舵澶勭悊 base64 宓屽叆妯″紡
    if embed_images and not save_images_locally and image_results is None:
        image_urls = news_item.images
        if image_urls:
            service = ImageService(platform=platform)
            image_results = service.download_images(image_urls)

    md_lines = []

    # 鏍囬
    md_lines.append(f"# {news_item.title}\n")

    # 鍏冧俊鎭?    meta = news_item.meta_info
    md_lines.append("## 鏂囩珷淇℃伅\n")
    if meta.get("author_name"):
        md_lines.append(f"**浣滆€?*: {meta['author_name']}  ")
    if meta.get("publish_time"):
        md_lines.append(f"**鍙戝竷鏃堕棿**: {meta['publish_time']}  ")
    md_lines.append(f"**鍘熸枃閾炬帴**: [{news_item.news_url}]({news_item.news_url})\n")
    md_lines.append("---\n")

    # 姝ｆ枃鍐呭
    md_lines.append("## 姝ｆ枃鍐呭\n")
    for content in news_item.contents:
        content_type = content.get("type", "text")
        content_text = content.get("content", "")

        if content_type == "text":
            md_lines.append(f"{content_text}\n")
        elif content_type == "image":
            # 浼樺厛浣跨敤鏈湴璺緞
            if save_images_locally and local_image_paths:
                local_path = local_image_paths.get(content_text)
                if local_path:
                    md_lines.append(f"![鍥剧墖]({local_path})\n")
                else:
                    md_lines.append(f"![鍥剧墖]({content_text})\n")
                    md_lines.append("<!-- 鍥剧墖涓嬭浇澶辫触 -->\n")
            # 鍏舵浣跨敤 base64 宓屽叆
            elif embed_images and image_results:
                result = image_results.get(content_text)
                if result and result.success:
                    data_url = result.to_data_url()
                    md_lines.append(f"![鍥剧墖]({data_url})\n")
                else:
                    md_lines.append(f"![鍥剧墖]({content_text})\n")
                    if result and result.error:
                        md_lines.append(f"<!-- 鍥剧墖鍔犺浇澶辫触: {result.error} -->\n")
            else:
                md_lines.append(f"![鍥剧墖]({content_text})\n")
        elif content_type == "video":
            md_lines.append(f"[瑙嗛]({content_text})\n")

    # 濯掍綋璧勬簮缁熻锛堜粎鍦ㄤ笉澶勭悊鍥剧墖鏃舵樉绀?URL 鍒楄〃锛?    if not save_images_locally and not embed_images and (news_item.images or news_item.videos):
        md_lines.append("\n---\n")
        md_lines.append("## 濯掍綋璧勬簮\n")

        if news_item.images:
            md_lines.append(f"\n### 鍥剧墖 ({len(news_item.images)})\n")
            for idx, img_url in enumerate(news_item.images, 1):
                md_lines.append(f"{idx}. {img_url}\n")

        if news_item.videos:
            md_lines.append(f"\n### 瑙嗛 ({len(news_item.videos)})\n")
            for idx, video_url in enumerate(news_item.videos, 1):
                md_lines.append(f"{idx}. {video_url}\n")

    return "\n".join(md_lines)
