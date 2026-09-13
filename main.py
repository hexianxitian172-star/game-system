import os
import random
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# .env ファイルからトークンを読み込む
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 参加者を保持するリスト
players = []

# --- 🖥️ 管理画面機能 ---
@app.get("/admin", response_class=HTMLResponse)
def control_center(request: Request):
    # templatesフォルダのadmin.htmlに、requestとplayersのデータを渡して描画
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"players": players}
    )

# 🎮 ゲーム開始処理 (POST)
@app.post("/admin/start")
def start_game(
    oni_count: int = Form(2),
    camp_sizes: str = Form("3,3"),
    disable_wolf: bool = Form(False)  # ★人狼無効化フラグを受け取る
):
    global players
    sizes = [int(s.strip()) for s in camp_sizes.split(",")]

    random.shuffle(players) # プレイヤー順をランダム化

    # 1. 鬼の割り当て
    for p in players[:oni_count]:
        p["role"] = "鬼"
        p["team"] = "鬼"

    # 2. 逃走者チーム＆人狼の割り当て
    remaining = players[oni_count:]
    team_names = ["A", "B", "C", "D"]

    for i, size in enumerate(sizes):
        if i >= len(team_names): break
        team_members = remaining[:size]
        remaining = remaining[size:]

        if team_members:
            if disable_wolf:
                # ★人狼OFF：チーム全員を「逃走者」にする
                for p in team_members:
                    p["role"] = "逃走者"
                    p["team"] = f"{team_names[i]}チーム"
            else:
                # ★人狼ON：先頭の1人を「人狼」、残りを「逃走者」にする
                werewolf = team_members.pop(0)
                werewolf["role"] = "人狼"
                werewolf["team"] = f"{team_names[i]}チーム"

                for p in team_members:
                    p["role"] = "逃走者"
                    p["team"] = f"{team_names[i]}チーム"

    return RedirectResponse(url="/admin", status_code=303)

# 🔄 参加者リセット処理 (POST)
@app.post("/admin/reset")
def admin_reset():
    global players
    players.clear() # リストを完全に空にする
    return RedirectResponse(url="/admin", status_code=303)


# --- 🤖 LINE Webhook 機能 ---
@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    events = body.get("events", [])
    
    for event in events:
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            reply_token = event["replyToken"]
            user_text = event["message"]["text"].strip()
            user_id = event["source"].get("userId")
            
            reply_text = await handle_command(user_text, user_id)
            await send_line_reply(reply_token, reply_text)
            
    return JSONResponse(content={"status": "success"})

async def get_line_profile(user_id: str) -> str:
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("displayName", "不明なユーザー")
    return "ゲスト"

async def handle_command(user_text: str, user_id: str) -> str:
    global players
    if user_text == "参加":
        if any(p["user_id"] == user_id for p in players):
            return "⚠️ あなたはすでに参加登録されています！"
        user_name = await get_line_profile(user_id) if user_id else "ゲスト"
        players.append({"user_id": user_id, "name": user_name, "role": "未割り当て", "team": "未設定"})
        return f"✅ {user_name} さんの参加登録が完了しました！\n現在の参加者数: {len(players)}名"

    elif user_text in ["参加者", "参加者一覧", "メンバー"]:
        if not players: return "📋 現在の参加者はまだいません。"
        member_list = "\n".join([f"・{p['name']} ({p['role']})" for p in players])
        return f"📋 【現在の参加者一覧 ({len(players)}名)】\n{member_list}"

    elif user_text in ["リセット", "参加リセット"]:
        players.clear()
        return "🔄 参加者リストをリセットしました。"
    else:
        return "「参加」「参加者」「リセット」が使えます。"

async def send_line_reply(reply_token: str, text: str):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {"replyToken": reply_token, "messages": [{"type": "text", "text": text}]}
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload, headers=headers)