# -*- coding: utf-8 -*-
# api_server.py — SoundInsight HTTP API（FastAPI）。
# 启动：python api_server.py  （默认 127.0.0.1:7860，见 config.json）
# 接口：GET /health  POST /predict {"texts": [...]}
# 与 soundinsight_agent / benchmark 共用 predict_core，保证口径一致。
import json
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)

from predict_core import load, predict_batch  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = load()
    app.state.device = state["device_name"]
    app.state.threshold = state["thr"]
    print(f"[api] models loaded (device={state['device_name']}, "
          f"threshold={state['thr']:.4f})")
    yield


app = FastAPI(title="SoundInsight API",
              description="音质差评识别与五类归因（本地推理，数据不出境）",
              version="1.0.0", lifespan=lifespan)


class PredictRequest(BaseModel):
    texts: list[str]


@app.get("/health")
def health():
    return {"status": "ok", "device": app.state.device,
            "threshold": app.state.threshold}


@app.post("/predict")
def predict(req: PredictRequest):
    results = predict_batch(req.texts)
    n_neg = sum(1 for r in results if r["pred"] == 1)
    n_unsup = sum(1 for r in results if r["is_unsupported"])
    return {"n": len(results), "n_negative": n_neg,
            "n_unsupported": n_unsup, "results": results}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=CFG["server_host"], port=int(CFG["server_port"]))
