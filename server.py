"""
server.py — Backend cho web chat VDON Đẹp Trai.

Chế độ trò chuyện — chọn được ngay trên giao diện:
- Gemini (Google)
- ChatGPT (OpenAI)
- Claude (Anthropic)
- DeepSeek
- Codex (OpenAI, chuyên viết code — dùng Responses API)

Chế độ tạo ảnh (Gemini hoặc ChatGPT):
- POST /api/image  {prompt, provider}

Chức năng chat:
- Phục vụ giao diện chat (static/index.html)
- Nếu tin nhắn chứa link, tự tải nội dung trang đó và đưa vào ngữ cảnh
- Giữ lịch sử hội thoại (frontend gửi lên mỗi lần) để trả lời có ngữ cảnh

Biến môi trường (chỉ cần điền API key của (các) hãng bạn muốn dùng):
  GEMINI_API_KEY,    GEMINI_MODEL       (mặc định: gemini-3.5-flash)
  OPENAI_API_KEY,    OPENAI_MODEL       (mặc định: gpt-5.5)
  ANTHROPIC_API_KEY, ANTHROPIC_MODEL    (mặc định: claude-sonnet-5)
  DEEPSEEK_API_KEY,  DEEPSEEK_MODEL     (mặc định: deepseek-v4-flash)
  CODEX_MODEL                           (mặc định: gpt-5-codex, dùng chung OPENAI_API_KEY)

  GEMINI_IMAGE_MODEL (mặc định: gemini-3.1-flash-image — "Nano Banana 2")
  OPENAI_IMAGE_MODEL (mặc định: gpt-image-2)

Codex và Xcode là hai thứ khác nhau: Codex là model AI viết code, gọi được
qua API. Xcode là phần mềm cài trên máy Mac, KHÔNG có API để server gọi vào
— vì vậy chế độ "Codex" ở đây tối ưu để xuất code Swift/SwiftUI sạch, sẵn
sàng copy-paste thẳng vào Xcode trên máy bạn.
"""

import os
import re
import requests
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup

app = Flask(__name__, static_folder="static", static_url_path="")

BOT_NAME = "VDON Đẹp Trai"

# Ảnh nền & avatar có thể trỏ tới file trong static/ (mặc định) HOẶC một link
# ảnh bất kỳ trên mạng (đặt biến môi trường BG_IMAGE_URL / AVATAR_IMAGE_URL).
# Dùng link ảnh giúp tránh hẳn việc phải upload file lên GitHub.
BG_IMAGE_URL = os.environ.get("BG_IMAGE_URL", "").strip()
AVATAR_IMAGE_URL = os.environ.get("AVATAR_IMAGE_URL", "").strip()

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

PROVIDERS = {
    "gemini": {
        "label": "Gemini",
        "api_key": os.environ.get("GEMINI_API_KEY", ""),
        "model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
    },
    "openai": {
        "label": "ChatGPT",
        "api_key": OPENAI_KEY,
        "model": os.environ.get("OPENAI_MODEL", "gpt-5.5"),
    },
    "anthropic": {
        "label": "Claude",
        "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
    },
    "deepseek": {
        "label": "DeepSeek",
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    },
    "codex": {
        "label": "Codex (viết code)",
        "api_key": OPENAI_KEY,
        "model": os.environ.get("CODEX_MODEL", "gpt-5.3-codex"),
    },
    "grok": {
        "label": "Grok",
        "api_key": os.environ.get("XAI_API_KEY", ""),
        "model": os.environ.get("XAI_MODEL", "grok-4.6"),
    },
}

IMAGE_PROVIDERS = {
    "gemini": {
        "label": "Gemini",
        "api_key": os.environ.get("GEMINI_API_KEY", ""),
        "model": os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image"),
    },
    "openai": {
        "label": "ChatGPT",
        "api_key": OPENAI_KEY,
        "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
    },
}

