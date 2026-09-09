# Phân tích thuật toán chọn số VietlottBot

**Ngày phân tích:** 09/09/2026
**Câu hỏi ban đầu:** "Bot chọn số không ổn — trước có khi trúng 3-4 số, giờ toàn miss hoặc trúng 1 số."
**Kết luận ngắn:** Thuật toán chọn số **không hỏng**. Cái hỏng là **hệ thống đo lường**.

---

## 1. Kết luận chính

Kiểm định trên **885 bộ số thật** bot đã gợi ý, đối chiếu kết quả xổ thật từ Google Sheet
(chỉ lấy `source=scheduler` — nguồn duy nhất không dính bug nhãn kỳ):

| Loại | Số bộ | Trúng TB thật | Nếu bốc ngẫu nhiên | z | Kết luận |
|---|---|---|---|---|---|
| 5/35 | 620 | 0.661 | 0.714 | −1.80 | không khác ngẫu nhiên |
| 6/45 | 130 | 0.831 | 0.800 | +0.45 | không khác ngẫu nhiên |
| 6/55 | 135 | 0.711 | 0.655 | +0.90 | không khác ngẫu nhiên |

Cả 3 đều `|z| < 1.96`. Chi-square cũng không bác bỏ giả thuyết ngẫu nhiên.

Phân bố số trúng của 5/35 khớp gần như tuyệt đối với phân bố siêu bội (hypergeometric):

```
trúng   thực tế   ngẫu nhiên
  0     48.39%      43.90%
  1     38.39%      42.21%
  2     11.94%      12.51%
  3      1.29%       1.34%   <- khớp gần như hoàn hảo
  4      0.00%       0.05%
```

**Trúng 4 số: 0 lần trên 885 bộ. Trúng 3 số: 12 lần (1.3%).**

### Vì sao "trước ngon hơn"

Mỗi kỳ xổ độc lập. Kỳ vọng số trúng của **mọi** cách chọn đều bằng `k²/n`:

- 5/35 → 25/35 = **0.714** số trúng/bộ
- 6/45 → 36/45 = **0.800**
- 6/55 → 36/55 = **0.655**

Không thuật toán nào thay đổi được con số này. Backtest walk-forward 300 kỳ gần nhất,
10 lần chạy độc lập, xác nhận:

| Loại | bot_ml | random thuần | chênh lệch | dao động tự nhiên |
|---|---|---|---|---|
| 5/35 | 0.7132 | 0.7184 | −0.005 | ±0.034 |
| 6/45 | 0.8165 | 0.8019 | +0.015 | ±0.032 |

Chênh lệch **nhỏ hơn nhiễu**. Ngay cả chiến lược `fixed_12345` (chọn cứng `01 02 03 04 05`
mãi mãi, không nhìn lịch sử) cũng cho 0.63/0.73/0.56 — vẫn trong biên nhiễu.

Cảm giác "hồi trước bot ngon hơn" là **ký ức chọn lọc**: ta nhớ vài lần trúng 3 số (hiếm,
ấn tượng) và quên hàng chục kỳ trúng 0-1 số xen giữa. Phân tích rolling window 30 kỳ cho
thấy giai đoạn "nóng" và "lạnh" chênh nhau 1.3 lần — thuần túy ngẫu nhiên, không nguyên nhân.

---

## 2. Bug đã sửa

### Bug #1 — Gợi ý thủ công bị gắn nhãn kỳ đã xổ (đã sửa)

**Triệu chứng đo được:**

| Nguồn | Số bộ | Tổng số trúng | % bộ trúng 0 số |
|---|---|---|---|
| `655` / bao thủ công | 51 | **0** | **100.0%** |
| `535` / bao thủ công | 246 | 15 | 95.5% |
| `535` / scheduler | 620 | 410 | 48.4% *(bình thường)* |

51/51 bộ trúng 0 số. Xác suất tự nhiên trúng 0 số ở 6/55 là 48%, nên 100% **không thể là
xui** — đó là dấu vết của loại trừ có hệ thống.

