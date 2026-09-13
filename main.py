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

import os
import random  # ★ファイルの最上部でまとめてインポート
import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --------------------------------------------------
# 🖥️ 管理画面表示 (GET)
# --------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
def get_admin(request: Request):
    display_players = []
    for p in players:
        p_copy = dict(p)
        if view_mode == "driver" and p_copy.get("role") == "人狼":
            p_copy["role"] = "逃走者"
        display_players.append(p_copy)

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "players": display_players,
            "view_mode": view_mode,
            "announcements": announcements,
            "game_schedule": game_schedule
        }
    )

import os
import random
import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --------------------------------------------------
# 🖥️ 管理画面表示 (GET)
# --------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
def get_admin(request: Request):
    display_players = []
    for p in players:
        p_copy = dict(p)
        if view_mode == "driver" and p_copy.get("role") == "人狼":
            p_copy["role"] = "逃走者"
        display_players.append(p_copy)

    # 全バージョン対応の TemplateResponse 構文
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "players": display_players,
            "view_mode": view_mode,
            "announcements": announcements,
            "game_schedule": game_schedule
        }
    )

# --------------------------------------------------
# 🎮 ゲーム開始処理 (POST)
# --------------------------------------------------
@app.post("/admin/start")
def start_game(
    oni_count: int = Form(2),
    camp_sizes: str = Form("3,3"),
    disable_wolf: bool = Form(False)
):
    global players
    if not players:
        return RedirectResponse(url="/admin", status_code=303)

    # 1. 全員のステータス初期化＆デフォルト役職の設定
    for p in players:
        p["status"] = "逃走中"
        p["role"] = "逃走者"
        p["team"] = "未所属"

    # 順番をランダム化
    random.shuffle(players)

    # 2. 鬼の割り当て
    for p in players[:oni_count]:
        p["role"] = "鬼"
        p["team"] = "鬼"

    # 3. 逃走者チーム＆人狼の割り当て
    remaining = players[oni_count:]
    sizes = [int(s.strip()) for s in camp_sizes.split(",") if s.strip().isdigit()]
    team_names = ["A", "B", "C", "D"]

    for i, size in enumerate(sizes):
        if i >= len(team_names) or not remaining:
            break

        team_members = remaining[:size]
        remaining = remaining[size:]

        if team_members:
            team_label = f"{team_names[i]}チーム"

            if disable_wolf:
                # 人狼OFF：チーム全員を「逃走者」にする
                for p in team_members:
                    p["role"] = "逃走者"
                    p["team"] = team_label
            else:
                # 人狼ON：先頭の1人を「人狼」、残りを「逃走者」にする
                werewolf = team_members.pop(0)
                werewolf["role"] = "人狼"
                werewolf["team"] = team_label

                for p in team_members:
                    p["role"] = "逃走者"
                    p["team"] = team_label

    return RedirectResponse(url="/admin", status_code=303)


# 🗑️ 参加者全員リセット処理
@app.post("/admin/reset_players")
def reset_players():
    global players
    players = []  # 参加者リストを空にする
    return RedirectResponse(url="/admin", status_code=303)


# ❌ 参加者の個別削除処理（必要な場合）
@app.post("/admin/delete_player/{player_name}")
def delete_player(player_name: str):
    global players
    players = [p for p in players if p.get("name") != player_name]
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
import os
import requests
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# LINE Botアクセストークン
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_LINE_ACCESS_TOKEN")

# --------------------------------------------------
# グローバル状態管理
# --------------------------------------------------
view_mode = "conductor"  # "conductor" (車掌モード) または "driver" (運転士モード)
players = []             # 参加者データリスト

# 案内メッセージテンプレート（複数管理）
announcements = [
    {"id": 1, "title": "集合案内", "text": "【連絡】本日の集合場所および注意事項です..."},
    {"id": 2, "title": "ゲーム開始", "text": "🚨 これより逃走中ゲームを開始します！"},
]

# ゲーム日程
game_schedule = {
    "date": "2026-10-15",
    "start_time": "10:00",
    "end_time": "16:00",
    "location": "都営地下鉄全線"
}

# --------------------------------------------------
# 管理画面表示 (GET)
# --------------------------------------------------
@app.get("/admin")
def get_admin(request: Request):
    # 運転士モードの場合は「人狼」の役職を「逃走者」に偽装してテンプレートへ渡す
    display_players = []
    for p in players:
        p_copy = dict(p)
        if view_mode == "driver" and p_copy.get("role") == "人狼":
            p_copy["role"] = "逃走者"
        display_players.append(p_copy)

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "players": display_players,
        "view_mode": view_mode,
        "announcements": announcements,
        "game_schedule": game_schedule
    })

# --------------------------------------------------
# 🎛️ 機能1: 車掌モード / 運転士モード 切り替え (POST)
# --------------------------------------------------
@app.post("/admin/set_mode")
def set_mode(mode: str = Form(...)):
    global view_mode
    view_mode = mode
    return RedirectResponse(url="/admin", status_code=303)

# --------------------------------------------------
# 📢 機能2: メニュー案内テンプレート管理 & LINE送信 (POST)
# --------------------------------------------------
@app.post("/admin/add_announcement")
def add_announcement(title: str = Form(...), text: str = Form(...)):
    global announcements
    new_id = max([a["id"] for a in announcements], default=0) + 1
    announcements.append({"id": new_id, "title": title, "text": text})
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/delete_announcement/{item_id}")
def delete_announcement(item_id: int):
    global announcements
    announcements = [a for a in announcements if a["id"] != item_id]
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/send_announcement/{item_id}")
def send_announcement(item_id: int):
    target = next((a for a in announcements if a["id"] == item_id), None)
    if target and LINE_CHANNEL_ACCESS_TOKEN != "YOUR_LINE_ACCESS_TOKEN":
        url = "https://api.line.me/v2/bot/message/broadcast"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
        }
        payload = {
            "messages": [{"type": "text", "text": target["text"]}]
        }
        requests.post(url, json=payload, headers=headers)
    return RedirectResponse(url="/admin", status_code=303)

# --------------------------------------------------
# 📅 機能3: ゲーム日程の更新 (POST)
# --------------------------------------------------
@app.post("/admin/update_schedule")
def update_schedule(
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    location: str = Form(...)
):
    global game_schedule
    game_schedule = {
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "location": location
    }
    return RedirectResponse(url="/admin", status_code=303)