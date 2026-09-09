"""
2 cau hoi:
1. Chenh lech bot_ml vs random co that khong, hay chi la nhieu? -> chay nhieu seed
2. Vi sao "truoc trung 3-4 so, gio toan miss"? -> phan tich chuoi nong/lanh
"""
import random, statistics, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest import (load_draws, compute_model, ml_pick, CONFIGS,
                      WINDOW_MID, N_SETS)

BACKTEST_LAST = 300


def multi_seed(type_key, n_seeds=10):
    cfg = CONFIGS[type_key]
    n_total, k = cfg["n"], cfg["k"]
    draws = load_draws(type_key)
    start = max(WINDOW_MID + 50, len(draws) - BACKTEST_LAST)
    baseline = k * k / n_total

    # Train truoc 1 lan cho moi ky (khong phu thuoc seed) de tiet kiem
    prepared = []
    for i in range(start, len(draws)):
        history = draws[:i]
        prepared.append((compute_model(history, cfg),
                         list(history[-1][:k]),
                         set(draws[i][:k])))

    bot_avgs, rnd_avgs = [], []
    per_draw_bot = None
    for s in range(n_seeds):
        random.seed(1000 + s)
        bot_scores, rnd_scores, per_draw = [], [], []
        for model, last_draw, actual in prepared:
            seen = set()
            draw_hits = []
            for _ in range(N_SETS):
                nums = ml_pick(model, n_total, k, seen, last_draw)
                seen.add(tuple(nums))
                h = len(set(nums) & actual)
                bot_scores.append(h)
                draw_hits.append(h)
                rnd_scores.append(len(set(random.sample(range(1, n_total + 1), k)) & actual))
            per_draw.append(max(draw_hits))  # bo trung nhieu nhat trong 5 bo cua ky do
        bot_avgs.append(statistics.mean(bot_scores))
        rnd_avgs.append(statistics.mean(rnd_scores))
        if per_draw_bot is None:
            per_draw_bot = per_draw

    print(f"\n{'='*74}")
    print(f"  {type_key} - {n_seeds} lan chay doc lap ({len(prepared)} ky x {N_SETS} bo)")
    print(f"  Ky vong ly thuyet: {baseline:.4f}")
    print(f"{'='*74}")
    print(f"  bot_ml : {statistics.mean(bot_avgs):.4f}  (min {min(bot_avgs):.4f} / max {max(bot_avgs):.4f}, sd {statistics.stdev(bot_avgs):.4f})")
    print(f"  random : {statistics.mean(rnd_avgs):.4f}  (min {min(rnd_avgs):.4f} / max {max(rnd_avgs):.4f}, sd {statistics.stdev(rnd_avgs):.4f})")
    diff = statistics.mean(bot_avgs) - statistics.mean(rnd_avgs)
    print(f"  -> chenh lech bot vs random: {diff:+.4f} (dao dong tu nhien +-{statistics.stdev(bot_avgs)*2:.4f})")
    return per_draw_bot


def hot_cold_streaks(type_key, per_draw, window=30):
    """Rolling window: 'bo trung nhieu nhat moi ky' trung binh qua tung giai doan."""
    print(f"\n  --- {type_key}: cam nhac 'giai doan nong / giai doan lanh' ---")
    print(f"  (so so trung cua BO TOT NHAT trong 5 bo, trung binh {window} ky lien tiep)")
    rolls = []
    for i in range(0, len(per_draw) - window + 1, window // 2):
        w = per_draw[i:i + window]
        rolls.append((i, statistics.mean(w), max(w)))
    for i, avg, mx in rolls:
        bar = "#" * int(avg * 30)
        print(f"   ky {i:>3}-{i+window:<3} | TB {avg:.2f} | cao nhat {mx} so | {bar}")
    vals = [a for _, a, _ in rolls]
    print(f"   => giai doan te nhat {min(vals):.2f} vs tot nhat {max(vals):.2f} "
          f"(chenh {max(vals)/max(min(vals),0.01):.1f} lan) - THUAN TUY NGAU NHIEN")

    n3 = sum(1 for x in per_draw if x >= 3)
    n4 = sum(1 for x in per_draw if x >= 4)
    print(f"   => trong {len(per_draw)} ky: {n3} ky co bo trung >=3 so ({n3/len(per_draw)*100:.1f}%), "
          f"{n4} ky trung >=4 so ({n4/len(per_draw)*100:.1f}%)")


if __name__ == "__main__":
    for tk in sys.argv[1:] or ["535"]:
        pd_ = multi_seed(tk)
        hot_cold_streaks(tk, pd_)
