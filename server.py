import asyncio
import json
import os
from pathlib import Path
BASE = Path(__file__).resolve().parent
import random
import secrets
from aiohttp import web, WSMsgType

MAX_PLAYERS = 4
COLORS = ['red', 'blue', 'green', 'yellow']
rooms = {}
clients = {}

def deck():
    d = []
    for color in COLORS:
        d.append({'color': color, 'value': '0'})
        for v in [str(i) for i in range(1,10)] + ['skip','reverse','+2','trap','swap','chaos']:
            d.extend([{'color': color, 'value': v} for _ in range(1 if v in ('trap','swap','chaos') else 2)])
    for v in ['wild','+4']:
        d.extend([{'color': 'wild', 'value': v} for _ in range(4)])
    random.shuffle(d)
    return d

POINT_VALUES = {'skip':20, 'reverse':20, '+2':20, 'trap':30, 'swap':40, 'chaos':40, 'wild':50, '+4':50}

def card_points(card):
    return POINT_VALUES.get(card['value'], int(card['value']) if card['value'].isdigit() else 0)

def finish_round(r, winner):
    # A round awards the winner the total value of all opponents' remaining cards.
    gained = sum(card_points(c) for p in r['players'] if p['id'] != winner['id'] for c in p['hand'])
    winner['score'] = winner.get('score', 0) + gained
    winner['wins'] = winner.get('wins', 0) + 1
    r['round'] = r.get('round', 0) + 1
    r['last_gain'] = gained
    r['last_breakdown'] = [dict(id=p['id'], name=p['name'], points=sum(card_points(c) for c in p['hand'])) for p in r['players'] if p['id'] != winner['id']]
    r['winner_id'] = winner['id']
    r['winner'] = winner['name']
    r['started'] = False
    r['message'] = f"🏆 {winner['name']} remporte la manche et gagne {gained} points !"

def player_view(p):
    return {'id': p['id'], 'name': p['name'], 'count': len(p['hand']), 'bot': p.get('bot', False), 'score': p.get('score', 0), 'wins': p.get('wins', 0)}

def view(room, pid):
    p = next((p for p in room['players'] if p['id'] == pid), None)
    return {'type': 'state', 'code': room['code'], 'public': room['public'], 'host': room['host'],
            'started': room['started'], 'players': [player_view(x) for x in room['players']],
            'hand': p['hand'] if p else [], 'you': pid, 'turn': room['players'][room['turn']]['id'] if room['started'] and room['players'] else None,
            'top': room['top'], 'color': room['color'], 'direction': room['direction'],
            'winner': room['winner'], 'winner_id': room.get('winner_id'), 'round': room.get('round', 0), 'last_gain': room.get('last_gain', 0), 'last_breakdown': room.get('last_breakdown', []), 'message': room['message'], 'drawn': room['drawn'],
            'uno': room['uno'], 'effect_event': room.get('effect_event'), 'traps': [{'owner': t['owner'], 'target': t['target']} for t in room.get('traps', [])]}

async def send(ws, data):
    if ws and not ws.closed:
        try:
            await ws.send_json(data)
        except (ConnectionError, RuntimeError):
            pass

async def broadcast(room):
    for p in list(room['players']):
        await send(clients.get(p['id']), view(room, p['id']))
    await lobby()

async def lobby():
    listing = [{'code': r['code'], 'players': len(r['players']), 'started': r['started']} for r in rooms.values() if r['public'] and len(r['players']) < MAX_PLAYERS and not r['started']]
    for ws in list(clients.values()):
        await send(ws, {'type': 'lobby', 'rooms': listing})

def next_turn(r, steps=1):
    r['turn'] = (r['turn'] + r['direction'] * steps) % len(r['players'])
    r['drawn'] = False
    r['uno'] = False
    activate_traps(r)

def draw(r, p, n):
    for _ in range(n):
        if not r['deck']:
            if len(r['discard']) <= 1:
                break
            saved = r['discard'][-1]
            r['deck'] = r['discard'][:-1]
            random.shuffle(r['deck'])
            r['discard'] = [saved]
        p['hand'].append(r['deck'].pop())

