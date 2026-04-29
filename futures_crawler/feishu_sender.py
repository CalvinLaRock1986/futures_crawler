from __future__ import annotations

import json
import mimetypes
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request


FEISHU_BASE = "https://open.feishu.cn"


def send_file_to_chat(*, app_id: str, app_secret: str, chat_id: str, file_path: str) -> None:
    token = _get_tenant_access_token(app_id=app_id, app_secret=app_secret)
    file_key = _upload_file(token=token, file_path=file_path)
    _send_file_message(token=token, chat_id=chat_id, file_key=file_key)


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> dict:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Feishu API HTTPError {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Feishu API URLError: {e}") from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Feishu API returned non-JSON: {raw[:300]}") from e


def _get_tenant_access_token(*, app_id: str, app_secret: str) -> str:
    url = f"{FEISHU_BASE}/open-apis/auth/v3/tenant_access_token/internal"
    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode("utf-8")
    data = _request_json(
        method="POST",
        url=url,
        headers={"Content-Type": "application/json; charset=utf-8"},
        body=payload,
    )
    if data.get("code") != 0:
        raise RuntimeError(f"Get tenant_access_token failed: {data}")
    token = data.get("tenant_access_token")
    if not token:
        raise RuntimeError(f"Missing tenant_access_token: {data}")
    return token


def _upload_file(*, token: str, file_path: str) -> str:
    url = f"{FEISHU_BASE}/open-apis/im/v1/files"
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        file_data = f.read()
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body, boundary = _encode_multipart_formdata(
        fields={"file_type": "stream", "file_name": filename},
        files={"file": (filename, file_data, content_type)},
    )
    data = _request_json(
        method="POST",
        url=url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        body=body,
    )
    if data.get("code") != 0:
        raise RuntimeError(f"Upload file failed: {data}")
    file_key = ((data.get("data") or {}).get("file_key")) if isinstance(data.get("data"), dict) else None
    if not file_key:
        raise RuntimeError(f"Missing file_key in upload response: {data}")
    return file_key


def _send_file_message(*, token: str, chat_id: str, file_key: str) -> None:
    query = urllib.parse.urlencode({"receive_id_type": "chat_id"})
    url = f"{FEISHU_BASE}/open-apis/im/v1/messages?{query}"
    content = json.dumps({"file_key": file_key}, ensure_ascii=False)
    payload = json.dumps(
        {"receive_id": chat_id, "msg_type": "file", "content": content},
        ensure_ascii=False,
    ).encode("utf-8")
    data = _request_json(
        method="POST",
        url=url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        body=payload,
    )
    if data.get("code") != 0:
        raise RuntimeError(f"Send file message failed: {data}")


def _encode_multipart_formdata(
    *,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----futures-crawler-{uuid.uuid4().hex}"
    lines: list[bytes] = []

    for name, value in fields.items():
        lines.extend(
            [
                f"--{boundary}".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"'.encode("utf-8"),
                b"",
                value.encode("utf-8"),
            ]
        )

    for name, (filename, data, content_type) in files.items():
        lines.extend(
            [
                f"--{boundary}".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
                ).encode("utf-8"),
                f"Content-Type: {content_type}".encode("utf-8"),
                b"",
                data,
            ]
        )

    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")
    body = b"\r\n".join(lines)
    return body, boundary

