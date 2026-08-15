# -*- coding: utf-8 -*-
"""
ui_server.py —— UI服务器
==================================================
提供Web界面和API接口
==================================================
"""
import sys
import os
import json
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import datetime

PROJ = r"D:\致敬传奇AI项目"
sys.path.insert(0, PROJ)
os.chdir(PROJ)

# 存储模拟数据
simulation_data = {
    "time": "等待开始...",
    "agents": {}
}

# 角色配置
AGENTS_CONFIG = [
    {"name": "陈子墨", "color": "#00d2ff", "avatar": "墨", "location": "教学楼-高二(3)班"},
    {"name": "林阳", "color": "#51cf66", "avatar": "阳", "location": "操场"},
    {"name": "王浩宇", "color": "#ffd43b", "avatar": "宇", "location": "宿舍楼-302寝室"},
    {"name": "赵天磊", "color": "#cc5de8", "avatar": "磊", "location": "图书馆"},
    {"name": "孙一凡", "color": "#339af0", "avatar": "凡", "location": "食堂"},
    {"name": "周景行", "color": "#ff6b6b", "avatar": "行", "location": "教学楼-高二(3)班"},
]

# 初始化角色数据
for agent in AGENTS_CONFIG:
    simulation_data["agents"][agent["name"]] = {
        **agent,
        "emotion": "平静",
        "activity": "等待中",
        "currentAction": "",
        "nextPlan": "",
        "thinking": [],
        "memory": [],
        "impressions": {}
    }


class RequestHandler(SimpleHTTPRequestHandler):
    """自定义请求处理器"""
    
    def do_GET(self):
        # API接口
        if self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(simulation_data, ensure_ascii=False).encode('utf-8'))
            return
        
        # 默认返回index.html
        if self.path == '/':
            self.path = '/ui/index.html'
        
        return SimpleHTTPRequestHandler.do_GET(self)
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def run_server(port=8080):
    """运行服务器"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"服务器启动在 http://localhost:{port}")
    print(f"打开浏览器访问: http://localhost:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