def start(r):
    r['deck'] = deck()
    r['discard'] = []
    for p in r['players']:
        p['hand'] = []
        draw(r, p, 7)
    while True:
        card = r['deck'].pop()
        if card['color'] != 'wild' and card['value'] not in ('+2','reverse','skip'):
            break
        r['deck'].insert(0, card)
    r['top'] = card
    r['discard'] = [card]
    r['color'] = card['color']
    r['started'] = True
    r['winner'] = None
    r['winner_id'] = None
    r['turn'] = 0
    r['direction'] = 1
    r['drawn'] = False
    r['uno'] = False
    r['message'] = 'La partie commence !'
    r['traps'] = []
    r['effect_event'] = None

def record_effect(r, player, card, target_id=None):
    value = card['value']
    if value not in ('trap', 'swap', 'chaos', 'skip', 'reverse', '+2', '+4'):
        return
    r['effect_seq'] = r.get('effect_seq', 0) + 1
    target = next((x for x in r['players'] if x['id'] == target_id), None)
    r['effect_event'] = {'id': r['effect_seq'], 'value': value,
                         'actor': player['name'], 'target': target['name'] if target else ''}

def apply_effect(r, p, card, target_id=None):
    """Apply custom card effects after the played card is removed from the hand."""
    value = card['value']
    if value == 'trap':
        target = r['players'][(r['turn'] + r['direction']) % len(r['players'])]
        r['traps'].append({'owner': p['id'], 'target': target['id']})
        r['message'] += ' 🪤 Un piège attend ' + target['name'] + ' !'
    elif value == 'swap':
        candidates = [x for x in r['players'] if x['id'] != p['id']]
        target = next((x for x in candidates if x['id'] == target_id), None)
        if target is None:
            target = max(candidates, key=lambda x: len(x['hand']))
        p['hand'], target['hand'] = target['hand'], p['hand']
        r['message'] += ' 🔁 ' + p['name'] + ' échange sa main avec ' + target['name'] + ' !'
    elif value == 'chaos':
        hands = [x['hand'] for x in r['players']]
        # Each player receives the hand of the previous player in seating order.
        for i, x in enumerate(r['players']):
            x['hand'] = hands[(i-1) % len(hands)]
        r['message'] += ' 🌪️ Toutes les mains tournent !'

def activate_traps(r):
    if not r['started']:
        return
    p = r['players'][r['turn']]
    active = [t for t in r['traps'] if t['target'] == p['id']]
    if active:
        r['traps'] = [t for t in r['traps'] if t['target'] != p['id']]
        draw(r, p, 2 * len(active))
        r['message'] += f' 🪤 {p["name"]} tombe dans {len(active)} piège(s) : +{2 * len(active)} cartes !'

def add_bot(r):
    if r['started'] or len(r['players']) >= MAX_PLAYERS:
        raise ValueError('Salon complet : 4 joueurs maximum.')
    num = 1 + sum(bool(p.get('bot')) for p in r['players'])
    r['players'].append({'id': 'bot-' + secrets.token_hex(5), 'name': f'Robot {num}', 'hand': [], 'bot': True, 'score': 0, 'wins': 0})