**Nguyên nhân:** `bot.py` gắn nhãn gợi ý bằng kỳ **vừa xổ xong**:

```python
ky_latest, _, _ = fetch_latest_result(type_key)
ky_save = ky_latest.split(" ")[0]        # <- kỳ VỪA XỔ, sai
```

Trong khi `_ml_pick()` lại **cố ý loại bỏ đúng các số của kỳ đó** khỏi pool:

```python
recent = set(last_draw or model.get("last_draw", []))
candidates = [... for n in range(1, n_total+1) if n not in recent]
```

Bot loại 6 số ra, rồi tự chấm điểm mình bằng chính 6 số đã loại → kết quả toán học bắt buộc = 0.

Nhánh `scheduler` làm đúng (cộng `+1`), nên chỉ nguồn đó có số liệu đáng tin.

**Cách sửa:** thêm helper `next_ky_str()` và dùng chung cho cả 4 chỗ (3 chỗ manual + scheduler),
để không tồn tại 2 bản logic `+1` dễ lệch nhau.

```python
def next_ky_str(ky):
    """'00874 (08/09/2026)' -> '00875'"""
    try:
        return str(int(str(ky).split(" ")[0]) + 1).zfill(5)
    except (ValueError, TypeError, AttributeError):
        return str(ky).split(" ")[0] if ky else "?"
```

### Bug #2 — Bot tự chấm điểm mình cao hơn thực tế (đã sửa)

Từ **01/07/2026**, cột `avg_matched` trong sheet `performance` bắt đầu lưu dạng `"0,8"`
(dấu phẩy — locale tiếng Việt). `get_all_values()` trả về chuỗi **đã format theo locale**,
nên `float("0,8")` ném `ValueError`, và lỗi bị nuốt bởi `except: continue`.

Nhưng `float("1")` thì **chạy được**. Nên bộ lọc chỉ giữ lại các điểm **số nguyên** — mà số
nguyên phần lớn là `1.0`.

Với 5/35, 30 dòng gần nhất:

```
đọc được: 4/30  ->  [1.0, 1.0, 1.0, 1.0]
avg bot tự tính = 1.0000   ->  "GOOD performance"  ->  w_recent = 4.2
avg THẬT (cả 30 dòng)  = 0.7867  ->  chỉ NEUTRAL  ->  w_recent phải là 3.0
```

Với 6/55: bot tự chấm 0.927, thật là 0.767 → đẩy `w_recent` lên 4.25.

Đây là **selection bias**: bug vứt bỏ mọi mẫu điểm thấp, chỉ giữ mẫu điểm cao. Suốt 2 tháng,
vòng lặp "tự học" của bot học từ dữ liệu bị lọc thiên vị và tự thưởng cho mình.

Tổng cộng **139/270 dòng** performance không đọc được — riêng `source=scheduler` mất **62%**.

**Cách sửa:** hàm `parse_score()` chịu được cả `'0.8'` lẫn `'0,8'`, đặt ở cả `bot.py` và
`scripts/train_model.py`. Thêm guard `if not scores` để tránh `ZeroDivisionError`.

> **Lưu ý:** sửa bug này **không** cải thiện tỷ lệ trúng — như phần 1 đã chứng minh, không
> trọng số nào thay đổi được `k²/n`. Nó chỉ khiến bot ngừng tự lừa dối.

### Bug #3 — Cloudflare Worker chết, mất kết quả trong ngày (đã sửa)

```
GET https://vietlott-proxy.regidgeneral.workers.dev/?type=535
-> 404 {"error":"Parse failed or no data","raw":""}
```

Worker vẫn sống (route vẫn nhận request, thiếu param trả 400 đúng) nhưng phần scrape upstream
trả rỗng.

**Hậu quả dây chuyền:**

1. Worker fail → fallback JSONL của `vietvudanh/vietlott-data`
2. JSONL chỉ cập nhật lúc **~00:01 sáng hôm sau** (kiểm chứng qua `process_time`)
3. Scheduler chạy 13:35 / 21:35 → JSONL chưa có kỳ hôm nay → retry 6 lần × 120s = 10 phút
   → gửi "⚠️ Không lấy được kết quả"
