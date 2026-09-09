# VietlottBot

**Ngày tạo ghi chú:** 09/09/2026

Discord bot gợi ý bộ số Vietlott, tạo link SMS mua vé, tự động báo kết quả sau giờ xổ.

## Tech stack

- Python 3.11 · `discord.py` (slash commands) · `requests` + `beautifulsoup4` · `gspread` + `google-auth` · `pytz`
- Deploy: Railway/Render/Heroku theo `Procfile` (`worker: python bot.py`)
- Lưu trữ: Google Sheets (không có DB)
- CI: GitHub Actions — `fetch_today.yml` (scrape kết quả), `train_model.yml` (retrain model, Chủ nhật)
- Repo gốc: `github.com/regidgeneral/vietlott-bot` (thư mục local này là bản zip, **không có `.git`**)

## Biến môi trường

| Biến | Dùng cho |
|---|---|
| `DISCORD_TOKEN` | login bot |
| `DISCORD_CHANNEL_ID` | kênh tự động báo kết quả |
| `GOOGLE_CREDENTIALS_B64` | service account JSON đã base64 |
| `GOOGLE_SHEET_ID` | ID spreadsheet |

## Cấu trúc

```
bot.py                     toàn bộ bot (~1200 dòng, single file)
scripts/fetch_today.py     scrape minhchinh.com -> data/today.json (CI)
scripts/train_model.py     train model -> models/model_*.json (CI, hàng tuần)
scripts/analysis/          script kiểm chứng thuật toán (xem README trong đó)
models/model_{535,645,655}.json
.claude/PHAN_TICH_THUAT_TOAN.md   phân tích đầy đủ + danh sách bug
```

## Nguồn dữ liệu (thứ tự ưu tiên, sau fix 09/09/2026)

```
minhchinh.com  ->  Cloudflare Worker  ->  JSONL vietvudanh
```

- **minhchinh.com** — nguồn chính, realtime, có ngay sau giờ xổ
- **Cloudflare Worker** (`vietlott-proxy.regidgeneral.workers.dev`) — **đang hỏng**, trả
  `{"error":"Parse failed or no data","raw":""}`. Source code Worker **không nằm trong repo này**
- **JSONL** (`vietvudanh/vietlott-data`) — chỉ cập nhật ~00:01 hôm sau, không dùng được cho kỳ trong ngày

## Điều quan trọng nhất cần biết

**Bot không thể dự đoán số trúng.** Mỗi kỳ xổ độc lập; kỳ vọng số trúng của mọi cách chọn
đều bằng `k²/n` (5/35 → 0.714, 6/45 → 0.800, 6/55 → 0.655). Đã kiểm định trên 885 bộ số
thật: `|z| < 1.96` ở cả 3 loại, không khác ngẫu nhiên.

Khi thấy số liệu lệch xa mốc này, **nghi ngờ bug đo lường trước** — đã có 2 lần lệch và cả
hai đều là bug, không phải thuật toán tốt lên/xấu đi. Chi tiết ở `.claude/PHAN_TICH_THUAT_TOAN.md`.

## Cạm bẫy đã gặp

- **Regex kết quả:** chỉ 5/35 có phần `- Lúc HH:MM` (xổ 2 lần/ngày). 6/45 và 6/55 **không có**.
  Phần giờ phải để optional, nếu không sẽ luôn parse ra 0 kết quả cho 2 loại đó.
- **Locale Google Sheets:** `get_all_values()` trả về chuỗi **đã format** theo locale sheet
  (tiếng Việt → `"0,8"`). Luôn dùng `parse_score()`, đừng gọi thẳng `float()`.
- **Nhãn kỳ:** gợi ý luôn dành cho kỳ **sắp** xổ. Dùng `next_ky_str()`, đừng dùng thẳng kết quả
  của `fetch_latest_result()` (đó là kỳ vừa xổ xong).
- **`except:` trần** nuốt lỗi ở rất nhiều chỗ trong codebase này — là nguyên nhân khiến 2 bug
  trên sống sót nhiều tháng. Cẩn thận khi thêm mới.
- **Export sheet để phân tích:** dùng `export?format=csv&gid=N`, **không** dùng
  `gviz/tq?tqx=out:csv` (gviz trả ô rỗng khi kiểu dữ liệu cột không đồng nhất).

## Quy ước sau đợt sửa 09/09/2026

- **Mọi lời gọi mạng / Google Sheets trong `async def` phải bọc `asyncio.to_thread(...)`.**
  Nếu thêm hàm blocking mới, nhớ bọc — nếu không sẽ chặn event loop và scheduler lỡ kỳ.
- `make_button()` là **async**, gọi bằng `view=await make_button(sms)`. Nó trả
  `discord.utils.MISSING` khi không rút gọn được URL (đừng đổi thành `None`).
- Khi thêm field vào embed kết quả, nhớ giới hạn: field ≤ 1024, cả embed ≤ 6000, ≤ 25 field.
- Ghi vào sheet `suggestions` phải tách dòng theo `BO_MOI_DONG` (35 cột).
- `get_combined_data()` gộp theo **số kỳ**, không nối list — nối thẳng sẽ đếm đôi.
- **Đừng gõ tay nhãn "max N bộ"** trong `bao*_choices` và đừng hardcode `Range[int, 1, N]`.
  Cả hai sinh từ `BAO_535` / `BAO_645_655` + `max_bo()`. Đổi `GIOI_HAN_NGAY` là mọi thứ
  tự khớp; gõ tay đã gây lệch một lần khi hạn mức 5/35 đổi 1tr → 2,5tr.

## Hạn mức (cập nhật 09/09/2026)

Hai tầng, đừng lẫn:

| Loại | Hạn mức NGÀY (tiền) | Bộ tối đa theo ngày | Bộ tối đa MỖI LỆNH |
|---|---|---|---|
| 5/35 | **2.500.000đ** | 125 (bd2) | **50** (`SO_BO_MOI_LENH`) |
| 6/45 | 2.100.000đ | 30 (b7) | 30 |
| 6/55 | 2.100.000đ | 30 (b7) | 30 |

- `max_bo()` → trần theo tiền · `max_bo_moi_lenh()` → `min(max_bo, SO_BO_MOI_LENH)`
- Nhãn choice và `Range` dùng bản `_moi_lenh`. Sinh qua `nhan_bao()`, đừng gõ tay.
- Giới hạn mềm 50 có lý do đo được: ở 125 bộ SMS dài 2885 ký tự (~19 đoạn) và URL 4678
  ký tự → TinyURL dễ từ chối → mất nút bấm. Cap 50 kéo về 1610 ký tự (~11 đoạn).
- ⚠️ Bot **không cộng dồn chi tiêu trong ngày** qua nhiều lệnh — gọi 3 lệnh `bd2` là vượt
  hạn mức mà không có cảnh báo. Muốn chặn thật phải lưu state theo user + ngày.

## Chưa sửa

Xem mục 5 trong `.claude/PHAN_TICH_THUAT_TOAN.md`. Đáng chú ý nhất:

1. **Alert jackpot spam** — bắn 2 lần/ngày khi jackpot > 12 tỷ (hiện 35,9 tỷ), chưa có dedupe
2. `_ml_pick` bỏ qua `freq` / `days_since` / `pair_freq` — tính xong rồi vứt
3. Vòng "adaptive weights" trong `train_model.py` tối ưu theo nhiễu
4. Dead code: `get_performance_weights`, `sms_bao535_bc/bd`, `sms_bao_645_655`
5. `Intents.all()` đòi privileged intents; `Intents.default()` là đủ của Discord