async def bot_loop(r):
    # Une seule boucle par salon ; jamais de carte envoyée aux autres joueurs.
    if r.get('bot_running'):
        return
    r['bot_running'] = True
    try:
        while r['started'] and r['players'] and r['players'][r['turn']].get('bot'):
            await asyncio.sleep(0.85)
            if not r['started'] or not r['players'] or not r['players'][r['turn']].get('bot'):
                break
            p = r['players'][r['turn']]
            playable = [(i,c) for i,c in enumerate(p['hand']) if valid(c, r, p['hand'])]
            if not playable:
                draw(r, p, 1)
                playable = [(i,c) for i,c in enumerate(p['hand']) if valid(c, r, p['hand'])]
            if not playable:
                r['message'] = p['name'] + ' passe son tour.'
                next_turn(r)
                await broadcast(r)
                continue
            i, card = playable[0]
            p['hand'].pop(i)
            r['discard'].append(card)
            r['top'] = card
            if card['color'] == 'wild':
                remaining = [c['color'] for c in p['hand'] if c['color'] in COLORS]
                r['color'] = max(COLORS, key=remaining.count) if remaining else random.choice(COLORS)
            else:
                r['color'] = card['color']
            r['message'] = p['name'] + ' joue ' + card['value'] + '.'
            record_effect(r, p, card)
            apply_effect(r, p, card)
            if not p['hand']:
                finish_round(r, p)
            else:
                steps = 1
                if card['value'] == 'reverse':
                    r['direction'] *= -1
                    if len(r['players']) == 2:
                        steps = 2
                elif card['value'] == 'skip':
                    steps = 2
                elif card['value'] in ('+2', '+4'):
                    target = r['players'][(r['turn'] + r['direction']) % len(r['players'])]
                    draw(r, target, 2 if card['value'] == '+2' else 4)
                    steps = 2
                next_turn(r, steps)
            await broadcast(r)
    finally:
        r['bot_running'] = False

def trigger_bots(r):
    if r['started'] and r['players'] and r['players'][r['turn']].get('bot'):
        asyncio.create_task(bot_loop(r))

def valid(card, r, hand):
    if card['value'] == '+4':
        return not any(c['color'] == r['color'] for c in hand if c is not card)
    return card['color'] == 'wild' or card['color'] == r['color'] or card['value'] == r['top']['value']

async def remove(pid):
    clients.pop(pid, None)
    for code, r in list(rooms.items()):
        index = next((i for i,p in enumerate(r['players']) if p['id'] == pid), None)
        if index is None:
            continue
        r['players'].pop(index)
        if not any(not p.get('bot') for p in r['players']):
            del rooms[code]
            break
        if not r['players']:
            del rooms[code]
            break
        if r['host'] == pid:
            r['host'] = next(p['id'] for p in r['players'] if not p.get('bot'))
        if r['started']:
            if len(r['players']) < 2:
                r['started'] = False
                r['winner'] = None
            else:
                if index < r['turn']:
                    r['turn'] -= 1
                elif index == r['turn']:
                    r['turn'] %= len(r['players'])
                r['drawn'] = False
                r['uno'] = False
        r['message'] = 'Un joueur a quitté la partie.'
        await broadcast(r)
        trigger_bots(r)
        break
    await lobby()