4. `get_jackpot_535()` luôn trả `None` → mất alert kỳ chia giải độc đắc

**Mất dữ liệu đo được trong sheet:**

| Loại | Kỳ lưu được | Thiếu | Thiếu gần đây |
|---|---|---|---|
| 5/35 | 733 / 873 | **140 (16%)** | 871, 868, 862, 850, 833, 825, 811 |
| 6/45 | 1356 | 6 | 1534, 1535, 1536 |
| 6/55 | 1388 | 7 | 1370, 1371, 1372, 1392 |

Ngoài ra 84 bộ số gợi ý không bao giờ chấm được vì kỳ tương ứng không có trong sheet.

**Cách sửa:** đưa minhchinh.com (đã verify còn hoạt động) làm **nguồn chính**, Worker và JSONL
thành dự phòng:

```
fetch_latest_result:  minhchinh.com  ->  Cloudflare Worker  ->  JSONL
```

### Bug #3b — Regex chỉ khớp 5/35, không khớp 6/45 và 6/55 (đã sửa)

Phát hiện trong lúc sửa #3. Regex cũ **bắt buộc** có phần `- Lúc HH:MM`:

```python
r'kỳ\s+#(\d+)\s+ngày\s+(\d{2}/\d{2}/\d{4})\s*-\s*Lúc\s+(\d+:\d+)\s+((?:\d+\s*){4,8})'
```

Nhưng chỉ 5/35 có giờ (xổ 2 lần/ngày). 6/45 và 6/55 xổ 1 lần/ngày nên **không có** phần đó:

```
535:  kỳ #874  ngày 08/09/2026 - Lúc 21:00  04 07 14 16 23 10
645:  kỳ #1559 ngày 06/09/2026             09 14 22 26 27 40
655:  kỳ #1395 ngày 08/09/2026             08 11 14 23 25 54 17
```

Nghĩa là `scripts/fetch_today.py` **chưa bao giờ** lấy được kết quả 6/45 và 6/55 — giải thích
vì sao `data/today.json` luôn rỗng cho 2 loại này.

**Cách sửa:** làm phần giờ thành optional `(?:-\s*Lúc\s+(\d+:\d+))?` ở cả `bot.py` và
`scripts/fetch_today.py`, kèm fallback `m.group(3) or ""`.

---

## 3. Kiểm chứng sau khi sửa

Đối chiếu với JSONL độc lập — khớp chính xác:

```
535: ky=00874 (08/09/2026)  nums=[4, 7, 14, 16, 23]      special=10
645: ky=01559 (06/09/2026)  nums=[9, 14, 22, 26, 27, 40] special=None
655: ky=01395 (08/09/2026)  nums=[8, 11, 14, 23, 25, 54] special=17
get_jackpot_535() = 35,959,161,000d
```

`fetch_today.py` sau khi sửa, giả lập ngày 08/09/2026:

```
535: 2 kết quả (13:00 và 21:00)   <- đúng, xổ 2 lần/ngày
645: 0 kết quả                    <- đúng, 08/09 là thứ Ba, 6/45 không xổ
655: 1 kết quả                    <- đúng
```

Script kiểm chứng nằm ở `scripts/analysis/`, chạy lại được bất cứ lúc nào.

---

## 4. Đợt sửa 2 — hạ tầng & toàn vẹn dữ liệu

### Bug #4 — `requests` blocking trong `async def` (đã sửa)

Mọi handler gọi mạng/Sheets đồng bộ ngay trên event loop. Một lệnh `/535` chặn loop
trong nhiều giây → discord.py báo "Heartbeat blocked", và `scheduler()` (so khớp phút
chính xác) **lỡ hẳn kỳ cần chạy**.

Đã bọc bằng `asyncio.to_thread(...)` tại: `get_combined_data`, `fetch_latest_result`,
`save_suggestions`, `save_result`, `compare_with_suggestions`, `track_performance`,
`get_jackpot_535`, `shorten_url`.

