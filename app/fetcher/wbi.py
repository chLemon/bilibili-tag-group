"""B 站 WBI 签名工具：为 API 请求参数添加 w_rid 和 wts 签名。"""
from __future__ import annotations

import hashlib
import time
import urllib.parse
from functools import lru_cache

import httpx

# WBI 混音密钥重排表（B 站前端固定常量，极少变动）
_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

# B 站通用请求头
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def _extract_key_from_url(url: str) -> str:
    """从 wbi_img URL 中提取文件名（不含扩展名）作为密钥片段。

    例如：
    "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png"
    -> "7cd084941338484aae1ad9425b84077c"
    """
    return url.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _derive_mixin_key(img_key: str, sub_key: str) -> str:
    """使用重排表从 img_key 和 sub_key 派生出 32 位混音密钥。"""
    raw = img_key + sub_key
    return "".join(raw[idx] for idx in _MIXIN_KEY_ENC_TAB[:32])


@lru_cache(maxsize=1)
def _get_cached_mixin_key() -> str:
    """获取并缓存混音密钥（从 B 站 nav 接口获取）。

    密钥极少变动，使用 lru_cache 避免每次签名都请求 nav 接口。
    缓存大小设为 1，有新密钥时可通过 _invalidate_mixin_key_cache() 清除。
    """
    response = httpx.get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers=BASE_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    wbi_img = data["data"]["wbi_img"]
    img_key = _extract_key_from_url(wbi_img["img_url"])
    sub_key = _extract_key_from_url(wbi_img["sub_url"])
    return _derive_mixin_key(img_key, sub_key)


def _invalidate_mixin_key_cache() -> None:
    """清除混音密钥缓存，强制下次签名时重新获取。"""
    _get_cached_mixin_key.cache_clear()


def sign_params(params: dict[str, str | int]) -> dict[str, str]:
    """为请求参数添加 WBI 签名（w_rid 和 wts）。

    参数：
        params: 原始请求参数字典（不含 w_rid 和 wts）

    返回：
        添加了 w_rid 和 wts 的新字典
    """
    wts = int(time.time())
    params["wts"] = wts

    # 按 key 字母序排序，构建 query string（值需 URL 编码）
    sorted_items = sorted(params.items(), key=lambda item: item[0])
    query_string = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}"
        for k, v in sorted_items
    )

    mixin_key = _get_cached_mixin_key()
    w_rid = hashlib.md5((query_string + mixin_key).encode()).hexdigest()

    # 构建返回字典，所有值转字符串
    result: dict[str, str] = {}
    for k, v in params.items():
        result[k] = str(v)
    result["w_rid"] = w_rid
    return result
