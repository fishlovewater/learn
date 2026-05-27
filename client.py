import socket
from flask import Flask, render_template, request, jsonify
import threading
import time

app = Flask(__name__, template_folder='htmlfile', static_folder='font')

# 【重要修改】HOST 改為 0.0.0.0，讓區域網路內的所有設備都能連線
HOST = '0.0.0.0'
PORT = 65432
s = None
messages = []
current_room = None

@app.route('/')
def index():
    return render_template('join.html') # 多人模式玩家點進來，直接進輸入房號頁面

@app.route('/api/connect_room', methods=['POST'])
def connect_room():
    global s, current_room, messages
    data = request.get_json()
    room_id = data.get("room_id")
    # 動態取得發送請求的主機 IP（也就是主持人的 IP）
    server_ip = request.host.split(':')[0] 
    messages = [] 
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((server_ip, PORT)) # 自動連線到主持人的 Socket Server
        s.send(f"JOIN:{room_id}\n".encode('utf-8'))
        current_room = room_id
        
        threading.Thread(target=receive_msg, daemon=True).start()
        return jsonify({"status": "success", "message": f"成功連接到房間 {room_id}"})
    except Exception as e:
        return jsonify({"status": "failed", "message": f"連線失敗: {e}"}), 500

@app.route('/api/send_msg', methods=['POST'])
def send_msg():
    global s
    data = request.get_json()
    msg = data.get("msg", "")
    if s:
        try:
            s.send((msg + '\n').encode('utf-8'))
            return jsonify({"status": "success"})
        except:
            return jsonify({"message": "傳送失敗，與伺服器中斷"}), 500
    return jsonify({"message": "尚未連線到任何房間"}), 400

@app.route('/messages')
def get_messages():
    return jsonify({"messages": messages})

def receive_msg():
    global s, messages
    while True:
        try:
            data = s.recv(1024).decode('utf-8')
            if not data: break
            for line in data.split('\n'):
                if line.strip():
                    messages.append(line.strip())
        except:
            break

if __name__ == '__main__':
    # 讓 client 的 Flask 也監聽 0.0.0.0，這樣別人的電腦也打得開這個網頁
    app.run(host='0.0.0.0', port=5573)