`make_button()` chuyển thành `async`: chỉ `shorten_url` chạy trong thread, còn
`discord.ui.View` phải dựng trên event loop nên không gộp cả hàm vào `to_thread` được.

Khối đọc Sheets nội tuyến trong `post_result` được tách thành `track_performance()`
để có thể đẩy sang thread.

### Bug #5 — `on_ready` tạo scheduler chồng (đã sửa)

`on_ready` fire lại sau **mỗi** lần reconnect → thêm một `create_task(scheduler())` →
báo kết quả trùng lặp; `tree.sync()` mỗi lần cũng dễ dính rate limit. Đã thêm cờ
`_khoi_dong_xong`.

`scheduler()` cũng được viết lại: khớp theo **cửa sổ 10 phút** thay vì đúng 1 phút,
kèm `_da_chay` để mỗi lịch chỉ chạy 1 lần/ngày kể cả khi có nhiều scheduler cùng sống.
Chu kỳ vòng lặp giảm 60s → 30s.

| Tình huống | Trước | Sau |
|---|---|---|
| Đúng giờ hẹn | chạy | chạy |
| Trễ 90s (loop bị chặn) | **lỡ hẳn** | chạy |
| Trễ 599s | lỡ | chạy |
| Trễ 601s | lỡ | bỏ qua (không báo muộn) |
| 2 scheduler cùng sống | **báo 2 lần** | báo 1 lần |

### Bug #6 — `shorten_url` tạo link cụt (đã sửa)

`return url[:512]` cắt giữa chuỗi query → nút SMS hỏng mà người dùng không biết.
Đo thực tế: **14/25 loại bao có URL > 512 ký tự** (`bd2` 50 bộ = 1903), nên nhánh này
chạy thật chứ không hiếm. Nay trả `None` → `make_button` trả `discord.utils.MISSING`
→ không gắn nút, thà thiếu nút còn hơn nút hỏng.

### Bug #7 — embed vượt 6000 ký tự (đã sửa — regression do chính Bug #1)

Sau khi sửa nhãn kỳ, gợi ý thủ công **dồn đúng về kỳ sắp tới**, nên `post_result` có
thể phải hiển thị tới 17 nguồn (scheduler + manual + 15 loại bao). Đo được:

```
5 nguồn -> ~5400 ký tự / 6000   OK
6 nguồn -> ~6440 ký tự / 6000   VƯỢT -> post_result ném HTTPException
```

Tức là bài báo kết quả **mất hoàn toàn**. Đã thêm giới hạn: tối đa 8 bộ/nguồn, cắt
field ở 1000 ký tự, dừng thêm field khi tổng chạm 5200 hoặc đã có 20 field, kèm dòng
"còn N nguồn nữa". Mỗi nguồn giờ hiển thị thêm **trung bình số trúng/bộ**.

### Bug #8 — gợi ý bao > 30 bộ không được lưu (đã sửa)

Sheet `suggestions` rộng **35 cột** (5 metadata + 30 bộ). `/bao535 bd2` sinh tới 50 bộ
→ `append_row` vượt khung → gspread ném lỗi → bị `except` nuốt → **mất gợi ý mà không
ai biết**. Ảnh hưởng `535/bd2` (50 bộ) và `535/bd3` (33 bộ).

Đã tách thành nhiều dòng, mỗi dòng tối đa 30 bộ, cùng `(type_key, ky, source)`. Các hàm
đọc đều đã gộp theo `source` nên nhiều dòng vẫn cho kết quả đúng.

### Bug #9 — mỗi kỳ bị đếm HAI lần (đã sửa)

`get_combined_data` nối thẳng `jsonl_nums + sheets_nums` mà không khử trùng. Đo thực tế:

| Loại | JSONL | Sheets | Bot cộng dồn | Thực tế duy nhất | Thổi phồng |
|---|---|---|---|---|---|
| 5/35 | 800 | 733 | 1533 | 803 | +91% |
| 6/45 | 1362 | 1356 | **2718** | 1362 | **+100%** |
| 6/55 | 1395 | 1388 | **2783** | 1395 | **+99%** |

