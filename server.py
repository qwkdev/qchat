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

app = Flask('qChat', template_folder=cwd / 'templates', static_folder=cwd / 'static')
CORS(app)
app.secret_key = 'example'  # os.getenv('app')

MAX_CHATS = 100

#####


@app.route('/')
def landing():
    return '<h1>hello world</h1>'


def getip(request):
    try:
        if request.headers.getlist('X-Forwarded-For'):
            return request.headers.getlist('X-Forwarded-For')[0]
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        return request.remote_addr
    except:
        return '???'


@app.route('/ping')
def ping():
    return {'success': True}


@app.route('/ip')
def jsonip():
    return {'success': True, 'ip': getip(request)}


def epoch() -> int:
    return int(time.time())
def isotime(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, ZoneInfo('Europe/London')).isoformat()

def safeText(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9\s_-]', '', text)

# User: qwk, @qwk, ^qwk, [qwk]
def parseUser(user: str) -> tuple[int, str]:
    if user.startswith('@'): return 1, safeText(user[1:])
    elif user.startswith('^'): return 2, safeText(user[1:])
    elif user.startswith('[') and user.endswith(']'):
        return 3, safeText(user[1:-1])
    return 0, safeText(user)

# Channel: ~main, &main, #main
def parseChannel(c: str) -> tuple[int, str]:
    if c.startswith('~'): return 0, '~'+safeText(c[1:])
    elif c.startswith('&'): return 1, '&'+safeText(c[1:])
    return 2, safeText(c)

users = {
    'qwk': ['password', 3]
}
channels = {
    'main': {
        'level': 2,
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
        'level': 0,
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
        'level': 1,
        'read': 0,
        'write': 3,
        'filter': False,
        'chat': [
            [0, 0, 0, '', '- Start of chat']
        ]
    }
}

@app.route('/channels')
def channel_debug():
    return channels

@app.route('/create/<path:c>')
def make_channel(channel):
    global channels

    cl, c = parseChannel(channel)
    data = request.get_json()

    level, user = parseUser(data.get('user', ''))
    if level > 0:
        if user in users and data.get('auth') == users[user][0]:
            level = users[user][1]
        else:
            return {'success': False, 'error': 'Invalid Auth'}

    if level < 2:
        return {'success': False, 'error': 'Access Denied'}

    if c in channels:
        return {'success': False, 'error': 'Invalid Channel Name'}
    if (cl + 1) > level:
        return {'success': False, 'error': 'Invalid Channel Level'}
    if (read := request.args.get('read', 0)) > level:
        return {'success': False, 'error': 'Invalid Read Level'}
    if (write := request.args.get('write', 0)) > level:
        return {'success': False, 'error': 'Invalid Write Level'}
    if not (msgfilter := request.args.get('filter', 'true') != 'false') and level != 3:
        return {'success': False, 'error': 'Filter Toggle Denied'}
    
    channels[c] = {
        'level': cl,
        'read': read,
        'write': write,
        'filter': msgfilter,
        'chat': [
            [0, epoch(), 0, '', '- Start of channel'],
        ]
    }
    
    return {'success': True}

@app.route('/get/<path:c>')
def get_messages(channel):
    _, c = parseChannel(channel)
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

@app.route('/msg/<path:c>')
def send_message(channel):
    _, c = parseChannel(channel)
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
