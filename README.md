# 🎰 VietlottBot

> Discord bot hỗ trợ mua vé xổ số Vietlott — tự động gợi ý bộ số, tạo SMS mua vé, và báo kết quả hàng ngày.

---

## ✨ Tính năng

- 🔢 **Gợi ý bộ số** cho Lotto 5/35, Mega 6/45, Power 6/55
- 📱 **Tạo SMS mua vé** gửi thẳng đến 9969 — bấm 1 nút là xong
- 🎯 **Hỗ trợ bao số** — BC4, BC6, BC7, BC8, BD2→BD12, B5→B10
- ⏰ **Tự báo kết quả** đúng giờ xổ mỗi ngày
- 📊 **Phân tích lịch sử** từ hàng nghìn kỳ xổ
- 💰 **Kiểm soát chi tiêu** tự động theo giới hạn ngày

---

## 🎮 Các lệnh

| Lệnh | Mô tả |
|------|-------|
| `/535 [số bộ]` | Gợi ý bộ số Lotto 5/35 |
| `/645 [số bộ]` | Gợi ý bộ số Mega 6/45 |
| `/655 [số bộ]` | Gợi ý bộ số Power 6/55 |
| `/bao535` | Bao số Lotto 5/35 |
| `/bao645` | Bao số Mega 6/45 |
| `/bao655` | Bao số Power 6/55 |

---

## 🛠️ Công nghệ

- **Python** + discord.py
- **Railway** — deploy 24/7
- **Google Sheets** — lưu lịch sử kết quả

---

## ⚙️ Cài đặt

### Yêu cầu
- Python 3.10+
- Discord Bot Token
- Google Service Account

### Biến môi trường
Tạo các biến sau trong Railway (hoặc file `.env` khi chạy local):

```
DISCORD_TOKEN=...
DISCORD_CHANNEL_ID=...
GOOGLE_CREDENTIALS_B64=...
GOOGLE_SHEET_ID=...
```

### Deploy lên Railway
1. Fork repo này
2. Tạo project mới trên [railway.app](https://railway.app)
3. Connect GitHub repo
4. Thêm các biến môi trường
5. Deploy!

---

## 📋 Requirements

```
discord.py
requests
beautifulsoup4
gspread
google-auth
pytz
```

---

## ⚠️ Lưu ý

- Bot chỉ gợi ý số dựa trên thống kê lịch sử — **không đảm bảo trúng thưởng**
- Hãy chơi có trách nhiệm, trong giới hạn tài chính của bạn
- SMS mua vé miễn phí 100% khi gửi đến **9969**

---

## 📄 License

MIT License — free to use, modify and distribute.