6/45 và 6/55 gần như đếm **mọi kỳ hai lần**. Embed hiển thị "2718 kỳ lịch sử" trong khi
thực tế chỉ có 1362.

Đã thay 4 hàm (`fetch_jsonl`, `load_from_sheets`, `compute_days_since_from_sheets`,
`compute_days_since`) bằng 2 hàm trả bản ghi `(ky, ngay, nums, sp)` rồi gộp theo số kỳ.
Sửa luôn 3 lỗi kèm theo:

- `get_sheet()` bị gọi **2 lần** mỗi lượt (2 lần tải cùng một sheet, 2× quota API) → còn 1
- `days_since` dùng `date.today()` = giờ **máy chủ** (Railway chạy UTC) → nay dùng `VN_TZ`
- `days_since` trước chỉ tính từ MỘT nguồn → nay từ cả hai
- `last_draw` nay đúng là kỳ mới nhất (535 → `[4,7,14,16,23]` = kỳ 874)

### Bug #10 — model cache không bao giờ hết hạn (đã sửa)

`_model_cache` giữ vĩnh viễn. Bot chạy 24/7 trên Railway vài tháng → mãi mãi dùng model
của lần khởi động đầu, **mọi lần retrain hàng tuần đều vô nghĩa**. Đã thêm TTL 6 giờ,
kèm fallback dùng bản cũ nếu tải lỗi.

### Sửa nhỏ kèm theo

- `run_bao535` / `run_bao645655`: thêm list `bo_da_sinh` giữ đúng thứ tự bộ số đã hiển thị
  (trước lưu từ `set` nên thứ tự ngẫu nhiên)
- Thêm `kiem_tra_env()` — báo thiếu `DISCORD_TOKEN`/`DISCORD_CHANNEL_ID` rõ ràng thay vì
  để discord.py ném "Improper token"; cảnh báo nếu thiếu biến Google Sheets
- Xoá dòng chết `_cache.pop(f"text_{type_key}")` (key này chưa từng được ghi)

### Đính chính

Ở bản ghi chú trước tôi liệt kê "`add_fields_chunked` vượt giới hạn 1024 ký tự/field".
Ở hạn mức cũ (1 triệu) thì trường hợp tệ nhất là `535/bd10` với **910/1024** — **không
vượt**. (Sau khi hạn mức lên 2,5 triệu thì vấn đề này thành thật — xem đợt sửa 3.)

---

## 4b. Đợt sửa 3 — hạn mức 5/35 lên 2.500.000đ

Hạn mức mua 5/35 mỗi ngày đổi từ **1.000.000đ → 2.500.000đ** (6/45 và 6/55 giữ nguyên
2.100.000đ). Thay đổi này lan ra nhiều chỗ hơn tưởng:

### Số bộ tối đa thay đổi toàn bộ

| Loại | Cũ | Mới | | Loại | Cũ | Mới |
|---|---|---|---|---|---|---|
| bc4 | 3 | 8 | | bd5 | 20 | 50 |
| bc6 | 16 | 41 | | bd6 | 16 | 41 |
| bc7 | 4 | 11 | | bd7 | 14 | 35 |
| bc8 | 1 | 4 | | bd8 | 12 | 31 |
| bd2 | 50 | **125** | | bd9 | 11 | 27 |
| bd3 | 33 | 83 | | bd10 | 10 | 25 |
| bd4 | 25 | 62 | | bd11 | 9 | 22 |
| | | | | bd12 | 8 | 20 |

### Nhãn choice hardcode → sinh tự động

15 nhãn `"BC4 – … – max 3 bộ"` được gõ tay trong `bao535_choices`, tất cả đều sai sau
khi đổi hạn mức. Nay sinh thẳng từ bảng giá:

```python
bao535_choices = [
    app_commands.Choice(
        name=f"{v['label']} ({fmt_gia(v['gia'])}) – max {max_bo(v['gia'], '535')} bộ",
        value=k)
    for k, v in BAO_535.items()
]
```