URL_REGEX = re.compile(r"https?://[^\s<>\"]+")
MAX_PAGE_CHARS = 8000
REQUEST_TIMEOUT = 12

SYSTEM_INSTRUCTION = (
    f"Bạn tên là '{BOT_NAME}', một trợ lý AI trò chuyện hữu ích, trả lời chính "
    "xác, ngắn gọn, rõ ràng, bằng ngôn ngữ mà người dùng sử dụng. Khi viết code, "
    "luôn đặt trong khối ```ngôn_ngữ ... ``` với tên ngôn ngữ chính xác (vd "
    "```html, ```swift, ```python) để giao diện có thể hiển thị đẹp và cho phép "
    "xem trước/sao chép. Nếu người dùng dán một đường link, bạn sẽ được cung cấp "
    "thêm nội dung trang web đó trong phần 'NGỮ CẢNH TỪ TRANG WEB' — hãy dùng nó "
    "để trả lời câu hỏi hoặc tóm tắt trang. Nếu không chắc chắn về một sự thật, "
    "hãy nói rõ điều đó thay vì bịa đặt."
)

CODEX_SYSTEM_INSTRUCTION = (
    f"Bạn tên là '{BOT_NAME}' ở chế độ Codex — chuyên viết code chất lượng cao. "
    "Khi người dùng yêu cầu code cho ứng dụng iOS/macOS, hãy viết Swift/SwiftUI "
    "chuẩn, biên dịch được, đặt trong khối ```swift ... ``` để họ có thể copy "
    "dán thẳng vào Xcode trên máy — không cần giải thích dài dòng trừ khi được "
    "hỏi, ưu tiên code sạch, đúng convention, có comment ngắn gọn khi cần. Với "
    "ngôn ngữ khác, dùng đúng tag ngôn ngữ trong khối code (```python, ```js...). "
    "Trả lời bằng ngôn ngữ người dùng sử dụng."
)


def fetch_url_content(url: str) -> str:
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; VdonBot/1.0)"},
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


def build_final_user_text(user_message: str, url_context: str) -> str:
    if not url_context:
        return user_message
    return (
        f"{user_message}\n\n"
        f"--- NGỮ CẢNH TỪ TRANG WEB ---\n{url_context}\n--- HẾT NGỮ CẢNH ---"
    )


# ---------------------------------------------------------------------------
# Mỗi hàm dưới đây gọi API của một hãng, trả về (text_trả_lời, lỗi_hoặc_None)
# ---------------------------------------------------------------------------

