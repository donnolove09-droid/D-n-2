# Lumo — Web Chat dùng Gemini API

Web chatbot đơn giản, giao diện tối kiểu ChatGPT/Claude, backend Flask
(`server.py`) gọi Gemini API. Dán link vào khung chat, bot sẽ tự tải nội dung
trang đó và trả lời/tóm tắt dựa trên nội dung thật.

## Cấu trúc dự án

```
geminichat/
├── server.py           # Backend Flask, gọi Gemini API
├── static/index.html   # Giao diện chat (1 file HTML/CSS/JS)
├── requirements.txt
├── Procfile             # Lệnh chạy cho Railway/Render
└── .env.example
```

## 1. Chạy thử ở máy local

```bash
cd geminichat
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Mở .env, dán GEMINI_API_KEY của bạn vào

export $(cat .env | xargs)      # Windows: dùng "set" hoặc set biến môi trường trong PowerShell
python3 server.py
```

Mở trình duyệt tại `http://localhost:5000`.

Lấy API key Gemini miễn phí tại: **https://aistudio.google.com/app/apikey**

## 2. Deploy lên Railway

1. Đẩy thư mục `geminichat/` này lên một repo GitHub.
2. Vào **railway.app** → **New Project** → **Deploy from GitHub repo**.
3. Railway tự nhận diện `Procfile` và `requirements.txt`.
4. Vào tab **Variables**, thêm:
   - `GEMINI_API_KEY` = API key của bạn
   - (tuỳ chọn) `GEMINI_MODEL` = `gemini-2.0-flash`
5. Railway sẽ tự build & deploy. Sau khi xong, mở domain mà Railway cấp
   (mục **Settings → Networking → Generate Domain**).

## 3. Deploy lên Render

1. Đẩy code lên GitHub như trên.
2. Vào **render.com** → **New** → **Web Service** → chọn repo.
3. Cấu hình:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app --bind 0.0.0.0:$PORT`
4. Trong **Environment**, thêm biến `GEMINI_API_KEY`.
5. Nhấn **Create Web Service**. Render tự build và cấp domain dạng
   `https://ten-app.onrender.com`.

## 4. Deploy lên Vercel (lưu ý)

Vercel chạy Python dưới dạng **serverless functions**, không phù hợp tốt với
một server Flask chạy liên tục như thế này (mỗi request là một hàm riêng,
không giữ được kết nối lâu). Khuyến nghị dùng **Railway** hoặc **Render** —
cả hai đều chạy Flask app như một server thật, đơn giản và ổn định hơn cho
trường hợp này. Nếu vẫn muốn dùng Vercel, cần bọc `server.py` thành một
serverless function riêng (`api/chat.py`) theo chuẩn của Vercel Python
Runtime — nhắn mình nếu bạn muốn mình chuyển đổi sang dạng đó.

## Ghi chú kỹ thuật

- Frontend gửi toàn bộ lịch sử hội thoại (`history`) mỗi lần hỏi, để Gemini
  trả lời có ngữ cảnh — bạn có thể thêm lưu trữ (database) nếu muốn giữ
  lịch sử qua nhiều phiên.
- Khi tin nhắn chứa link, server tải tối đa 3 link, mỗi link giới hạn ~8000
  ký tự nội dung để tránh vượt giới hạn token.
- Đổi `GEMINI_MODEL` trong biến môi trường nếu Google cập nhật tên model mới.
- Không commit file `.env` thật (chứa API key) lên GitHub — chỉ commit
  `.env.example`.
