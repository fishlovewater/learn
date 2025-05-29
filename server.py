import socket
import threading
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS#備用
import time

# Socket Server 設定
HOST = '0.0.0.0'#設定為廣播，備用
PORT = 65432
clients = {}  # key: addr, value: socket
messages = []  # 用來儲存提問紀錄
ans=""#用來儲存答案

# Flask 設定
app = Flask(__name__,template_folder='htmlfile',static_folder='font')
#備用
CORS(app)

#設置主頁為home.html
@app.route('/')
def index():
    return render_template('home.html')

@app.route('/ser')
def ser():
    return render_template('s.html')

@app.route('/story')
def story():
    return render_template('story.html')

@app.route('/reply', methods=['POST'])
def handle_reply():
    global ans
    data = request.get_json()#取得html回傳的json格式資料
    answer = data.get("reply", "")#取得資料
    reply_msg = f"主持人回覆：{answer}"
    messages.append(reply_msg)#加到提問紀錄的list

    if not clients:
        return jsonify({"message": "目前沒有連線中的 client"}), 400 #錯誤提示

    for addr, conn in list(clients.items()):#所有client
        try:
            conn.send((reply_msg+ '\n').encode())#把回答傳給所有cilent
            if "回答正確" in answer:
                messages.append(ans)#如果回答正確就把答案加入紀錄的list
                conn.send((ans+ '\n').encode())#把答案傳給client
                time.sleep(3)
                conn.send(("感謝參與，遊戲結束！即將斷線...\n").encode())
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
                del clients[addr]
        except:
            del clients[addr]#刪除client(切斷連線)
    return jsonify({"message": f"已廣播回覆：{answer}"})
    
@app.route('/getst', methods=['POST'])    
def get_story():
    story=request.get_json()
    answer = story.get("storyg", "")
    reply_msg = f"🫕故事：{answer}"
    messages.append(reply_msg)
    if clients:
        for addr, conn in list(clients.items()):
            try:
                conn.send((reply_msg+ '\n').encode())
            except:
                del clients[addr]
        return jsonify({"message": f"已廣播湯底"})
    else:
        return jsonify({"message": "目前沒有連線中的 client"}), 400

@app.route('/ansg',methods=['POST'])
def get_ans():
    global ans
    ans_msg=request.get_json()
    data=ans_msg.get("ans","")
    ans = f"真正的故事👻：{data}，遊戲結束"
    return jsonify({"message": ans})#備用

@app.route('/messages')
def get_messages():
    return jsonify({"messages": messages})

def handle_client(conn, addr):
    print(f"[連線] 玩家已連線：{addr}")
    clients[addr] = conn

    for msg in messages:
        try:
            conn.send((msg + '\n').encode())#傳送之前的log給client
        except:
            continue

    with conn:
        while True:
            try:
                data = conn.recv(1024).decode()#buffer 1024 
                msg = f"[玩家 {addr[0]}] 提問：{data}"
                messages.append(msg)
                if not data:
                    print(f"[斷線] {addr}（未收到資料）")
                    break  
            except:
                break

    print(f"[斷線] {addr}")
    if addr in clients:
        del clients[addr]


def socket_server():
    print("[Socket] 啟動中...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == '__main__':
    threading.Thread(target=socket_server, daemon=True).start()#build a thread run socket_server
    print("[Flask] 開啟主持人網頁介面：http://127.0.0.1:5678")
    app.run(port=5678)#open flask