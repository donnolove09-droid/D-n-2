# VDON Đẹp Trai — Web Chat đa mô hình + tạo ảnh + Codex

Web chatbot giao diện tối giản kiểu Grok (nền đen, nút chế độ dạng viên
thuốc). Chọn nhà cung cấp AI ngay trên giao diện, dán link để bot đọc và
tóm tắt, chuyển sang chế độ "Tạo ảnh" để vẽ ảnh AI, và khi bot viết code sẽ
có nút **Xem trước** (với HTML) hoặc **Sao chép** (mọi ngôn ngữ, riêng
Swift ghi rõ "Sao chép cho Xcode").

## Các chế độ trò chuyện
| Chế độ | Hãng | Dùng cho |
|---|---|---|
| Gemini | Google | Chat tổng quát |
| ChatGPT | OpenAI | Chat tổng quát |
| Claude | Anthropic | Chat tổng quát |
| DeepSeek | DeepSeek | Chat tổng quát |
| Codex | OpenAI | Chuyên viết code, tối ưu xuất Swift/SwiftUI sạch để copy vào Xcode |
| Grok | xAI | Chat tổng quát, mạnh về thông tin thời sự/real-time (qua X) |

## Chế độ tạo ảnh
Gemini (Nano Banana 2) hoặc ChatGPT (GPT Image 2) — bấm nút **🎨 Tạo ảnh**
trên giao diện, mô tả ảnh muốn vẽ.

**Lưu ý về Codex & Xcode:** Codex là model AI viết code, gọi được qua API
(đã tích hợp). Xcode là phần mềm cài trên máy Mac, **không có API** để một
web server gọi vào — nên khi bạn hỏi code app iOS, bot sẽ xuất code
Swift/SwiftUI sạch, sẵn nút "Sao chép cho Xcode" để bạn tự dán vào Xcode
trên máy.

## Đổi tên & avatar bot — chỉ cần sửa đúng 2 chỗ

**Đổi tên:** mở `server.py`, sửa dòng đầu file:
```python
BOT_NAME = "VDON Đẹp Trai"
```
Đổi ở đây là đủ — tiêu đề trang, câu chào, nhãn tin nhắn, placeholder ô
nhập... tự động lấy tên mới, không cần sửa gì trong `index.html`.

**Đổi ảnh nền & avatar — 2 cách:**

*Cách 1 (khuyên dùng — không cần upload file):* dán link ảnh trực tiếp vào
Railway → Variables:
```
BG_IMAGE_URL=https://link-anh-nen-cua-ban.jpg
AVATAR_IMAGE_URL=https://link-avatar-cua-ban.png
```
Web tự lấy ảnh từ link đó, không cần đụng vào GitHub. Đây là cách tránh
được lỗi thường gặp "upload nhầm thư mục / sai tên file / quên push ảnh".

*Cách 2 (dùng file trong repo):* nếu không đặt `BG_IMAGE_URL`/
`AVATAR_IMAGE_URL`, web sẽ tự tìm file `static/bg.jpg` (ảnh nền) và
`static/avatar.png`/`.jpg`/`.jpeg`/`.webp` (avatar) — đặt tên đúng và bỏ
vào thư mục `static/`, push lên GitHub. Nếu không có ảnh nào ở cả 2 cách,
giao diện tự dùng chữ cái đầu tên bot làm avatar mặc định — không lỗi gì cả.

## Cấu trúc dự án
```
geminichat/
├── server.py           # Backend Flask — gọi API của các hãng
├── static/index.html   # Giao diện chat
├── requirements.txt
├── Procfile
└── .env.example
```

**⚠️ Quan trọng:** thư mục chứa giao diện phải tên là `static` (chữ thường
toàn bộ) — Linux server phân biệt hoa/thường.

## Chạy thử local
```bash
cd geminichat
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # rồi điền API key
export $(cat .env | grep -v '^#' | xargs)
python3 server.py
```
Mở `http://localhost:5000`.

## Deploy Railway / Render
Đẩy code lên GitHub → tạo service → thêm các biến trong `.env.example` vào
phần **Variables**. Không cần điền đủ mọi hãng, chỉ điền hãng bạn dùng.

## Ghi chú kỹ thuật
- `OPENAI_API_KEY` dùng chung cho cả 3 tính năng của OpenAI: ChatGPT, Codex,
  và tạo ảnh (GPT Image 2) — chỉ cần 1 key.
- Codex gọi qua **Responses API** (`/v1/responses`), khác với ChatGPT dùng
  **Chat Completions** (`/v1/chat/completions`) — đây là 2 endpoint khác
  nhau của OpenAI, code đã xử lý đúng cho từng loại.
- Ảnh tạo ra được trả về dạng base64 trực tiếp trong response, không lưu
  trên server — nếu muốn lưu lịch sử ảnh cần thêm storage riêng.
- Không commit file `.env` thật lên GitHub, chỉ commit `.env.example`.
