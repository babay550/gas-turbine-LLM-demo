import datetime
import os
import time

from fastapi import FastAPI, Request, Response
from starlette.requests import ClientDisconnect

app = FastAPI()
SAVE_DIR = "./photos"
os.makedirs(SAVE_DIR, exist_ok=True)


@app.post("/upload")
async def upload(request: Request) -> Response:
    t0 = time.monotonic()
    if request.headers.get("content-type") != "image/jpeg":
        return Response(content="Unsupported", status_code=415)
    try:
        data = await request.body()
    except ClientDisconnect:
        print("Client disconnected before upload completed")
        return Response(content="Client disconnected", status_code=499)
    t_recv = time.monotonic()
    filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S.jpg")
    with open(os.path.join(SAVE_DIR, filename), "wb") as f:
        f.write(data)
    t_write = time.monotonic()
    recv_ms = round((t_recv - t0) * 1000)
    write_ms = round((t_write - t_recv) * 1000)
    total_ms = round((t_write - t0) * 1000)
    speed_kbs = round(len(data) / 1024 / (t_recv - t0), 1) if t_recv > t0 else 0
    print(f"Saved {filename}, size={len(data)}B, recv={recv_ms}ms, write={write_ms}ms, total={total_ms}ms, speed={speed_kbs}KB/s")
    return Response(content="http://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/prod/qwen3-tts/20260610/1824955572943589/6c08bf88-82a3-48e4-a903-74ec77048e29.wav?Expires=1781160281&OSSAccessKeyId=LTAI5tGzqbGcEmE58b221XQy&Signature=x20gP4QOzLgBFQgLjmq3cQAkDA4%3D", status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18080)
