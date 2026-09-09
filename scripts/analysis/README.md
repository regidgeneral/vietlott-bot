# Script kiểm chứng thuật toán

Đi kèm `.claude/PHAN_TICH_THUAT_TOAN.md`. Chạy lại được bất cứ lúc nào để kiểm tra.

## Chuẩn bị dữ liệu

```powershell
# JSONL lịch sử (cho backtest.py / variance.py)
foreach($t in @('535','645','655')){
  curl.exe -s -o "$env:TEMP\v$t.jsonl" `
    "https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power$t.jsonl"
}

# Google Sheet -> CSV (cho analyze_sheet.py / verify.py / final_stats.py / sim_weights.py)
# Sheet phải để "Anyone with the link -> Viewer" trong lúc chạy.
$id  = $env:GOOGLE_SHEET_ID          # đừng hardcode ID vào đây — repo này public
$gid = @{ '535'=0; '645'=383875126; '655'=931735051;
          'suggestions'=46215372; 'performance'=1528130779 }
foreach($k in $gid.Keys){
  curl.exe -s -L -o "scripts\analysis\sheet_$k.csv" `
    "https://docs.google.com/spreadsheets/d/$id/export?format=csv&gid=$($gid[$k])"
}
```

> Dùng `export?format=csv`, **không** dùng `gviz/tq?tqx=out:csv` — gviz suy luận kiểu cột và
> trả về rỗng cho ô lệch kiểu, gây hiểu nhầm là dữ liệu bị mất.

## Các script

| Script | Mục đích | Nguồn dữ liệu |
|---|---|---|
| `backtest.py` | Walk-forward 300 kỳ: so `_ml_pick` với random / hottest / coldest / fixed | JSONL |
| `variance.py` | 10 seed độc lập + phân tích chuỗi nóng-lạnh | JSONL |
| `analyze_sheet.py` | Tự chấm lại toàn bộ gợi ý, phát hiện kỳ thiếu | Sheet CSV |
| `verify.py` | Kiểm chứng bug nhãn kỳ (tỷ lệ bộ trúng 0 số) | Sheet CSV |
| `final_stats.py` | Kiểm định chi-square + z-test vs phân bố siêu bội | Sheet CSV |
| `sim_weights.py` | Mô phỏng `get_adaptive_weights()` để lộ selection bias | Sheet CSV |
| `test_fixes.py` | Test `next_ky_str` / `parse_score` / 3 nguồn realtime | mạng thật |
| `test_integration.py` | Chạy thật `post_result`, `save_suggestions`, `make_button` với mock — kiểm giới hạn Discord, tách dòng sheet, cửa sổ scheduler | mock |
| `test_combined.py` | Kiểm `get_combined_data` khử trùng đúng số kỳ | JSONL + Sheet CSV |
| `test_gioihan.py` | Kiểm hạn mức 2,5tr: nhãn choice khớp `max_bo()`, `Range` đúng, embed ở ca xấu nhất (bd2 125 bộ) | mock |
| `audit_limits.py` | Tính chính xác giới hạn 1024/6000 ký tự và độ dài URL SMS | không cần |
| `check_cols.py` | Đối chiếu số bộ tối đa mỗi lệnh với số cột sheet | Sheet CSV |
| `check_dup.py` | Đo mức trùng lặp kỳ giữa JSONL và Sheets | JSONL + Sheet CSV |

Ba script `test_*.py` nạp `bot.py` qua AST và gỡ `client.run()` nên **không** đăng nhập
Discord thật. `test_integration.py` và `test_combined.py` không gọi mạng.

## Chạy

```powershell
python scripts\analysis\backtest.py          # ~1 phút
python scripts\analysis\variance.py 535 645  # ~2 phút
python scripts\analysis\analyze_sheet.py
python scripts\analysis\final_stats.py
python scripts\analysis\sim_weights.py
python scripts\analysis\test_fixes.py        # cần: pip install discord.py beautifulsoup4 pytz gspread google-auth
```

## Con số mốc

Kỳ vọng số trúng của **mọi** cách chọn = `k²/n`:

| Loại | Kỳ vọng |
|---|---|
| 5/35 | 0.714 |
| 6/45 | 0.800 |
| 6/55 | 0.655 |

Nếu một lần chạy cho kết quả lệch xa mốc này, hãy nghi ngờ **bug đo lường** trước khi nghĩ
thuật toán đã tốt lên hay xấu đi.
