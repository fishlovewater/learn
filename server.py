import socket
import threading
import random
import pymysql
import os
import time
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__, template_folder='htmlfile', static_folder='font')
CORS(app)

HOST = '0.0.0.0'
PORT = 65432

# 升級版的房間字典架構
# rooms = { "房號": { "clients": {}, "messages": [], "story": "", "ans": "", "status": "waiting" } }
rooms = {}

def get_db_connection():
    return pymysql.connect(
        host='127.0.0.1', user='root', password='',
        database='turtle_soup', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def get_random_story():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT story, answer FROM game_stories ORDER BY RAND() LIMIT 1")
            row = cursor.fetchone()
        conn.close()
        if row: return row['story'], row['answer']
    except: pass
    return "暫無題目", "暫無答案"

# ==================== 1. 網頁切換路由 ====================
@app.route('/')
def home(): return render_template('home.html')

@app.route('/cli_page')
def cli_page(): return render_template('cli.html')

@app.route('/submit_page')
def submit_page(): return render_template('submit.html')

# ==================== 2. 核心遊戲與投稿 API ====================

# 【防呆查重】讓投稿頁面渲染現有所有題目
@app.route('/api/get_all_titles', methods=['GET'])
def get_all_titles():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT title, story FROM game_stories")
            rows = cursor.fetchall()
        conn.close()
        return jsonify(rows)
    except:
        return jsonify([])

@app.route('/api/submit', methods=['POST'])
def submit_story():
    data = request.get_json()
    title = data.get("title")
    story = data.get("story")
    answer = data.get("answer")
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 插入投稿表格
            sql = "INSERT INTO submissions (title, story, answer) VALUES (%s, %s, %s)"
            cursor.execute(sql, (title, story, answer))
            # 💡 為了方便 demo 測試，我們順便也塞進正式題庫，這樣玩家投稿完能立刻在左邊查重看到！
            sql2 = "INSERT INTO game_stories (title, story, answer) VALUES (%s, %s, %s)"
            cursor.execute(sql2, (title, story, answer))
        conn.commit()
        conn.close()
        return jsonify({"message": "投稿成功！已即時存入題庫！"})
    except Exception as e:
        return jsonify({"message": f"寫入失敗: {e}"}), 500

# 建立指定房號的房間（多人模式關主觸發）
@app.route('/api/create_specific_room', methods=['POST'])
def create_specific_room():
    data = request.get_json()
    room_id = data.get("room_id")
    story, answer = get_random_story()
    rooms[room_id] = {
        "clients": {},
        "messages": [f"關主已建立房間 {room_id}。等候玩家連線中..."],
        "story": story,
        "ans": answer,
        "status": "waiting"
    }
    return jsonify({"story": story, "answer": answer})

# 用於單人模式臨時撈題
@app.route('/api/create_room', methods=['POST'])
def create_room():
    story, answer = get_random_story()
    return jsonify({"story": story, "answer": answer})

@app.route('/api/start_game', methods=['POST'])
def start_game():
    data = request.get_json()
    room_id = data.get("room_id")
    if room_id in rooms:
        rooms[room_id]["status"] = "playing"
        msg = f"遊戲正式開始！【題目】：{rooms[room_id]['story']}"
        rooms[room_id]["messages"].append(msg)
        for addr, conn in rooms[room_id]["clients"].items():
            try: conn.send((msg + '\n').encode('utf-8'))
            except: pass
        return jsonify({"status": "success"})
    return jsonify({"message": "房間不存在"}), 400

@app.route('/api/get_messages', methods=['GET'])
def get_messages():
    room_id = request.args.get("room_id")
    if room_id not in rooms:
        return jsonify({"status": "closed", "messages": [], "player_count": 0})
    
    # 計算扣除關主自己後，有多少個 Socket 玩家連線
    count = len(rooms[room_id]["clients"])
    return jsonify({
        "status": rooms[room_id]["status"],
        "messages": rooms[room_id]["messages"],
        "player_count": count
    })

@app.route('/api/reply', methods=['POST'])
def handle_reply():
    data = request.get_json()
    room_id = data.get("room_id")
    answer = data.get("reply", "")
    if room_id not in rooms: return jsonify({"message": "房間不存在"}), 400

    reply_msg = f"關主回覆：【{answer}】"
    rooms[room_id]["messages"].append(reply_msg)

    for addr, conn in list(rooms[room_id]["clients"].items()):
        try:
            conn.send((reply_msg + '\n').encode('utf-8'))
            if "回答正確" in answer:
                truth = f"故事真相：{rooms[room_id]['ans']} 遊戲結束！"
                rooms[room_id]["messages"].append(truth)
                conn.send((truth + '\n').encode('utf-8'))
        except: pass
    return jsonify({"message": "已成功廣播回覆"})

# 【功能】關主自訂提示
@app.route('/api/send_hint', methods=['POST'])
def send_hint():
    data = request.get_json()
    room_id = data.get("room_id")
    hint_content = data.get("hint", "")[:30] # 限制30字
    if room_id in rooms:
        hint_msg = f"提示：\"{hint_content}\""
        rooms[room_id]["messages"].append(hint_msg)
        return jsonify({"status": "success"})
    return jsonify({"message": "房間不存在"}), 400

# 【功能】關主下一題重置房間
@app.route('/api/next_round', methods=['POST'])
def next_round():
    data = request.get_json()
    room_id = data.get("room_id")
    if room_id in rooms:
        story, answer = get_random_story()
        rooms[room_id]["story"] = story
        rooms[room_id]["ans"] = answer
        rooms[room_id]["status"] = "waiting"
        rooms[room_id]["messages"] = [f"關主已開啟新的一局！房號為 {room_id}，等待遊戲開始..."]
        return jsonify({"status": "success"})
    return jsonify({"message": "房間不存在"}), 400

# 關主離開，房間不存在，通知所有人
@app.route('/api/close_room', methods=['POST'])
def close_room():
    data = request.get_json()
    room_id = data.get("room_id")
    if room_id in rooms:
        for addr, conn in list(rooms[room_id]["clients"].items()):
            try: conn.close()
            except: pass
        del rooms[room_id]
    return jsonify({"status": "success"})

# AI 關主骨架
@app.route('/api/ai_chat', methods=['POST'])
def ai_chat():
    data = request.get_json()
    player_msg = data.get("msg", "")
    answer_context = data.get("answer", "")
    reply = "與此無關"
    if any(k in player_msg for k in ["死", "殺", "兒", "肉", "水草"]): reply = "🔺 是！"
    elif any(k in player_msg for k in ["餐廳", "游泳"]): reply = "🔺 是，但不重要"
    elif any(k in player_msg for k in ["真相", "正確答案", "是不是兒"]): reply = f"回答正確！揭曉真相：{answer_context}"
    return jsonify({"reply": reply})

# ==================== 3. SOCKET 通訊模組 ====================
def handle_socket_client(conn, addr):
    room_id = None
    with conn:
        try:
            init_data = conn.recv(1024).decode('utf-8').strip()
            if init_data.startswith("JOIN:"):
                room_id = init_data.split(":")[1]
                if room_id in rooms:
                    rooms[room_id]["clients"][addr] = conn
                    # 廣播有人進房了
                    rooms[room_id]["messages"].append(f"👤 有新玩家從 {addr[0]} 加入了房間！")
                else:
                    conn.send("❌ 錯誤：房間不存在！\n".encode('utf-8'))
                    return
            
            while True:
                data = conn.recv(1024).decode('utf-8').strip()
                if not data: break
                if room_id in rooms:
                    rooms[room_id]["messages"].append(data) # 儲存玩家提問
        except: pass
    if room_id in rooms and addr in rooms[room_id]["clients"]:
        del rooms[room_id]["clients"][addr]

def socket_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        while True:
            try:
                conn, addr = s.accept()
                threading.Thread(target=handle_socket_client, args=(conn, addr), daemon=True).start()
            except: pass

if __name__ == '__main__':
    threading.Thread(target=socket_server, daemon=True).start()
    app.run(host='0.0.0.0', port=5678, debug=False, threaded=True)