Làm tương tự cho 645/655 để cùng một loại lệch không tái diễn.

### `Range` của slash command

`so_bo: Range[int, 1, 50]` sẽ **chặn người dùng ở 50** trong khi bd2 cho phép 125.
Nay tính từ dữ liệu: `MAX_BO_535 = 125`, `MAX_BO_645 = MAX_BO_655 = 30`.

### `add_fields_chunked` — chunk cứng không còn đủ

Đo ở hạn mức mới:

```
bd12  20 bộ -> field 1019/1024   (sát nút, chỉ dư 5 ký tự)
bd2  125 bộ -> embed 6754/6000   VỠ -> HTTPException
```

Đã viết lại: gom theo **độ dài thật** thay vì 10 dòng cứng, có ngân sách embed 5500 và
trần 23 field, thừa thì ghi "Còn N bộ nữa — xem đầy đủ trong SMS". Kết quả sau sửa:

| Loại | Số bộ | Embed | Field | Field dài nhất |
|---|---|---|---|---|
| bd2 | 125 | 5464/6000 | 13 | 520/1024 |
| bd3 | 83 | 4945/6000 | 11 | 569/1024 |
| bd12 | 20 | 2191/6000 | 5 | 917/1024 |

### Bug #8 lan rộng hơn

Số loại bao vượt 35 cột của sheet `suggestions` tăng từ **2 lên 8**
(bd2, bd3, bd4, bd5, bd6, bd7, bd8, bc6). Fix tách dòng ở đợt 2 đã bao được:
125 bộ → 5 dòng, không mất bộ nào.

### Giới hạn mềm: 50 bộ mỗi lệnh