def call_gemini(cfg, history, user_message, url_context):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent"
    contents = []
    for turn in history:
        role = "model" if turn.get("role") == "assistant" else "user"
        text = turn.get("content", "")
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": build_final_user_text(user_message, url_context)}]})

    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "generationConfig": {"maxOutputTokens": 2048},
    }
    resp = requests.post(url, params={"key": cfg["api_key"]}, json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    candidates = result.get("candidates") or []
    if not candidates:
        reason = result.get("promptFeedback", {}).get("blockReason", "unknown")
        return None, f"Gemini không trả về nội dung (lý do: {reason})."
    parts = candidates[0].get("content", {}).get("parts", [])
    answer = "".join(p.get("text", "") for p in parts).strip()
    return answer or None, None if answer else "Gemini trả về phản hồi rỗng."


def call_openai(cfg, history, user_message, url_context):
    url = "https://api.openai.com/v1/chat/completions"
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    for turn in history:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = turn.get("content", "")
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": build_final_user_text(user_message, url_context)})

    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {"model": cfg["model"], "messages": messages, "max_tokens": 2048}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    choices = result.get("choices") or []
    if not choices:
        return None, "ChatGPT không trả về nội dung."
    answer = (choices[0].get("message", {}).get("content") or "").strip()
    return answer or None, None if answer else "ChatGPT trả về phản hồi rỗng."


def call_deepseek(cfg, history, user_message, url_context):
    url = "https://api.deepseek.com/chat/completions"
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    for turn in history:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = turn.get("content", "")
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": build_final_user_text(user_message, url_context)})

    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {"model": cfg["model"], "messages": messages, "max_tokens": 2048}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    choices = result.get("choices") or []
    if not choices:
        return None, "DeepSeek không trả về nội dung."
    answer = (choices[0].get("message", {}).get("content") or "").strip()
    return answer or None, None if answer else "DeepSeek trả về phản hồi rỗng."


def call_anthropic(cfg, history, user_message, url_context):
    url = "https://api.anthropic.com/v1/messages"
    messages = []
    for turn in history:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = turn.get("content", "")
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": build_final_user_text(user_message, url_context)})

    headers = {
        "x-api-key": cfg["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg["model"],
        "system": SYSTEM_INSTRUCTION,
        "messages": messages,
        "max_tokens": 2048,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    blocks = result.get("content") or []
    answer = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    return answer or None, None if answer else "Claude trả về phản hồi rỗng."


def call_codex(cfg, history, user_message, url_context):
    # Codex chỉ dùng được qua Responses API (không dùng chat/completions).
    url = "https://api.openai.com/v1/responses"
    transcript_lines = []
    for turn in history:
        speaker = "Trợ lý" if turn.get("role") == "assistant" else "Người dùng"
        text = turn.get("content", "")
        if text:
            transcript_lines.append(f"{speaker}: {text}")
    transcript = "\n".join(transcript_lines)

    final_user = build_final_user_text(user_message, url_context)
    full_input = CODEX_SYSTEM_INSTRUCTION
    if transcript:
        full_input += f"\n\n--- LỊCH SỬ HỘI THOẠI ---\n{transcript}"
    full_input += f"\n\nNgười dùng: {final_user}"

    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {"model": cfg["model"], "input": full_input}
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    result = resp.json()

    # SDK tiện ích đôi khi có "output_text" thẳng; nếu không, tự duyệt "output"
    answer = (result.get("output_text") or "").strip()
    if not answer:
        chunks = []
        for item in result.get("output", []):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") in ("output_text", "text"):
                        chunks.append(c.get("text", ""))
        answer = "".join(chunks).strip()

    return answer or None, None if answer else "Codex trả về phản hồi rỗng."


def call_grok(cfg, history, user_message, url_context):
    # xAI Grok dùng API tương thích chuẩn OpenAI (chat/completions)
    url = "https://api.x.ai/v1/chat/completions"
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    for turn in history:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = turn.get("content", "")
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": build_final_user_text(user_message, url_context)})

    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {"model": cfg["model"], "messages": messages, "max_tokens": 2048}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    choices = result.get("choices") or []
    if not choices:
        return None, "Grok không trả về nội dung."
    answer = (choices[0].get("message", {}).get("content") or "").strip()
    return answer or None, None if answer else "Grok trả về phản hồi rỗng."


PROVIDER_HANDLERS = {
    "gemini": call_gemini,
    "openai": call_openai,
    "anthropic": call_anthropic,
    "deepseek": call_deepseek,
    "codex": call_codex,
    "grok": call_grok,
}


# ---------------------------------------------------------------------------
# Tạo ảnh
# ---------------------------------------------------------------------------

def generate_image_gemini(cfg, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    resp = requests.post(url, params={"key": cfg["api_key"]}, json=payload, timeout=90)
    resp.raise_for_status()
    result = resp.json()
    candidates = result.get("candidates") or []
    if not candidates:
        return None, None, "Gemini không tạo được ảnh."
    for part in candidates[0].get("content", {}).get("parts", []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            return inline["data"], mime, None
    return None, None, "Gemini không trả về dữ liệu ảnh."


def generate_image_openai(cfg, prompt):
    url = "https://api.openai.com/v1/images/generations"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {"model": cfg["model"], "prompt": prompt, "size": "1024x1024"}
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    result = resp.json()
    data = result.get("data") or []
    if not data or not data[0].get("b64_json"):
        return None, None, "ChatGPT không trả về dữ liệu ảnh."
    return data[0]["b64_json"], "image/png", None


IMAGE_HANDLERS = {
    "gemini": generate_image_gemini,
    "openai": generate_image_openai,
}


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []
    provider_key = (data.get("provider") or "gemini").strip().lower()

    if provider_key not in PROVIDERS:
        return jsonify({"error": f"Nhà cung cấp '{provider_key}' không hợp lệ."}), 400
    if not user_message:
        return jsonify({"error": "Tin nhắn trống."}), 400

    cfg = PROVIDERS[provider_key]
    if not cfg["api_key"]:
        return jsonify({
            "error": f"Server chưa cấu hình API key cho {cfg['label']}. "
                     f"Hãy thêm biến môi trường tương ứng rồi thử lại."
        }), 500

    urls = URL_REGEX.findall(user_message)
    url_context = ""
    if urls:
        chunks = [f"[Link: {u}]\n{fetch_url_content(u)}" for u in urls[:3]]
        url_context = "\n\n".join(chunks)

    handler = PROVIDER_HANDLERS[provider_key]
    try:
        answer, err = handler(cfg, history, user_message, url_context)
        if err or not answer:
            return jsonify({"error": err or "Không có phản hồi."}), 502
        return jsonify({"reply": answer, "used_urls": urls[:3], "provider": provider_key})

    except requests.exceptions.HTTPError as exc:
        detail = ""
        try:
            body = exc.response.json()
            detail = (
                body.get("error", {}).get("message")
                or body.get("message")
                or str(body)
            )
        except Exception:  # noqa: BLE001
            detail = str(exc)
        return jsonify({"error": f"Lỗi gọi {cfg['label']} API: {detail}"}), 502
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Lỗi máy chủ: {exc}"}), 500


@app.route("/api/image", methods=["POST"])
def image():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    provider_key = (data.get("provider") or "gemini").strip().lower()

    if provider_key not in IMAGE_PROVIDERS:
        return jsonify({
            "error": f"'{provider_key}' chưa hỗ trợ tạo ảnh. Hãy chọn Gemini hoặc ChatGPT."
        }), 400
    if not prompt:
        return jsonify({"error": "Mô tả ảnh trống."}), 400

    cfg = IMAGE_PROVIDERS[provider_key]
    if not cfg["api_key"]:
        return jsonify({
            "error": f"Server chưa cấu hình API key cho {cfg['label']}."
        }), 500

    handler = IMAGE_HANDLERS[provider_key]
    try:
        b64_data, mime_type, err = handler(cfg, prompt)
        if err or not b64_data:
            return jsonify({"error": err or "Không tạo được ảnh."}), 502
        return jsonify({"image_base64": b64_data, "mime_type": mime_type, "provider": provider_key})

    except requests.exceptions.HTTPError as exc:
        detail = ""
        try:
            body = exc.response.json()
            detail = body.get("error", {}).get("message") or str(body)
        except Exception:  # noqa: BLE001
            detail = str(exc)
        return jsonify({"error": f"Lỗi tạo ảnh ({cfg['label']}): {detail}"}), 502
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Lỗi máy chủ: {exc}"}), 500


@app.route("/api/health")
def health():
    return jsonify({
        "bot_name": BOT_NAME,
        "bg_image_url": BG_IMAGE_URL,
        "avatar_image_url": AVATAR_IMAGE_URL,
        "providers": {
            key: {"label": cfg["label"], "model": cfg["model"], "configured": bool(cfg["api_key"])}
            for key, cfg in PROVIDERS.items()
        },
        "image_providers": {
            key: {"label": cfg["label"], "model": cfg["model"], "configured": bool(cfg["api_key"])}
            for key, cfg in IMAGE_PROVIDERS.items()
        },
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
