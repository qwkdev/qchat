import os
from flask import Flask, request, abort
import requests as rq
import hashlib
import io
from copy import deepcopy as dc
import json
import time
import re
from datetime import datetime
from flask_cors import CORS
from pathlib import Path
from zoneinfo import ZoneInfo

cwd = Path(__file__).parent.resolve()

app = Flask("qChat", template_folder=cwd / "templates", static_folder=cwd / "static")
CORS(app)
app.secret_key = "example"  # os.getenv('app')

MAX_CHATS = 100

#####


@app.route("/")
def landing():
    return "<h1>hello world</h1>"


def getip(request):
    try:
        if request.headers.getlist("X-Forwarded-For"):
            return request.headers.getlist("X-Forwarded-For")[0]
        elif request.headers.get("X-Real-IP"):
            return request.headers.get("X-Real-IP")
        return request.remote_addr
    except:
        return "???"


@app.route("/ping")
def ping():
    return {"success": True}


@app.route("/ip")
def jsonip():
    return {"success": True, "ip": getip(request)}


def epoch() -> int:
    return int(time.time())
def isotime(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, ZoneInfo('Europe/London')).isoformat()

def safeText(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9\s_-]', '', text)

# User: qwk, @qwk, ^qwk, [qwk]
# Channel: ~main, &main, #main

def parseUser(user: str) -> tuple[int, str]:
    if user.startswith('@'): return 1, safeText(user[1:])
    elif user.startswith('^'): return 2, safeText(user[1:])
    elif user.startswith('[') and user.endswith(']'):
        return 3, safeText(user[1:-1])
    return 0, safeText(user)

users = {
    'qwk': ['password', 3]
}
channels = {
    'main': {
        'read': 0,
        'write': 0,
        'filter': True,
        'chat': [
            [0, 0, 0, '', '- Start of chat'],
            [1, 1759715003, 0, '', 'hello world'],
            [2, 1759715006, 0, '', 'bye world']
        ]
    },
    'x': {
        'read': 2,
        'write': 2,
        'filter': True,
        'chat': [
            [0, 0, 0, '', '- Start of chat'],
            [1, 1759715003, 0, '', 'hello world'],
            [2, 1759715006, 0, '', 'bye world']
        ]
    },
    'push': {
        'read': 0,
        'write': 3,
        'filter': False,
        'chat': [
            [0, 0, 0, '', '- Start of chat']
        ]
    }
}

#! TODO: Create channel (L2+) - [0, 0, 0, '', '- Start of chat']

@app.route("/get/<path:c>")
def get_messages(c):
    data = request.get_json()

    level, user = parseUser(data.get('user', ''))
    if level > 0:
        if user in users and data.get('auth') == users[user][0]:
            level = users[user][1]
        else:
            return {'success': False, 'error': 'Invalid Auth'}

    if c not in channels:
        return {'success': False, 'error': 'Invalid Channel'}
    if channels[c]['read'] > level:
        return {'success': False, 'error': 'Access Denied'}

    if (after := int(request.args.get('after', 0))):
        return {'success': True, 'chat': [i for i in channels[c]['chat'] if i[0] > after]}

    return {'success': True, 'chat': channels[c]['chat']}

@app.route("/msg/<path:c>")
def send_message(c):
    data = request.get_json()

    if not data.get('msg'): return {'success': False}

    level, user = parseUser(data.get('user', ''))
    if level > 0:
        if user in users and data.get('auth') == users[user][0]:
            level = users[user][1]
        else:
            return {'success': False, 'error': 'Invalid Auth'}

    if c not in channels:
        return {'success': False, 'error': 'Invalid Channel'}
    if channels[c]['write'] > level:
        return {'success': False, 'error': 'Access Denied'}
    
    channels[c]['chat'].append([channels[c]['chat'][-1][0]+1, epoch(), level, user, data.get('msg')])
    channels[c]['chat'] = channels[c]['chat'][-MAX_CHATS:]
    
    return {'success': True}


app.run(debug=True)