Ở 125 bộ, nội dung SMS dài **2885 ký tự** (~19 đoạn SMS) và URL trước khi rút gọn là
**4678 ký tự** — TinyURL dễ từ chối, khi đó bot bỏ nút (Bug #6) và người dùng mất nút bấm.

Đã thêm `SO_BO_MOI_LENH = 50`. **Hạn mức ngày 2.500.000đ giữ nguyên** — đây chỉ là trần
cho MỘT lệnh; muốn đặt thêm thì gọi lệnh nữa.

Số liệu khi chọn ngưỡng (ca xấu nhất trong 15 loại bao 5/35):

| Ngưỡng | SMS dài nhất | Số đoạn SMS | URL dài nhất |
|---|---|---|---|
| 20 | 1071 (bd12) | 8 | 1794 |
| **50 (đã chọn)** | **1610 (bd5)** | **11** | **2653** |
| 125 (không cap) | 2885 (bd2) | 19 | 4678 |

Lưu ý: cap theo **số bộ** không san bằng được gánh nặng, vì độ dài mỗi bộ rất khác nhau —
`bd12` chỉ 20 bộ đã 1071 ký tự, trong khi `bd2` 50 bộ mới 1160. Cap 50 giảm ca xấu nhất
từ 19 xuống 11 đoạn SMS, nhưng **13/15 loại vẫn cần TinyURL**.

Cấu trúc: `max_bo()` = trần theo tiền (hạn mức ngày), `max_bo_moi_lenh()` = `min(max_bo,
SO_BO_MOI_LENH)`. Nhãn choice và `Range` đều dùng bản `_moi_lenh`; nhãn nêu thêm hạn mức
ngày khi hai số khác nhau, ví dụ:

```
BD2  – Bao 2 số đặc biệt (20.000d) – max 50 bộ/lệnh (ngày: 125)
BD12 – Bao 12 số đặc biệt (120.000d) – max 20 bộ
```

Embed cũng in cả hai số, kèm cảnh báo bot **không cộng dồn chi tiêu trong ngày**.

Sau khi cap, ca xấu nhất của embed cũng nhẹ đi: `bd2` từ 5464 xuống **2770/6000**.

---

## 5. Vấn đề CHƯA sửa (chỉ ghi nhận)

| # | Vị trí | Vấn đề |
|---|---|---|
| 1 | `post_result` — alert jackpot | **Cần quyết định.** Alert bắn sau MỖI kỳ 535 (2 lần/ngày) khi jackpot > 12 tỷ, không có dedupe. Jackpot hiện tại là **35,9 tỷ** → bot sẽ spam 2 lần/ngày cho tới khi có người trúng. Nội dung còn ghi "kỳ 21:00 ngày mai" nên bắn sau kỳ 13:00 là sai nghĩa |
| 2 | `bot.py` `_ml_pick` | Bỏ qua hoàn toàn `freq`, `days_since`, `pair_freq`. Sau Bug #9 thì càng lãng phí: bot tính `pair_freq` trên 1362 kỳ rồi vứt đi |
| 3 | `scripts/train_model.py` | Vòng "adaptive weights" đang tối ưu theo nhiễu. Nên cân nhắc bỏ hẳn |
| 4 | `bot.py` `save_result` | Ghi `ky` kèm ngày vào cột "Kỳ" (`00870 (06/09/2026)`), trong khi dòng cũ chỉ có `00001` → cột B không nhất quán, mọi chỗ đọc phải `.split(" ")[0]` |
| 5 | `bot.py` | Dead code: `get_performance_weights`, `sms_bao535_bc`, `sms_bao535_bd`, `sms_bao_645_655` — định nghĩa nhưng không nơi nào gọi |
| 6 | `bot.py` | `discord.Intents.all()` đòi bật privileged intents trong Dev Portal. Bot chỉ dùng slash command + gửi tin nên `Intents.default()` là đủ |
| 7 | `data/today.json` | Không nơi nào trong `bot.py` đọc file này — pipeline GitHub Actions chạy không công |
| 8 | `scripts/train_model.py` | `datetime.utcnow()` deprecated từ Python 3.12 |
| 9 | Chi tiêu trong ngày | Bot **không cộng dồn** chi tiêu qua nhiều lệnh. Sau khi có giới hạn mềm 50 bộ/lệnh, người dùng gọi 3 lệnh `bd2` là vượt hạn mức ngày mà bot không cảnh báo. Cần state theo user+ngày nếu muốn chặn thật |

---

## 5. Ghi chú về kỳ vọng

Có **đúng một** thứ trong xổ số mà lựa chọn số ảnh hưởng được: **không phải xác suất trúng,
mà là số tiền nhận khi trúng.** Jackpot chia đều cho những người cùng trúng, nên tránh bộ số
mà nhiều người khác cũng chọn sẽ tăng kỳ vọng tiền thưởng.

Trớ trêu là `_ml_pick` đang làm **ngược lại**: chọn từ top-20 số có score cao nhất — tức "số
nóng", thứ mà ai cũng tra được trên minhchinh.com và cũng chọn theo. Bot đang đẩy người chơi
về phía đám đông.

Hướng cải tiến nếu muốn (không tăng tỷ lệ trúng, chỉ tăng giá trị khi trúng):

- Bỏ bias top-20, chọn đều trên toàn dải
- Ưu tiên bộ có ít nhất 2-3 số **> 31** (đa số người chơi dùng ngày sinh, chỉ 1-31)
- Tránh dãy liên tiếp và các bộ đối xứng/dễ nhớ

---

## 6. Về các nhóm "lúc nào cũng trúng lớn"

Dữ liệu 885 bộ số thật của chính bot này cho thấy tỷ lệ trúng 3 số là **1.3%** và trúng 4 số
là **0%**. Đây là giới hạn vật lý của trò chơi, không phải giới hạn của thuật toán.

Cách kiểm chứng một nhóm bất kỳ: yêu cầu họ **đăng công khai bộ số kèm timestamp trước giờ
xổ**, liên tục 20 kỳ, rồi tự tính tỷ lệ. Mô hình phổ biến là mua 200 bộ, khoe 1 bộ trúng, im
lặng 199 bộ trượt — hoặc chốt số sau giờ xổ rồi đăng ảnh.
