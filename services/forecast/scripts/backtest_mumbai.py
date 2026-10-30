"""Mumbai backtest of the forecast engine on the simulated history; writes services/forecast/eval/backtest_mumbai.json."""
import asyncio, json, sys, time, subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forecast.config import Settings
from forecast.engine import Engine
from forecast.network import load_network
IST = ZoneInfo("Asia/Kolkata")
net = load_network(ROOT.parents[1] / "cities" / "mumbai")
windows = {"2026-10-27_30": datetime(2026, 10, 30, 0, 0, tzinfo=IST),
           "2026-09-24_26 (monsoon; Anant Chaturdashi 25 Sep 2026, approximate)": datetime(2026, 9, 27, 0, 0, tzinfo=IST)}
out = {"label": "SIMULATED history (synthetic.py, seed in the module) · MODELLED V/C",
       "network": net.source, "segments": len(net.segments),
       "commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"]).decode().strip(),
       "run_at": datetime.now(IST).isoformat(timespec="seconds"), "windows": {}}
for name, end in windows.items():
    s = Settings(data_source="synthetic", contender="timesfm", backtest_days=3, backtest_stride_hours=6, context_days=14)
    eng = Engine(s, net)
    t0 = time.time()
    bt = asyncio.run(eng.backtest(end=end))
    bt["wall_s"] = round(time.time() - t0, 1)
    out["windows"][name] = bt
    try:
        eng.model.slot.unload()
    except Exception:
        pass
    print(name, {k: v.get("mae_vc") for k, v in bt.get("models", {}).items()}, flush=True)
(ROOT / "eval").mkdir(exist_ok=True)
(ROOT / "eval" / "backtest_mumbai.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("written")
