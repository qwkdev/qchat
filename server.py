
from flask import Flask, jsonify, make_response, request
from copy import deepcopy as dc
import json
import time
import re
import os
from datetime import datetime
from flask_cors import CORS
from pathlib import Path
from zoneinfo import ZoneInfo
import random
import bcrypt
import emoji
from profanityfilter import ProfanityFilter
pFilter = ProfanityFilter()

cwd = Path(__file__).parent.resolve()

app = Flask('qChat', template_folder=cwd / 'templates', static_folder=cwd / 'static')
CORS(app, supports_credentials=True, origins=[
    'http://127.0.0.1:5500',
    'http://localhost:5500'
])
app.secret_key = 'example'  # os.getenv('app')

AUTH_COOKIE_NAME = 'auth'

MAX_CHATS = 100
MAX_MESSAGE_LENGTH = 256
TOKEN_LENGTH = 64
MAX_NAME_LENGTH = 16

#! TODO: Save channels/users on exit? or every ping or etc
#! TODO: Use MySQL for channel chats?

RNG = random.SystemRandom()

#####

def hash(plain: str) -> str:
    return bcrypt.hashpw(plain, bcrypt.gensalt())
def checkHash(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain, hashed)

def randomStr(n):
    return ''.join([RNG.choice(
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
        'abcdefghijklmnopqrstuvwxyz' +
        '0123456789'
    ) for _ in range(n)])

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
    saveChannels()
    return {'success': True}

@app.route('/ip')
def jsonip():
    return {'success': True, 'ip': getip(request)}

def epoch() -> int:
    return int(time.time())
def isotime(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, ZoneInfo('Europe/London')).isoformat()

def safeText(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '', text)[:MAX_NAME_LENGTH]

def splitPrefix(text: str, prefix: str) -> str:
    return [
        u for n, i in enumerate(text.split(prefix))
        for u in ([i] if n == 0 else [
            prefix+j if m == 0 else j for m, j in enumerate(re.split(r'([^a-zA-Z0-9_-])', i, maxsplit=1))
        ])
    ]

def parseUser(user: str | None) -> tuple[bool, str]:
    if not user: return False, ''
    if user.startswith('@'):
        return True, safeText(user[1:])
    return False, safeText(user)

# Channel: ~main, ^main, #main
def parseChannel(c: str) -> tuple[int, str]:
    if c.startswith('~'): return 0, '~'+safeText(c[1:])
    elif c.startswith('&'): return 1, '&'+safeText(c[1:])
    return 2, safeText(c)

def parseMessage(text: str, filter: bool=True) -> str:
    txt = emoji.emojize(text, language='alias')

    if filter:
        txt = pFilter.censor(txt)

    resp = []
    for part in splitPrefix(txt, '@'):
        if part.startswith('@'): 
            if part[1:].lower() in users:
                resp.append({
                    'type': 'mention',
                    'level': users[part[1:].lower()][2],
                    'value': part
                })
            else:
                resp.append(part)
        else:
            resp.append(part)

    final = []
    for part in resp:
        if isinstance(part, str):
            for temp in re.split(r'(\n)', part):
                if temp == '\n':
                    final.append({'type': 'newline'})
                elif final and isinstance(final[-1], str):
                    final[-1] += temp
                else:
                    final.append(temp)
        else:
            final.append(part)

    return [i for i in final if i]

users = {}
channels = {}

def loadUsers():
    global users

    with open(cwd/'users.json', encoding='utf-8') as f:
        data = json.load(f)
    users = {u: [i[0], None, i[1], i[2]] for u, i in data.items()}
