"""
server.py — Backend cho web chat sử dụng Gemini API.

Chức năng:
- Phục vụ giao diện chat (static/index.html)
- Nhận tin nhắn từ người dùng, nếu phát hiện link (URL) trong tin nhắn,
  tự động tải nội dung trang đó về và đưa vào ngữ cảnh cho Gemini trả lời.
- Giữ lịch sử hội thoại (do frontend gửi lên mỗi lần) để trả lời có ngữ cảnh.

Triển khai:
- Railway / Render: dùng Procfile "web: gunicorn server:app"
- Cần biến môi trường GEMINI_API_KEY (bắt buộc)
- Tuỳ chọn: GEMINI_MODEL (mặc định "gemini-2.0-flash")
"""

import os
import re
import requests
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup

app = Flask(__name__, static_folder="static", static_url_path="")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

URL_REGEX = re.compile(r"https?://[^\s<>\"]+")
MAX_PAGE_CHARS = 8000
REQUEST_TIMEOUT = 12

SYSTEM_INSTRUCTION = (
    "Bạn là một trợ lý AI trò chuyện hữu ích, trả lời chính xác, ngắn gọn, "
    "và rõ ràng bằng ngôn ngữ mà người dùng sử dụng. Nếu người dùng dán một "
    "đường link, bạn sẽ được cung cấp thêm nội dung trang web đó trong phần "
    "'NGỮ CẢNH TỪ TRANG WEB' — hãy dùng nó để trả lời câu hỏi hoặc tóm tắt "
    "trang, và nói rõ nếu nội dung không đủ để trả lời. Nếu không chắc chắn "
    "về một sự thật, hãy nói rõ điều đó thay vì bịa đặt."
)


def fetch_url_content(url: str) -> str:
    """Tải và trích xuất văn bản chính từ một URL. Trả về chuỗi rỗng nếu lỗi."""
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GeminiChatBot/1.0)"},
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text" not in content_type:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        text = " ".join(soup.get_text(separator=" ").split())

        combined = f"Tiêu đề: {title}\n\n{text}" if title else text
        return combined[:MAX_PAGE_CHARS]
    except Exception as exc:  # noqa: BLE001
        return f"[Không thể tải nội dung từ {url}: {exc}]"


def build_gemini_contents(history, user_message, url_context):
    """Chuyển lịch sử hội thoại + tin nhắn hiện tại sang định dạng Gemini `contents`."""
    contents = []
    for turn in history:
        role = "model" if turn.get("role") == "assistant" else "user"
        text = turn.get("content", "")
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})

    final_text = user_message
    if url_context:
        final_text = (
            f"{user_message}\n\n"
            f"--- NGỮ CẢNH TỪ TRANG WEB ---\n{url_context}\n--- HẾT NGỮ CẢNH ---"
        )

    contents.append({"role": "user", "parts": [{"text": final_text}]})
    return contents


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    if not GEMINI_API_KEY:
        return jsonify({"error": "Server chưa cấu hình GEMINI_API_KEY."}), 500

    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not user_message:
        return jsonify({"error": "Tin nhắn trống."}), 400

    urls = URL_REGEX.findall(user_message)
    url_context = ""
    if urls:
        chunks = [f"[Link: {u}]\n{fetch_url_content(u)}" for u in urls[:3]]
        url_context = "\n\n".join(chunks)

    contents = build_gemini_contents(history, user_message, url_context)

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        },
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        candidates = result.get("candidates") or []
        if not candidates:
            reason = result.get("promptFeedback", {}).get("blockReason", "unknown")
            return jsonify({"error": f"Gemini không trả về nội dung (lý do: {reason})."}), 502

        parts = candidates[0].get("content", {}).get("parts", [])
        answer = "".join(p.get("text", "") for p in parts).strip()
        if not answer:
            return jsonify({"error": "Gemini trả về phản hồi rỗng."}), 502

        return jsonify({"reply": answer, "used_urls": urls[:3]})

    except requests.exceptions.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            detail = str(exc)
        return jsonify({"error": f"Lỗi gọi Gemini API: {detail}"}), 502
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Lỗi máy chủ: {exc}"}), 500


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "model": GEMINI_MODEL, "configured": bool(GEMINI_API_KEY)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
