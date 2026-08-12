#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HuluXia Comment/Topic Bot - Python Web Version
Flask web application replicating the Java Spring Boot version.
All API calls, signing, and logic are identical to the original.
"""

import hashlib
import io
import json
import os
import random
import string
import tempfile
import threading
import time
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, render_template, request

app = Flask(__name__)

# ═══════════════════════════════════════════
# Constants (mirrors Java constants)
# ═══════════════════════════════════════════
SECRET_KEY = "fa1c28a5b62e79c3e63d9030b6142e4b"
IMAGE_SECRET = "my_sign@huluxia.com"
FIXED_DEVICE_CODE = "[d]664f4abb-156e-4d55-9ecd-26ac39f3fea4"
FIXED_HLX_ANDROID_ID = "bbf53771-89a4-4a48-82d8-5281927c920d"
COUPLE_MID_FILE = Path("couplemid.jpg")

# ═══════════════════════════════════════════
# Global State (mirrors BotService fields)
# ═══════════════════════════════════════════
STATE = {
    "current_session": None,   # dict with _key, user info etc.
    "running": False,
    "cancelled": False,
}

# Config
CONFIG = {
    "base_url": "http://floor.huluxia.com",
    "upload_url": "http://upload.huluxia.com",
    "app_version": "4.4.1.6",
    "versioncode": "440106",
    "market_id": "tool_xiaomi",
    "platform": "2",
    "gkey": "000000",
    "phone_brand_type": "MI",
    "login_path": "/account/login",
    "login_api_version": "4.1.8",
    "comment_path": "/comment/create",
    "comment_api_version": "4.1.8",
    "topic_path": "/post/create",
    "topic_api_version": "4.2.6",
    "mixed_topic_api_version": "4.1.8",
    "upload_path": "/upload/v3/image",
}

# ═══════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════

def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def sign(params: dict, tags: list) -> str:
    """PHP ToSign($args, $tags, false) - lowercase MD5"""
    raw = ""
    for tag in tags:
        v = params.get(tag, "")
        raw += tag + (v if v else "")
    raw += SECRET_KEY
    return md5(raw)

def sign_upper(params: dict, tags: list) -> str:
    """PHP ToSign($args, $tags, true) - uppercase MD5"""
    return sign(params, tags).upper()

def sign_image(params: dict, tags: list) -> str:
    """PHP ToSign_image - key=value&...secret=... MD5 uppercase"""
    raw = ""
    for tag in tags:
        v = params.get(tag, "")
        raw += f"{tag}={v}&"
    raw += f"secret={IMAGE_SECRET}"
    return md5(raw).upper()

def random_nonce(length: int = 32) -> str:
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(length))

def random_ip() -> str:
    return f"{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"

def is_image_file(name: str) -> bool:
    lo = name.lower()
    return lo.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))

def load_images(directory: str) -> list:
    """Load image files sorted by modification time."""
    d = Path(directory)
    if not d.is_dir():
        return []
    files = sorted(
        [f for f in d.iterdir() if f.is_file() and is_image_file(f.name)],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    return files

def truncate(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[:max_len] + "..."

def compress_image_if_needed(filepath: Path, max_size_mb: int = 12) -> Path:
    """If image file is larger than max_size_mb MB, compress and return temp path.
    Otherwise return the original path unchanged."""
    max_size = max_size_mb * 1024 * 1024
    original_size = filepath.stat().st_size

    if original_size <= max_size:
        return filepath  # No compression needed

    print(f"[COMPRESS] {filepath.name}: {original_size // 1024}KB > {max_size_mb}MB, compressing...")

    from PIL import Image
    img = Image.open(filepath)
    img_format = (img.format or "JPEG").upper()
    orig_w, orig_h = img.width, img.height

    # Determine save format & convert RGBA/P to RGB when targeting JPEG
    if img_format in ("JPEG", "JPG"):
        save_format = "JPEG"
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
    elif img_format == "PNG":
        # PNG quality param has little effect — convert to JPEG for large files
        save_format = "JPEG"
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
    elif img_format == "WEBP":
        save_format = "WEBP"
    else:
        save_format = "JPEG"
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

    current_img = img
    quality = 95

    # Phase 1: reduce quality until under target
    for q in range(95, 4, -5):
        buf = io.BytesIO()
        current_img.save(buf, format=save_format, quality=q, optimize=True)
        if buf.tell() <= max_size:
            quality = q
            break
    else:
        quality = 5

    # Phase 2: if still too large, also reduce dimensions
    buf = io.BytesIO()
    current_img.save(buf, format=save_format, quality=quality, optimize=True)
    if buf.tell() > max_size:
        for scale in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]:
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))
            resized = img.resize((new_w, new_h), Image.LANCZOS)
            buf2 = io.BytesIO()
            resized.save(buf2, format=save_format, quality=quality, optimize=True)
            if buf2.tell() <= max_size:
                current_img = resized
                print(f"[COMPRESS] Also resized: {orig_w}x{orig_h} -> {new_w}x{new_h}")
                break

    # Save to temp file
    suffix = filepath.suffix if save_format == (img.format or "JPEG").upper() else ".jpg"
    fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix="hlx_compressed_")
    os.close(fd)
    current_img.save(temp_path, format=save_format, quality=quality, optimize=True)

    final_size = os.path.getsize(temp_path)
    print(f"[COMPRESS] Done: {original_size // 1024}KB -> {final_size // 1024}KB "
          f"({final_size * 100 // original_size}%)")
    return Path(temp_path)

def escape_xml(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def join_fids(fids: list) -> str:
    if not fids:
        return ""
    clean = [f.strip() for f in fids if f and f.strip()]
    return ",".join(clean) + "," if clean else ""

def first_non_empty(*values) -> str:
    for v in values:
        if v and str(v).strip():
            return str(v).strip()
    return ""


# ═══════════════════════════════════════════
# HTTP Client (mirrors HttpClient.java)
# ═══════════════════════════════════════════

class HttpClient:
    def __init__(self, base_url=None, upload_url=None):
        self.base_url = base_url or CONFIG["base_url"]
        self.upload_url = upload_url or CONFIG["upload_url"]

    def _build_url(self, base: str, path: str, api_version: str) -> str:
        path = path.lstrip("/")
        if api_version and api_version not in ("none", ""):
            return f"{base}/{path}/ANDROID/{api_version}"
        return f"{base}/{path}"

    def _headers(self) -> dict:
        return {
            "User-Agent": "okhttp/3.8.1",
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
        }

    def get_api(self, path: str, api_version: str, params: dict, cls=None):
        """GET request. cls ignored (Python uses dict)."""
        return self._get_api(self.base_url, path, api_version, params)

    def get_api_ex(self, base: str, path: str, api_version: str, params: dict):
        """GET request with explicit base URL."""
        return self._get_api(base, path, api_version, params)

    def _get_api(self, base: str, path: str, api_version: str, params: dict):
        url = self._build_url(base, path, api_version)
        resp = requests.get(url, params=params, headers=self._headers(), timeout=60)
        print(f"[HTTP] GET {resp.url}")
        if resp.status_code != 200:
            print(f"[HTTP] ERROR {resp.status_code}: {truncate(resp.text, 300)}")
            raise IOError(f"HTTP {resp.status_code}: {truncate(resp.text, 200)}")
        body = resp.text
        print(f"[HTTP] -> {resp.status_code} body: {truncate(body, 200)}")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def post_api(self, path: str, api_version: str, params: dict, cls=None):
        """POST form body."""
        return self._post_api(self.base_url, path, api_version, params)

    def post_api_ex(self, base: str, path: str, api_version: str, params: dict):
        return self._post_api(base, path, api_version, params)

    def _post_api(self, base: str, path: str, api_version: str, params: dict):
        url = self._build_url(base, path, api_version)
        resp = requests.post(url, data=params, headers=self._headers(), timeout=60)
        print(f"[HTTP] POST {resp.url}")
        if resp.status_code != 200:
            print(f"[HTTP] ERROR {resp.status_code}: {truncate(resp.text, 300)}")
            raise IOError(f"HTTP {resp.status_code}: {truncate(resp.text, 200)}")
        body = resp.text
        print(f"[HTTP] -> {resp.status_code} body: {truncate(body, 200)}")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def post_api_with_query(self, path: str, api_version: str,
                             query_params: dict, body_params: dict, cls=None):
        """POST with query params in URL + form body."""
        url = self._build_url(self.base_url, path, api_version)
        resp = requests.post(url, params=query_params, data=body_params,
                             headers=self._headers(), timeout=60)
        print(f"[HTTP] POST(Q) {resp.url}")
        if resp.status_code != 200:
            print(f"[HTTP] ERROR {resp.status_code}: {truncate(resp.text, 300)}")
            raise IOError(f"HTTP {resp.status_code}: {truncate(resp.text, 200)}")
        body = resp.text
        print(f"[HTTP] -> {resp.status_code} body: {truncate(body, 200)}")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def upload_api(self, upload_path: str, query_params: dict,
                    filepath, cls=None) -> dict:
        """Upload file as multipart."""
        url = self._build_url(self.upload_url, upload_path, "")
        with open(filepath, "rb") as f:
            files = {
                "file": (Path(filepath).name, f, "image/jpg"),
            }
            data = {"_key": "key_10"}
            headers = {
                **self._headers(),
                "X-FORWARDED-FOR": random_ip(),
                "CLIENT-IP": random_ip(),
            }
            resp = requests.post(url, params=query_params, data=data,
                                  files=files, headers=headers, timeout=120)
        print(f"[HTTP] UPLOAD {resp.url}")
        if resp.status_code != 200:
            print(f"[HTTP] ERROR {resp.status_code}: {truncate(resp.text, 300)}")
            raise IOError(f"HTTP {resp.status_code}: {truncate(resp.text, 200)}")
        body = resp.text
        print(f"[HTTP] -> {resp.status_code} body: {truncate(body, 200)}")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}


# ═══════════════════════════════════════════
# Auth Manager (mirrors AuthManager.java)
# ═══════════════════════════════════════════

class AuthManager:
    def __init__(self, http_client: HttpClient, login_base_url: str,
                 login_path: str, login_api_version: str):
        self.http = http_client
        self.login_base_url = login_base_url
        self.login_path = login_path
        self.login_api_version = login_api_version
        self.device_code = FIXED_DEVICE_CODE
        self.session = None

    def login(self, account: str, raw_password: str) -> dict:
        print(f"[AUTH] Logging in as: {account}")
        hashed_password = md5(raw_password)

        params = {
            "device_code": self.device_code,
            "voice_code": "",
            "account": account,
            "login_type": "2",
            "password": hashed_password,
            "phone_brand_type": CONFIG["phone_brand_type"],
            "hlx_android_id": FIXED_HLX_ANDROID_ID,
        }
        s = sign(params, ["account", "device_code", "password", "voice_code"])
        params["sign"] = s

        self.session = self.http.get_api_ex(
            self.login_base_url, self.login_path,
            self.login_api_version, params
        )

        if self.session and self._is_success(self.session):
            user = self.session.get("user", {})
            print(f"[AUTH] Login success! userId={user.get('userID')}, nick={user.get('nick')}")
            print(f"[AUTH] token={self.session.get('_key')}")
        else:
            print(f"[AUTH] Login failed: {self.session}")

        return self.session

    def get_token(self) -> str:
        return self.session.get("_key", "") if self.session else ""

    def _is_success(self, resp: dict) -> bool:
        if resp.get("status") == 1:
            return True
        return not resp.get("msg")


# ═══════════════════════════════════════════
# Upload Manager (mirrors UploadManager.java)
# ═══════════════════════════════════════════

SIGN_TAGS_UPLOAD = [
    "_key", "app_version", "device_code", "gkey", "market_id",
    "nonce_str", "platform", "timestamp", "use_type", "versioncode"
]

class UploadManager:
    def __init__(self, http_client: HttpClient, auth: AuthManager, upload_path: str):
        self.http = http_client
        self.auth = auth
        self.upload_path = upload_path

    def upload_image(self, img_file) -> dict:
        fp = Path(img_file)
        if not fp.exists():
            raise IOError(f"File not found: {fp}")

        print(f"[UPLOAD] {fp.name} ({fp.stat().st_size // 1024}KB)")

        query = {
            "_key": self.auth.get_token(),
            "app_version": CONFIG["app_version"],
            "device_code": self.auth.device_code,
            "gkey": CONFIG["gkey"],
            "market_id": CONFIG["market_id"],
            "nonce_str": random_nonce(32),
            "platform": CONFIG["platform"],
            "timestamp": str(int(time.time() * 1000)),
            "use_type": "2",
            "versioncode": CONFIG["versioncode"],
        }
        query["sign"] = sign_image(query, SIGN_TAGS_UPLOAD)

        result = self.http.upload_api(self.upload_path, query, str(fp))

        if result and self._is_success(result):
            print(f"[UPLOAD] OK fid={result.get('fid')}")
        else:
            print(f"[UPLOAD] Failed: {result}")

        return result

    def _is_success(self, resp: dict) -> bool:
        if resp.get("status") == 1:
            return True
        return not resp.get("msg")


# ═══════════════════════════════════════════
# Comment Manager (mirrors CommentManager.java)
# ═══════════════════════════════════════════

SIGN_TAGS_COMMENT = ["_key", "comment_id", "device_code", "images", "post_id", "text"]

class CommentManager:
    def __init__(self, http_client: HttpClient, auth: AuthManager,
                 comment_path: str, comment_api_version: str):
        self.http = http_client
        self.auth = auth
        self.comment_path = comment_path
        self.comment_api_version = comment_api_version

    def post_comment(self, post_id: int, text: str, fids: list,
                      parent_cid: int = 0, patcha: str = "",
                      remind_users: str = "") -> dict:
        params = {
            "platform": CONFIG["platform"],
            "gkey": CONFIG["gkey"],
            "app_version": CONFIG["app_version"],
            "versioncode": CONFIG["versioncode"],
            "market_id": CONFIG["market_id"],
            "phone_brand_type": CONFIG["phone_brand_type"],
            "device_code": self.auth.device_code,
            "hlx_android_id": FIXED_HLX_ANDROID_ID,
            "_key": self.auth.get_token(),
            "comment_id": str(parent_cid),
            "post_id": str(post_id),
            "text": text,
            "patcha": patcha or "",
            "images": ",".join(fids) if fids else "",
            "remindUsers": remind_users or "",
        }
        params["sign"] = sign(params, SIGN_TAGS_COMMENT)

        print(f"[COMMENT] postId={post_id} fids={len(fids)} text={truncate(text, 40)}")

        resp = self.http.get_api(self.comment_path, self.comment_api_version, params)

        if resp:
            if self._is_success(resp):
                print("[COMMENT] OK")
            else:
                print(f"[COMMENT] Failed: code={resp.get('code')} msg={resp.get('msg')}")

        return resp

    def _is_success(self, resp: dict) -> bool:
        if resp.get("status") == 1:
            return True
        return not resp.get("msg")


# ═══════════════════════════════════════════
# Topic Manager (mirrors TopicManager.java)
# ═══════════════════════════════════════════

SIGN_TAGS_TOPIC = ["_key", "detail", "device_code", "images", "title", "voice"]

SIGN_TAGS_TOPIC_NORMAL = ["_key", "cat_id", "detail", "device_code",
                           "images", "tag_id", "title", "voice"]
TOPIC_SECRET = "cPqzc91RXPJlNiWSPrDpzJjo2YuiImtx"


class TopicManager:
    def __init__(self, http_client: HttpClient, auth: AuthManager,
                 topic_path: str, topic_api_version: str):
        self.http = http_client
        self.auth = auth
        self.topic_path = topic_path
        self.topic_api_version = topic_api_version

    def create_topic(self, cat_id: int, tag_id: int, title: str,
                      detail: str, fids: list) -> dict:
        """Normal topic: detail with <text>, images in images param."""
        text_detail = f"<text>{detail}</text>"
        params = self._build_params(cat_id, tag_id, title, text_detail, ",".join(fids) if fids else "")
        params["sign"] = sign_upper(params, SIGN_TAGS_TOPIC)
        print(f"[DETAIL] {text_detail}")
        print(f"[IMAGES] {','.join(fids) if fids else ''}")
        return self._do_request(cat_id, tag_id, title, fids, params)

    def create_mixed_topic(self, cat_id: int, tag_id: int, title: str,
                            detail: str, fids: list, dimensions: list) -> dict:
        """Mixed topic: detail includes <text> and <image> tags, images empty."""
        mixed_detail = self._build_mixed_detail(detail, fids, dimensions)
        params = self._build_params(cat_id, tag_id, title, mixed_detail, "")
        print(f"[DETAIL] {mixed_detail}")
        params["sign"] = sign_upper(params, SIGN_TAGS_TOPIC)
        return self._do_request(cat_id, tag_id, title, fids, params)

    def _build_params(self, cat_id: int, tag_id: int, title: str,
                       detail: str, images: str) -> dict:
        return {
            "platform": CONFIG["platform"],
            "gkey": CONFIG["gkey"],
            "app_version": CONFIG["app_version"],
            "versioncode": CONFIG["versioncode"],
            "market_id": CONFIG["market_id"],
            "_key": self.auth.get_token(),
            "device_code": self.auth.device_code,
            "phone_brand_type": CONFIG["phone_brand_type"],
            "draft_id": "0",
            "cat_id": str(cat_id),
            "tag_id": str(tag_id),
            "type": "0",
            "title": title,
            "detail": detail,
            "patcha": "",
            "voice": "",
            "lng": "0.0",
            "lat": "0.0",
            "images": images,
            "user_ids": "",
            "recommendTopics": "",
            "remindTopics": "",
            "hlx_imei": "",
            "hlx_android_id": FIXED_HLX_ANDROID_ID,
            "hlx_oaid": "",
            "is_app_link": "",
        }

    def _do_request(self, cat_id: int, tag_id: int, title: str,
                     fids: list, params: dict) -> dict:
        print(f"[POST_BODY] {params}")
        resp = self.http.post_api(self.topic_path, self.topic_api_version, params)
        ok = self._is_success(resp) if resp else False
        print(f"[TOPIC] catId={cat_id} tagId={tag_id} "
              f"title={truncate(title, 40)} fids={len(fids or [])} "
              f"-> {'OK' if ok else 'FAIL'}")
        return resp

    @staticmethod
    def _build_mixed_detail(text: str, fids: list, dimensions: list) -> str:
        parts = [f"<text>{text}</text>"]
        if fids:
            for i, fid in enumerate(fids):
                dim = dimensions[i] if i < len(dimensions) else [0, 0]
                parts.append(f"<image>{fid},{dim[0]},{dim[1]}</image>")
        parts.append("<text></text>")
        return "".join(parts)

    def _is_success(self, resp: dict) -> bool:
        if resp.get("status") == 1:
            return True
        return not resp.get("msg")


# ═══════════════════════════════════════════
# Check-in Manager (mirrors CheckInManager.java)
# ═══════════════════════════════════════════

class CheckInManager:
    def __init__(self, http_client: HttpClient, token: str, device_code: str):
        self.http = http_client
        self.token = token
        self.device_code = device_code

    def check_in_all(self) -> int:
        category_ids = self._fetch_category_ids()
        if not category_ids:
            return 0
        success = 0
        for cat_id in category_ids:
            try:
                resp = self._check_in(cat_id)
                if resp and self._is_success(resp):
                    success += 1
                    print(f"[签到] 板块 {cat_id} 签到成功")
                elif resp:
                    print(f"[签到] 板块 {cat_id} 签到失败: {resp.get('msg', 'unknown')}")
            except Exception as e:
                # 403等错误会被捕获，继续下一个板块
                print(f"[签到] 板块 {cat_id} 异常: {e}")
                continue
        return success

    def _fetch_category_ids(self) -> list:
        params = self._base_params()
        params["is_hidden"] = "0"
        resp = self.http.get_api("/category/list", "2.0", params)
        ids = []
        for cat in resp.get("categories", []):
            cid = cat.get("categoryID")
            if cid and int(cid) > 0:
                ids.append(int(cid))
        return ids

    def _check_in(self, category_id: int) -> dict:
        t = int(time.time() * 1000)
        s = sign({"cat_id": str(category_id), "time": str(t)},
                  ["cat_id", "time"])
        query = self._base_params()
        query["cat_id"] = str(category_id)
        query["time"] = str(t)
        body = {"sign": s}
        return self.http.post_api_with_query(
            "/user/signin", "4.1.8", query, body)

    def _base_params(self) -> dict:
        return {
            "platform": CONFIG["platform"],
            "gkey": CONFIG["gkey"],
            "app_version": CONFIG["app_version"],
            "versioncode": CONFIG["versioncode"],
            "market_id": CONFIG["market_id"],
            "_key": self.token,
            "device_code": self.device_code or "",
            "phone_brand_type": CONFIG["phone_brand_type"],
        }

    def _is_success(self, resp: dict) -> bool:
        if resp.get("status") == 1:
            return True
        return not resp.get("msg")


# ═══════════════════════════════════════════
# Bot Service (mirrors BotService.java)
# ═══════════════════════════════════════════

class BotService:
    def __init__(self):
        self.http = HttpClient()
        self.auth = AuthManager(self.http, "https://floor.huluxia.com",
                                 CONFIG["login_path"], CONFIG["login_api_version"])
        self.upload = UploadManager(self.http, self.auth, CONFIG["upload_path"])
        self.comment = CommentManager(self.http, self.auth,
                                       CONFIG["comment_path"],
                                       CONFIG["comment_api_version"])
        self.topic = TopicManager(self.http, self.auth,
                                   CONFIG["topic_path"],
                                   CONFIG["mixed_topic_api_version"])

    def get_session(self):
        return STATE["current_session"]

    def login(self, account: str, password: str) -> dict:
        session = self.auth.login(account, password)
        if session and self._is_success(session):
            STATE["current_session"] = session
        return session

    def cancel(self):
        STATE["cancelled"] = True

    def update_config(self, cfg: dict):
        if "app_version" in cfg:
            CONFIG["app_version"] = cfg["app_version"]
        if "versioncode" in cfg:
            CONFIG["versioncode"] = cfg["versioncode"]
        if "topic_api_version" in cfg:
            CONFIG["topic_api_version"] = cfg["topic_api_version"]
        if "mixed_topic_api_version" in cfg:
            CONFIG["mixed_topic_api_version"] = cfg["mixed_topic_api_version"]
        # Re-init topic manager with updated versions
        self.topic = TopicManager(self.http, self.auth,
                                   CONFIG["topic_path"],
                                   CONFIG["mixed_topic_api_version"])

    def check_in_all(self):
        token = STATE["current_session"].get("_key", "") if STATE["current_session"] else ""
        cim = CheckInManager(self.http, token, FIXED_DEVICE_CODE)
        return cim.check_in_all()

    def post_topics(self, signatures: list, post_count: int, topic_mode: int,
                     images_per_post: int, image_files: list,
                     cat_id: int, tag_id: int, title_prefix: str,
                     upload_delay_ms: int, topic_delay_ms: int,
                     log_callback) -> tuple:
        """Returns (success_count, total_count)"""
        STATE["cancelled"] = False

        # Re-init auth to ensure fresh state, then restore login session
        self.auth = AuthManager(self.http, "https://floor.huluxia.com",
                                 CONFIG["login_path"], "4.1.8")
        # Restore token from login session so upload/comment APIs have _key
        if STATE.get("current_session"):
            self.auth.session = STATE["current_session"]
        self.topic = TopicManager(self.http, self.auth,
                                   CONFIG["topic_path"],
                                   CONFIG["mixed_topic_api_version"])
        self.upload = UploadManager(self.http, self.auth, CONFIG["upload_path"])

        if images_per_post == 0:
            source_imgs_per_post = 0
        elif topic_mode == 2:
            source_imgs_per_post = 2
        else:
            source_imgs_per_post = images_per_post

        needed = post_count * source_imgs_per_post
        if needed > 0 and len(image_files) < needed:
            log_callback(f"图片不足，需要{needed}张，只有{len(image_files)}张")
            return 0, post_count

        if len(signatures) < post_count * 2:
            log_callback(f"签名不足，需要{post_count * 2}条，只有{len(signatures)}条")
            return 0, post_count

        success, img_idx = 0, 0
        for i in range(post_count):
            if STATE["cancelled"]:
                break
            num = i + 1

            # Gather images for this post
            group = []
            if images_per_post > 0:
                if topic_mode == 2:
                    group.append(image_files[img_idx]); img_idx += 1
                    group.append(COUPLE_MID_FILE)
                    group.append(image_files[img_idx]); img_idx += 1
                else:
                    for _ in range(images_per_post):
                        group.append(image_files[img_idx]); img_idx += 1

            # Upload images
            fids = []
            dimensions = []
            if images_per_post > 0:
                for j, img_file in enumerate(group):
                    if STATE["cancelled"]:
                        break
                    sz = img_file.stat().st_size // 1024 if img_file.exists() else 0
                    log_callback(
                        f"上传 {num}/{post_count} ({j+1}/{len(group)}): "
                        f"{img_file.name} ({sz}KB)")
                    try:
                        if topic_mode == 1:
                            try:
                                from PIL import Image
                                img = Image.open(img_file)
                                dimensions.append([img.width, img.height])
                            except Exception:
                                dimensions.append([0, 0])
                        compressed = compress_image_if_needed(img_file)
                        info = self.upload.upload_image(compressed)
                        if info and info.get("fid"):
                            fids.append(info["fid"])
                        # Clean up temp compressed file
                        if compressed != img_file:
                            try:
                                compressed.unlink()
                            except Exception:
                                pass
                    except Exception as e:
                        log_callback(f"上传失败: {e}")
                    if j < len(group) - 1:
                        time.sleep(upload_delay_ms / 1000.0)

            title_text = signatures[i * 2]
            detail_text = signatures[i * 2 + 1]
            title = title_prefix + title_text

            log_callback(f"发帖 {num}/{post_count}: {truncate(title, 50)}")
            try:
                if topic_mode == 1 and fids:
                    r = self.topic.create_mixed_topic(
                        cat_id, tag_id, title, detail_text, fids, dimensions)
                else:
                    r = self._create_normal_topic(
                        cat_id, tag_id, title, detail_text, fids)
                if r and self._is_success(r):
                    success += 1
                elif r:
                    log_callback(f"失败: code={r.get('code')} {r.get('msg')}")
            except Exception as e:
                log_callback(f"异常: {e}")

            if i < post_count - 1:
                time.sleep(topic_delay_ms / 1000.0)

        return success, post_count

    def post_comments(self, post_id: int, texts: list, image_files: list,
                       images_per_comment: int, couple_mode: bool,
                       comment_delay_ms: int, upload_delay_ms: int,
                       log_callback) -> tuple:
        """Returns (success_count, total_count)"""
        STATE["cancelled"] = False

        # Re-init auth, then restore login session token
        self.auth = AuthManager(self.http, "https://floor.huluxia.com",
                                 CONFIG["login_path"], "4.1.8")
        if STATE.get("current_session"):
            self.auth.session = STATE["current_session"]
        self.comment = CommentManager(self.http, self.auth,
                                       CONFIG["comment_path"],
                                       CONFIG["comment_api_version"])
        self.upload = UploadManager(self.http, self.auth, CONFIG["upload_path"])

        if couple_mode:
            img_count = min(len(image_files) // 2, len(texts))
        else:
            if images_per_comment == 0:
                images_per_comment = 1
            img_count = min(len(image_files) // images_per_comment, len(texts))

        txt_count = max(0, len(texts) - img_count)
        total = img_count + txt_count
        success, img_idx = 0, 0

        log_callback(f"=== 共 {total} 条评论 ===")

        # Phase 1: image + text
        for i in range(img_count):
            if STATE["cancelled"]:
                break
            num = i + 1
            group = []
            fids = []

            if couple_mode:
                group.append(image_files[img_idx]); img_idx += 1
                group.append(COUPLE_MID_FILE)
                group.append(image_files[img_idx]); img_idx += 1
            else:
                for _ in range(images_per_comment):
                    group.append(image_files[img_idx]); img_idx += 1

            for j, img_file in enumerate(group):
                log_callback(
                    f"上传 {num}/{total} ({j+1}/{len(group)}): {img_file.name}")
                try:
                    compressed = compress_image_if_needed(img_file)
                    info = self.upload.upload_image(compressed)
                    if info and info.get("fid"):
                        fids.append(info["fid"])
                    # Clean up temp compressed file
                    if compressed != img_file:
                        try:
                            compressed.unlink()
                        except Exception:
                            pass
                except Exception as e:
                    log_callback(f"上传失败: {e}")
                if j < len(group) - 1:
                    time.sleep(upload_delay_ms / 1000.0)

            log_callback(f"评论 {num}/{total}: {truncate(texts[i], 40)}")
            try:
                r = self.comment.post_comment(post_id, texts[i], fids)
                if r and self._is_success(r):
                    success += 1
                elif r:
                    log_callback(f"失败: code={r.get('code')} {r.get('msg')}")
            except Exception as e:
                log_callback(f"异常: {e}")
            if i < img_count - 1:
                time.sleep(comment_delay_ms / 1000.0)

        # Phase 2: text only
        for i in range(img_count, img_count + txt_count):
            if STATE["cancelled"]:
                break
            num = i + 1
            log_callback(f"评论 {num}/{total}: {truncate(texts[i], 40)}")
            try:
                r = self.comment.post_comment(post_id, texts[i], [])
                if r and self._is_success(r):
                    success += 1
                elif r:
                    log_callback(f"失败: code={r.get('code')} {r.get('msg')}")
            except Exception as e:
                log_callback(f"异常: {e}")
            if i < img_count + txt_count - 1:
                time.sleep(comment_delay_ms / 1000.0)

        return success, total

    def _create_normal_topic(self, cat_id: int, tag_id: int, title: str,
                              detail: str, fids: list) -> dict:
        """Create topic with signing matching PHP/BotService.createNormalTopic"""
        session = STATE.get("current_session", {}) or {}
        user_key = first_non_empty(
            session.get("_key", ""),
            session.get("key", ""),
            session.get("token", ""),
            self.auth.get_token(),
        )
        device_code = first_non_empty(
            session.get("deviceCode", ""),
            session.get("device_code", ""),
            self.auth.device_code,
            FIXED_DEVICE_CODE,
        )

        if not user_key:
            raise IOError("无法读取_key")
        if not device_code:
            raise IOError("无法读取device_code")

        text_detail = f"<text>{escape_xml(detail)}</text>"
        images = join_fids(fids)

        query = {
            "platform": CONFIG["platform"],
            "gkey": CONFIG["gkey"],
            "app_version": CONFIG["app_version"],
            "versioncode": CONFIG["versioncode"],
            "market_id": CONFIG["market_id"],
            "_key": user_key,
            "device_code": device_code,
            "phone_brand_type": CONFIG["phone_brand_type"],
        }

        body = {
            "draft_id": "0",
            "cat_id": str(cat_id),
            "tag_id": str(tag_id),
            "type": "0",
            "title": title or "",
            "detail": text_detail,
            "patcha": "",
            "voice": "",
            "lng": "0.0",
            "lat": "0.0",
            "images": images,
            "user_ids": "",
            "recommendTopics": "",
            "remindTopics": "",
            "hlx_sign_imei": "",
            "hlx_sign_android_id": FIXED_HLX_ANDROID_ID,
            "hlx_sign_oaid": "",
            "hlx_model": "PCLM10",
            "hlx_brand": "OPPO",
            "is_app_link": "3",
        }

        # Sign: combine query + body, use topic_normal tags
        sign_params = {**query, **body}
        body["sign"] = self._sign_topic_normal(sign_params)

        return self.http.post_api_with_query(
            CONFIG["topic_path"], CONFIG["topic_api_version"],
            query, body)

    @staticmethod
    def _sign_topic_normal(params: dict) -> str:
        """Mirrors signTopicNormal"""
        tags = ["_key", "cat_id", "detail", "device_code",
                "images", "tag_id", "title", "voice"]
        raw = ""
        for tag in tags:
            raw += tag + (params.get(tag, "") or "")
        raw += TOPIC_SECRET
        return md5(raw).upper()

    @staticmethod
    def _is_success(resp: dict) -> bool:
        if resp.get("status") == 1:
            return True
        return not resp.get("msg")


# ═══════════════════════════════════════════
# Flask Routes (mirrors HlxApiController + PageController)
# ═══════════════════════════════════════════

bot = BotService()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/back/<path:filename>")
def serve_back(filename):
    from flask import send_from_directory
    return send_from_directory("static/back", filename)


# ─── Login ───

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    account = (data.get("account") or "").strip()
    password = (data.get("password") or "").strip()

    if not account or not password:
        return jsonify({"success": False, "msg": "请输入账号和密码"}), 400

    try:
        session = bot.login(account, password)
        if session and session.get("status") == 1:
            # 保存session到STATE，供签到等功能使用
            STATE["current_session"] = session
            user = session.get("user", {})
            return jsonify({
                "success": True,
                "msg": "登录成功",
                "nick": user.get("nick", ""),
                "uid": user.get("userID", ""),
                "token": session.get("_key", ""),
            })
        return jsonify({
            "success": False,
            "msg": (session or {}).get("msg", "网络错误"),
        })
    except Exception as e:
        return jsonify({"success": False, "msg": f"异常: {e}"})


# ─── Check-in ───

@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    try:
        count = bot.check_in_all()
        return jsonify({"success": True, "msg": f"签到成功 {count} 个板块", "count": count})
    except Exception as e:
        return jsonify({"success": False, "msg": f"签到失败: {e}"})


# ─── Status ───

@app.route("/api/status")
def api_status():
    session = STATE.get("current_session")
    return jsonify({
        "running": STATE["running"],
        "loggedIn": bool(session and session.get("status") == 1),
    })


# ─── Cancel ───

@app.route("/api/cancel", methods=["POST"])
def api_cancel():
    bot.cancel()
    STATE["running"] = False
    return jsonify({"success": True, "msg": "已取消"})


# ─── Post Topics (SSE) ───

@app.route("/api/post/topics", methods=["POST"])
def api_post_topics():
    """SSE endpoint for posting topics."""
    if STATE["running"]:
        return Response(
            "event: error\ndata: {\"msg\":\"已有任务在运行\"}\n\n",
            mimetype="text/event-stream"
        )

    STATE["running"] = True
    data = request.get_json(force=True, silent=True) or {}

    # Parse params
    signatures = _parse_string_list(data, "signatures")
    post_count = _parse_int(data, "postCount", 1)
    topic_mode = _parse_int(data, "topicMode", 0)
    images_per_post = _parse_int(data, "imagesPerPost", 3)
    image_dir = _parse_str(data, "imageDir", "images")
    cat_id = _parse_int(data, "catId", 57)
    tag_id = _parse_int(data, "tagId", 0)
    title_prefix = _parse_str(data, "titlePrefix", "")
    upload_delay = _parse_int(data, "uploadDelayMs", 2000)
    topic_delay = _parse_int(data, "topicDelayMs", 60000)

    # ── Thread + Queue for SSE ──
    import queue
    log_queue = queue.Queue()

    def run_thread():
        try:
            image_files = load_images(image_dir)
            if images_per_post > 0 and not image_files:
                log_queue.put(("error", {"msg": f"图片目录为空: {image_dir}"}))
                return

            log_queue.put(("log", {"msg": f"图片: {len(image_files)} 张, 签名: {len(signatures)} 条"}))
            mode_name = {2: "情头", 1: "图文混编", 0: "普通"}.get(topic_mode, "普通")
            log_queue.put(("log", {"msg": f"发帖数: {post_count}, 模式: {mode_name}"}))

            cfg = {}
            if data.get("app_version"):
                cfg["app_version"] = _parse_str(data, "app_version", "4.4.1.6")
            if data.get("versioncode"):
                cfg["versioncode"] = _parse_str(data, "versioncode", "440106")
            if data.get("topic_api_version"):
                cfg["topic_api_version"] = _parse_str(data, "topic_api_version", "4.2.6")
            if data.get("mixed_topic_api_version"):
                cfg["mixed_topic_api_version"] = _parse_str(data, "mixed_topic_api_version", "4.1.8")
            bot.update_config(cfg)

            def log_cb(msg):
                log_queue.put(("log", {"msg": msg}))

            success, total = bot.post_topics(
                signatures, post_count, topic_mode,
                images_per_post, image_files,
                cat_id, tag_id, title_prefix,
                upload_delay, topic_delay,
                log_cb
            )
            log_queue.put(("complete", {
                "success": success, "total": total,
                "msg": f"完成: {success}/{total}"
            }))
        except Exception as e:
            log_queue.put(("error", {"msg": f"异常: {e}"}))
        finally:
            STATE["running"] = False
            log_queue.put(("__done__", {}))

    threading.Thread(target=run_thread, daemon=True).start()

    def sse_generator():
        while True:
            try:
                event, data = log_queue.get(timeout=0.5)
                if event == "__done__":
                    break
                yield _sse(event, data)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue

    return Response(sse_generator(), mimetype="text/event-stream")


# ─── Post Comments (SSE) ───

@app.route("/api/post/comments", methods=["POST"])
def api_post_comments():
    """SSE endpoint for posting comments."""
    if STATE["running"]:
        return Response(
            "event: error\ndata: {\"msg\":\"已有任务在运行\"}\n\n",
            mimetype="text/event-stream"
        )

    STATE["running"] = True
    data = request.get_json(force=True, silent=True) or {}

    post_id = _parse_int(data, "postId", 0)
    if post_id == 0:
        STATE["running"] = False
        return Response(
            "event: error\ndata: {\"msg\":\"请输入帖子ID\"}\n\n",
            mimetype="text/event-stream"
        )

    texts = _parse_string_list(data, "texts") or _parse_string_list(data, "signatures")
    image_dir = _parse_str(data, "imageDir", "images")
    images_per_comment = _parse_int(data, "imagesPerComment", 1)
    couple_mode = _parse_bool(data, "coupleMode", False)
    comment_delay = _parse_int(data, "commentDelayMs", 10000)
    upload_delay = _parse_int(data, "uploadDelayMs", 2000)

    import queue
    log_queue = queue.Queue()

    def run_thread():
        try:
            image_files = load_images(image_dir)
            log_queue.put(("log", {"msg": f"图片: {len(image_files)} 张, 文本: {len(texts)} 条"}))

            def log_cb(msg):
                log_queue.put(("log", {"msg": msg}))

            success, total = bot.post_comments(
                post_id, texts, image_files,
                images_per_comment, couple_mode,
                comment_delay, upload_delay,
                log_cb
            )
            log_queue.put(("complete", {
                "success": success, "total": total,
                "msg": f"完成: {success}/{total}"
            }))
        except Exception as e:
            log_queue.put(("error", {"msg": f"异常: {e}"}))
        finally:
            STATE["running"] = False
            log_queue.put(("__done__", {}))

    threading.Thread(target=run_thread, daemon=True).start()

    def sse_generator():
        while True:
            try:
                event, data = log_queue.get(timeout=0.5)
                if event == "__done__":
                    break
                yield _sse(event, data)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue

    return Response(sse_generator(), mimetype="text/event-stream")


# ─── Image listing ───

@app.route("/api/images/list")
def api_images_list():
    directory = request.args.get("dir", "images")
    files = load_images(directory)
    result = [{"name": f.name, "size": f.stat().st_size, "path": str(f.absolute())} for f in files]
    return jsonify({"count": len(files), "images": result})


# ─── File browser ───

@app.route("/api/files/browse")
def api_files_browse():
    path_str = request.args.get("path", "")
    entries = []

    if not path_str:
        # Return drive roots (Windows)
        import string as _str
        for letter in _str.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                total = 0
                try:
                    import shutil
                    total = shutil.disk_usage(drive).total
                except Exception:
                    pass
                entries.append({
                    "name": drive,
                    "path": drive,
                    "type": "dir",
                    "size": total,
                })
        return jsonify({"path": "", "parent": "", "entries": entries})

    d = Path(path_str)
    if not d.exists() or not d.is_dir():
        return jsonify({"error": f"目录不存在: {path_str}"}), 400

    parent = str(d.parent) if d.parent != d else ""
    if parent and parent != path_str:
        entries.append({"name": ".. (上级目录)", "path": parent, "type": "parent"})
    elif not parent:
        entries.append({"name": ".. (驱动器列表)", "path": "", "type": "parent"})

    try:
        children = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except PermissionError:
        return jsonify({"error": "无权限访问"}), 403

    img_count = 0
    for child in children:
        if child.name.startswith(".") or child.name.startswith("$"):
            continue
        if child.is_dir():
            entries.append({
                "name": child.name,
                "path": str(child.absolute()),
                "type": "dir",
            })
        elif is_image_file(child.name):
            img_count += 1
            entries.append({
                "name": child.name,
                "path": str(child.absolute()),
                "type": "image",
                "size": child.stat().st_size,
            })

    return jsonify({
        "path": str(d.absolute()),
        "parent": parent,
        "imageCount": img_count,
        "entries": entries,
    })


@app.route("/api/files/scan")
def api_files_scan():
    path_str = request.args.get("path", "")
    d = Path(path_str)
    if not d.exists() or not d.is_dir():
        return jsonify({"count": 0, "valid": False})
    images = load_images(path_str)
    return jsonify({
        "count": len(images),
        "valid": True,
        "path": str(d.absolute()),
    })


# ─── Categories & Tags ───

# Cached categories data (fetched from huluxia on first request)
_CATEGORIES_CACHE = None


@app.route("/api/categories")
def api_categories():
    """Fetch all categories with their tags from huluxia API."""
    global _CATEGORIES_CACHE
    if _CATEGORIES_CACHE is not None:
        return jsonify(_CATEGORIES_CACHE)

    http_client = HttpClient()
    params = {
        "platform": CONFIG["platform"],
        "gkey": CONFIG["gkey"],
        "app_version": CONFIG["app_version"],
        "versioncode": CONFIG["versioncode"],
        "market_id": CONFIG["market_id"],
        "device_code": FIXED_DEVICE_CODE,
        "phone_brand_type": CONFIG["phone_brand_type"],
        "is_hidden": "0",
        "hlx_android_id": FIXED_HLX_ANDROID_ID,
    }

    try:
        resp = http_client._get_api(
            "https://floor.huluxia.com",
            "/category/list", "2.0", params
        )
    except Exception as e:
        print(f"[CATEGORIES] API error: {e}")
        # Try HTTP fallback
        try:
            resp = http_client._get_api(
                "http://floor.huluxia.com",
                "/category/list", "2.0", params
            )
        except Exception as e2:
            return jsonify({"error": f"获取分类失败: {e2}", "categories": []}), 500

    categories = resp.get("categories", [])
    result = []
    for cat in categories:
        cid = cat.get("categoryID", 0)
        if cid <= 0:
            continue
        tags = []
        for t in cat.get("tags", []):
            tid = t.get("ID", 0)
            if tid > 0:
                tags.append({"id": tid, "name": t.get("name", "")})

        result.append({
            "id": cid,
            "title": cat.get("title", ""),
            "description": (cat.get("description") or "")[:50],
            "tags": tags,
        })

    result.sort(key=lambda x: x["id"])
    _CATEGORIES_CACHE = {"categories": result}
    return jsonify(_CATEGORIES_CACHE)


@app.route("/api/categories/refresh")
def api_categories_refresh():
    """Force refresh categories cache."""
    global _CATEGORIES_CACHE
    _CATEGORIES_CACHE = None
    return api_categories()


# ═══════════════════════════════════════════
# SSE Helpers
# ═══════════════════════════════════════════

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ═══════════════════════════════════════════
# Request Parsing Helpers
# ═══════════════════════════════════════════

def _parse_string_list(body: dict, key: str) -> list:
    val = body.get(key)
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [p.strip() for p in val.split(",") if p.strip()]
    return []

def _parse_str(body: dict, key: str, default: str) -> str:
    val = body.get(key)
    return str(val).strip() if val is not None else default

def _parse_int(body: dict, key: str, default: int) -> int:
    try:
        return int(_parse_str(body, key, str(default)))
    except (ValueError, TypeError):
        return default

def _parse_bool(body: dict, key: str, default: bool) -> bool:
    v = _parse_str(body, key, str(default))
    return v.lower() in ("true", "yes", "y", "1")


# ═══════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════

if __name__ == "__main__":
    # Ensure working directory is the app's location
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 50)
    print("  HuluXia Comment/Topic Bot - Python Web")
    print("  Running at http://localhost:5000")
    print("  Working dir:", os.getcwd())
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