def saveUsers():
    global users

    data = {u: [i[0], i[2], i[3]] for u, i in users.items()}
    with open(cwd/'users.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
def loadChannels():
    global channels

    with open(cwd/'channels.json', encoding='utf-8') as f:
        data = json.load(f)

    channels = {c: {**i, 'chat': [[0, 0, 5, '', ['- Start of channel']]]} for c, i in data.items()}
def saveChannels():
    global channels

    data = {c: {k: v for k, v in i.items() if k != 'messages'} for c, i in channels.items()}
    with open(cwd/'channels.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def password(checkPassword: str, user: str) -> bool:
    return users[user.lower()][0] and checkHash(checkPassword, users[user.lower()][0])
def auth(checkAuth: str, user: str) -> bool:
    return users[user.lower()][1] and checkAuth == users[user.lower()][1]

def token_gen(user: str) -> str:
    global users
    users[user.lower()][1] = randomStr(TOKEN_LENGTH)
    return users[user.lower()][1]

def login(request, min_level: int=0, use_password: bool=False):
    data = request.get_json()
    if not data: return False, {'success': False, 'error': 'Invalid/No JSON'}

    level, user = parseUser(data.get('user', ''))
    if level:
        if use_password:
            if user.lower() in users and password(data.get('password'), user.lower()):
                level = users[user.lower()][2]
            else:
                return {'success': False, 'error': 'Invalid Password'}
        else:
            if user.lower() in users and auth(request.cookies.get(AUTH_COOKIE_NAME), user.lower()):
                level = users[user.lower()][2]
            else:
                return False, {'success': False, 'error': 'Invalid Auth'}
    elif user.lower() in users:
        return False, {'success': False, 'error': 'Username registered'}
    else:
        level = 0

    if level < min_level:
        return False, {'success': False, 'error': 'Access Denied'}
    
    return True, (level, user)

@app.route('/login', methods=['POST'])
def new_session():
    valid, login_resp = login(request, use_password=True)
    if not valid: return login_resp
    level, user = login_resp

    resp = make_response(jsonify({'success': True, 'user': user, 'level': level}))

    if level:
        resp.set_cookie(
            AUTH_COOKIE_NAME,
            token_gen(user.lower()),
            httponly=True,
            secure=True,
            samesite='None',
            path='/'
        )
    
    return resp
    
@app.route('/logout', methods=['POST'])
def remove_sessions():
    data = request.get_json()
    resp = {'success': True}

    level, user = parseUser(data.get('user', ''))
    if level:
        if user.lower() in users and auth(request.cookies.get(AUTH_COOKIE_NAME), user.lower()):
            token_gen(user)
            resp = {'success': True}
        else:
            resp = {'success': False, 'error': 'Invalid Auth'}
    elif user.lower() in users:
        resp = {'success': False, 'error': 'Username registered'}

    final = make_response(jsonify(resp))
    final.set_cookie(AUTH_COOKIE_NAME, '', expires=0)

    return final

@app.route('/get/<path:channel>', methods=['POST'])
def get_messages(channel):
    _, c = parseChannel(channel)

    valid, login_resp = login(request)
    if not valid: return login_resp
    level, _ = login_resp

    if c not in channels:
        return {'success': False, 'error': 'Invalid Channel'}
    if channels[c]['read'] > level:
        return {'success': False, 'error': 'Access Denied'}

    if (after := int(request.args.get('after', 0))):
        return {'success': True, 'chat': [i for i in channels[c]['chat'] if i[0] > after]}

    return {'success': True, 'chat': channels[c]['chat']}

@app.route('/msg/<path:channel>', methods=['POST'])
def send_message(channel):
    global channels

    _, c = parseChannel(channel)
    data = request.get_json()

    if not data.get('msg'): return {'success': False}

    msg = parseMessage(data.get('msg', '')[:MAX_MESSAGE_LENGTH], channels[c].get('filter', True))

    valid, login_resp = login(request)
    if not valid: return login_resp
    level, user = login_resp

    if c not in channels:
        return {'success': False, 'error': 'Invalid Channel'}
    if channels[c]['write'] > level:
        return {'success': False, 'error': 'Access Denied'}
    
    channels[c]['chat'].append([channels[c]['chat'][-1][0]+1, epoch(), level, user, msg])
    channels[c]['chat'] = channels[c]['chat'][-MAX_CHATS:]

    channels[c]['total'] += 1
    if level: users[user.lower()][3] += 1
    
    return {'success': True}

@app.route('/dev/create/<path:channel>', methods=['POST'])
def make_channel(channel):
    global channels

    cl, c = parseChannel(channel)
    data = request.get_json()

    valid, login_resp = login(request, 4)
    if not valid: return login_resp
    level, _ = login_resp

    if c in channels:
        return {'success': False, 'error': 'Invalid Channel Name'}
    if (cl + 1) > level:
        return {'success': False, 'error': 'Invalid Channel Level'}
    if (read := data.get('read', 0)) > level:
        return {'success': False, 'error': 'Invalid Read Level'}
    if (write := data.get('write', 0)) > level:
        return {'success': False, 'error': 'Invalid Write Level'}
    if not (msgfilter := data.get('filter', True)) and level != 3:
        return {'success': False, 'error': 'Filter Toggle Denied'}
    
    channels[c] = {
        'total': 0,
        'level': cl,
        'read': read,
        'write': write,
        'filter': msgfilter,
        'chat': [
            [0, 0, 5, '', ['- Start of channel']],
        ]
    }
    
    return {'success': True}

@app.route('/dev/signup', methods=['POST'])
def signup():
    global users
    data = request.get_json()

    valid, login_resp = login(request, 4)
    if not valid: return login_resp
    
    newUser = data.get('new-user')
    newLevel = int(data.get('level', 0))
    newPassword = data.get('password')

    if not any((newUser, newLevel, newPassword)):
        return {'success': False, 'error': 'Missing params'}
    if newUser.lower() in users:
        return {'success': False, 'error': 'Username registered'}
    if newLevel <= 0 or newLevel >= 4:
        return {'success': False, 'error': 'Invalid level (1-3)'}
    
    users[newUser.lower()] = [hash(newPassword), None, newLevel]

    return {'success': True}

@app.route('/dev/hash')
def dev_hash():
    if not (text := request.args.get('text')): return {'hashed': '', 'text': ''}
    print(text, type(text))
    return {'hashed': hash(text), 'text': text}

@app.route('/dev/stats')
def stats():
    valid, login_resp = login(request, 4)
    if not valid: return login_resp

    return {
        'total': sum([channels[c]['total'] for c in channels]),
        'channels': {c: i['total'] for c, i in channels.items()},
        'users': {u: i[3] for u, i in users.items()}
    }

@app.route('/dev/channels')
def get_channels():
    valid, login_resp = login(request, 4)
    if not valid: return login_resp

    return {c: {k: v for k, v in i.items() if k != 'messages'} for c, i in channels.items()}

@app.route('/dev/edit/<path:channel>')
def dev_edit_channel(channel):
    global channels

    data = request.get_json()
    _, c = parseChannel(channel)

    valid, login_resp = login(request, 4)
    if not valid: return login_resp

    channels[c] |= data.get('edits', {})

loadUsers()
loadChannels()

app.run(debug=True)