async def websocket(request):
    ws = web.WebSocketResponse(heartbeat=25, max_msg_size=4096)
    await ws.prepare(request)
    pid = secrets.token_hex(8)
    clients[pid] = ws
    current = None
    await send(ws, {'type': 'welcome', 'id': pid})
    await lobby()
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
                action = data.get('action')
                if action in ('create','join'):
                    if current:
                        raise ValueError('Quitte d’abord ton salon.')
                    name = str(data.get('name','')).strip()[:20]
                    if not name:
                        raise ValueError('Choisis un pseudo.')
                    if action == 'create':
                        code = secrets.token_hex(3).upper()
                        while code in rooms:
                            code = secrets.token_hex(3).upper()
                        r = {'code': code, 'public': bool(data.get('public')), 'host': pid, 'players': [], 'started': False,
                             'deck': [], 'discard': [], 'top': None, 'color': None, 'turn': 0, 'direction': 1,
                             'winner': None, 'winner_id': None, 'round': 0, 'last_gain': 0, 'last_breakdown': [], 'message': 'En attente de joueurs...', 'drawn': False, 'uno': False, 'traps': []}
                        rooms[code] = r
                    else:
                        code = str(data.get('code','')).strip().upper()
                        r = rooms.get(code)
                        if not r or r['started'] or len(r['players']) >= MAX_PLAYERS:
                            raise ValueError('Salon introuvable, complet ou déjà en partie.')
                    r['players'].append({'id': pid, 'name': name, 'hand': [], 'score': 0, 'wins': 0})
                    current = code
                    await broadcast(r)
                    continue
                if action == 'leave':
                    await remove(pid)
                    clients[pid] = ws
                    current = None
                    await send(ws, {'type': 'left'})
                    await lobby()
                    continue
                if not current or current not in rooms:
                    raise ValueError('Rejoins un salon.')
                r = rooms[current]
                p = next((p for p in r['players'] if p['id'] == pid), None)
                if not p:
                    raise ValueError('Joueur introuvable.')
                if action == 'add_bot':
                    if pid != r['host']:
                        raise ValueError('Seul l’hôte peut ajouter un robot.')
                    add_bot(r)
                elif action == 'start':
                    if pid != r['host'] or len(r['players']) < 2 or r['started']:
                        raise ValueError('Seul l’hôte peut lancer une partie à 2 joueurs minimum.')
                    start(r)
                elif action == 'restart':
                    if pid != r['host'] or len(r['players']) < 2 or r['started']:
                        raise ValueError('Impossible de relancer maintenant.')
                    start(r)
                elif action in ('play','draw','pass','uno'):
                    if not r['started'] or r['players'][r['turn']]['id'] != pid:
                        raise ValueError('Ce n’est pas ton tour.')
                    if action == 'uno':
                        if len(p['hand']) == 2:
                            r['uno'] = True
                            r['message'] = p['name'] + ' annonce UNO !'
                        else:
                            raise ValueError('Annonce UNO avant de jouer ton avant-dernière carte.')
                    elif action == 'draw':
                        if r['drawn']:
                            raise ValueError('Tu as déjà pioché.')
                        draw(r, p, 1)
                        r['drawn'] = True
                        r['message'] = p['name'] + ' pioche une carte.'
                    elif action == 'pass':
                        if not r['drawn']:
                            raise ValueError('Pioche avant de passer.')
                        r['message'] = p['name'] + ' passe son tour.'
                        next_turn(r)
                    else:
                        index = data.get('index')
                        if type(index) is not int or not 0 <= index < len(p['hand']):
                            raise ValueError('Carte invalide.')
                        card = p['hand'][index]
                        if not valid(card, r, p['hand']):
                            raise ValueError('Cette carte ne peut pas être jouée.')
                        chosen = data.get('color')
                        if card['color'] == 'wild' and chosen not in COLORS:
                            raise ValueError('Choisis une couleur.')
                        if card['value'] == 'swap' and data.get('target') not in [x['id'] for x in r['players'] if x['id'] != pid]:
                            raise ValueError('Cible invalide.')
                        p['hand'].pop(index)
                        r['discard'].append(card)
                        r['top'] = card
                        r['color'] = chosen if card['color'] == 'wild' else card['color']
                        r['message'] = p['name'] + ' joue ' + card['value'] + '.'
                        record_effect(r, p, card, data.get('target'))
                        apply_effect(r, p, card, data.get('target'))
                        if len(p['hand']) == 1 and not r['uno']:
                            draw(r, p, 2)
                            r['message'] += ' UNO oublié : +2 cartes !'
                        if not p['hand']:
                            finish_round(r, p)
                        else:
                            steps = 1
                            if card['value'] == 'reverse':
                                r['direction'] *= -1
                                if len(r['players']) == 2:
                                    steps = 2
                            elif card['value'] == 'skip':
                                steps = 2
                            elif card['value'] in ('+2','+4'):
                                target = r['players'][(r['turn'] + r['direction']) % len(r['players'])]
                                draw(r, target, 2 if card['value'] == '+2' else 4)
                                steps = 2
                            next_turn(r, steps)
                else:
                    raise ValueError('Action inconnue.')
                await broadcast(r)
                trigger_bots(r)
            except (ValueError, KeyError, TypeError) as exc:
                await send(ws, {'type': 'error', 'message': str(exc)})
    finally:
        await remove(pid)
    return ws

async def index(request):
    return web.FileResponse(BASE / 'static' / 'index.html')

app = web.Application()
app.router.add_get('/', index)
app.router.add_get('/ws', websocket)
app.router.add_static('/static/', BASE / 'static')
if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8000')))
