import socket
from flask import Flask, render_template, request, jsonify
import threading
import time


HOST = '127.0.0.1'  # 或 Server 的 IP
PORT = 65432

remsg="✅ 遊戲結束，收到正解"
messages=[]

app = Flask(__name__,template_folder='htmlfile',static_folder='font')

@app.route('/')#設置主頁為cli.html
def cli():
    return render_template('cli.html')


s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))
s.send(("玩家已連線\n").encode())
print("✅ 已連線到主持人")

@app.route('/getmsg', methods=['POST'])
def getmsg():
    data=request.get_json()
    msg = data.get("getm", "")
    s.send(msg.encode())
    messages.append("玩家提問: "+msg)
    return jsonify({"message":"send msg" })

@app.route('/messages')
def get_messages():
    return jsonify({"messages": messages})

def msg():
    while True:
        try:
            data = s.recv(1024).decode()
            messages.append(data)
            if not data:
                print("❌ 主持人已離線")
                break
            if "真正的故事👻" in data:
                s.send(remsg.encode())
                messages.append(remsg)
                time.sleep(3)
                s.shutdown(socket.SHUT_RDWR)
                s.close()
        except Exception as e:
            print(f"❌ 連線錯誤：{e}")
            break

if __name__ == '__main__':
    threading.Thread(target=msg, daemon=True).start()
    app.run(port=5573)
