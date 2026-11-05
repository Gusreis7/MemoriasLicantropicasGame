"""Live HTTP playthroughs with public observations and LLM chosen actions only.

The running application owns time, randomness, inference and rules. Limits stop
an evaluation; they never manufacture a terminal game result.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import time
from urllib.parse import quote

import httpx

ACTIONS = {
    'observe': 'Refresh public observations without mutation.',
    'move': 'Walk to x in current location using real elapsed time.',
    'travel': 'Use map with target_location_id in world.travel_targets.',
    'approach': 'Approach nearby living npc_id and read its conversation.',
    'dialogue': 'Say content to nearby npc_id; travel and walk into reach first.',
    'close_dialogue': 'Close current conversation and release the NPC.',
    'search': 'Search nearby crime_id for one remaining clue.',
    'inspect': 'Inspect collected evidence_id.',
    'present': 'Present collected evidence_id to nearby npc_id.',
    'review': 'Police review of suspect_id, evidence_ids and testimony_ids.',
    'accuse': 'Request detention with suspect_id, evidence_ids and testimony_ids.',
    'open_assembly': 'Nominate suspect_id with evidence_ids, testimony_ids, speech.',
    'resolve_assembly': 'Conclude assembly with reply.',
    'skip_day': 'End day, resolve real night, read next morning paper.',
    'wait': 'Wait seconds (0 to 30) in real time; useful during night.',
}


class ActionRejected(Exception):
    def __init__(self, detail):
        self.detail = detail
        self.code = detail.get('code', 'action_rejected')
        super().__init__(detail.get('code', 'action_rejected'))


def _now():
    return datetime.now(UTC).isoformat()


def _segment(value):
    if not isinstance(value, str) or not value or len(value) > 100:
        raise ValueError('Invalid action identifier')
    return quote(value, safe='')


class LiveSession:
    def __init__(self, api_url: str, agent, output_dir: Path, max_steps: int = 200,
                 max_seconds: float = 1800, request_timeout: float = 120, *,
                 transport: httpx.AsyncBaseTransport | None = None):
        if max_steps < 1 or max_seconds <= 0 or request_timeout <= 0:
            raise ValueError('Session limits must be positive')
        self.api_url, self.agent = api_url.rstrip('/'), agent
        self.output_dir = Path(output_dir)
        self.max_steps, self.max_seconds = max_steps, max_seconds
        self.request_timeout, self.transport = request_timeout, transport
        self.game_id = self.case = self.world = self.conversation = None
        self.conversations, self.recent = {}, []
        self.actions, self.errors = Counter(), []
        self.http_requests = self.http_errors = self.dialogue_turns = 0
        self.latencies = []

    def _event(self, kind, **data):
        with (self.directory / 'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'at': _now(), 'type': kind, **data}, ensure_ascii=False) + '\n')

    def _save(self, report):
        temporary = self.directory / 'session.json.tmp'
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.directory / 'session.json')

    async def _request(self, method, path, body=None):
        self.http_requests += 1
        started = time.monotonic()
        try:
            response = await self.client.request(method, path, json=body) if body is not None else await self.client.request(method, path)
            if response.status_code >= 400:
                self.http_errors += 1
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                detail = {'status': response.status_code, 'code': payload.get('code', 'http_error'),
                          'detail': payload.get('detail', 'Application request failed')}
                self._event('http_error', method=method, path=path, **detail)
                raise ActionRejected(detail)
            result = response.json() if response.status_code != 204 else None
            self._event('http_response', method=method, path=path, status=response.status_code,
                        duration_seconds=time.monotonic() - started, response=result)
            return result
        except httpx.HTTPError as error:
            self.http_errors += 1
            self._event('http_error', method=method, path=path, code=type(error).__name__)
            raise

    @property
    def base(self):
        return f'/api/v1/games/{_segment(self.game_id)}'

    async def _observe(self):
        # Sequential reads avoid competing phase-resolution leases at dawn.
        self.case = await self._request('GET', f'{self.base}/investigation')
        self.world = await self._request('GET', f'{self.base}/world')
        cast = await self._request('GET', self.base)
        reports = await self._request('GET', f'{self.base}/social/reports')
        return {'case': self.case, 'world': self.world, 'cast': cast,
                'locations': self.locations, 'heard_reports': reports,
                'conversations': self.conversations, 'current_conversation': self.conversation,
                'recent_results': self.recent[-12:], 'actions': ACTIONS,
                'remaining_steps': self.max_steps - self.steps,
                'rules': 'Use public information only. Walk within 64px of NPCs and 90px of scenes. Four wolf victims among seven residents end the case. Application alone decides outcomes.'}

    async def _close(self):
        if self.conversation:
            await self._request('POST', f"{self.base}/conversations/{_segment(self.conversation['id'])}/close", {})
            self.conversation = None

    async def _approach(self, npc_id):
        if self.conversation and self.conversation['npc_id'] != npc_id:
            await self._close()
        self.conversation = await self._request('POST', f'{self.base}/approaches', {'npc_id': npc_id})
        return self.conversation

    async def _history(self):
        history = await self._request('GET', f"{self.base}/conversations/{_segment(self.conversation['id'])}/messages?limit=30")
        self.conversations[self.conversation['npc_id']] = history
        return history

    async def _movement_intention(self, direction):
        self.world = await self._request('GET', f'{self.base}/world')
        player = self.world['player']
        self.world = await self._request('POST', f'{self.base}/movement', {
            'direction': direction, 'seq': player['movement_seq'] + 1,
            'location_id': player['location_id'], 'revision': self.world['revision']})
        return self.world

    async def _move(self, target):
        if not isinstance(target, (int, float)) or not math.isfinite(target):
            raise ValueError('move requires finite x')
        target = min(self.world['location']['width'] - 32, max(32, target))
        moving = False
        try:
            for _ in range(80):
                distance = target - self.world['player']['x']
                if abs(distance) <= 5:
                    break
                moving = True
                await self._movement_intention('right' if distance > 0 else 'left')
                await asyncio.sleep(min(.3, max(.025, abs(target - self.world['player']['x']) / 210)))
                await self._movement_intention('idle')
                moving = False
            else:
                raise ValueError('Movement did not reach target')
        finally:
            # Even errors/cancellation attempt a real idle command. Server may
            # reject it if night started; that rejection is logged, not hidden.
            if moving:
                try:
                    await self._movement_intention('idle')
                except (ActionRejected, httpx.HTTPError) as error:
                    self._event('movement_stop_failed', code=type(error).__name__)
        return self.world

    async def _act(self, decision):
        action = decision['action']
        if action not in ACTIONS:
            raise ValueError('Unknown action')
        if action == 'observe':
            return {'observed': True}
        if action == 'wait':
            seconds = decision.get('seconds', 1)
            if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
                raise ValueError('wait requires finite seconds')
            seconds = min(30, max(0, seconds))
            await asyncio.sleep(seconds)
            return {'waited_seconds': seconds}
        if action == 'close_dialogue':
            await self._close()
            return {'closed': True}
        if action == 'move':
            await self._close()
            return await self._move(decision['x'])
        if action == 'travel':
            await self._close()
            return await self._request('POST', f'{self.base}/travel', {
                'target_location_id': decision['target_location_id'], 'revision': self.world['revision']})
        if action in {'approach', 'dialogue'}:
            await self._approach(decision['npc_id'])
            if action == 'approach':
                return await self._history()
            result = await self._request('POST', f"{self.base}/conversations/{_segment(self.conversation['id'])}/messages", {'content': decision['content']})
            self.dialogue_turns += 1
            await self._history()
            return result
        if action == 'search':
            return await self._request('POST', f"{self.base}/crime-scenes/{_segment(decision['crime_id'])}/search", {})
        if action in {'inspect', 'present'}:
            body = {} if action == 'inspect' else {'npc_id': decision['npc_id']}
            return await self._request('POST', f"{self.base}/evidence/{_segment(decision['evidence_id'])}/{action}", body)
        if action == 'skip_day':
            await self._close()
            return await self._request('POST', f'{self.base}/investigation/skip-day', {'day': self.case['day']})
        if action in {'review', 'accuse', 'open_assembly'}:
            await self._close()
            body = {'suspect_id': decision['suspect_id'], 'evidence_ids': decision.get('evidence_ids', []),
                    'testimony_ids': decision.get('testimony_ids', [])}
            suffix = {'review': 'accusations/review', 'accuse': 'accusations', 'open_assembly': 'assembly/open'}[action]
            if action == 'open_assembly':
                body['speech'] = decision.get('speech', '')
            return await self._request('POST', f'{self.base}/{suffix}', body)
        if action == 'resolve_assembly':
            return await self._request('POST', f'{self.base}/assembly/resolve', {'reply': decision.get('reply', '')})
        raise ValueError('Unsupported action')

    async def run(self, index: int) -> dict:
        self.directory = self.output_dir / f'session-{index:04d}'
        self.directory.mkdir(parents=True, exist_ok=False)
        self.steps = 0
        started = time.monotonic()
        baseline = dict(getattr(self.agent, 'stats', {}))
        report = {'index': index, 'game_id': None, 'status': 'running', 'result': None,
                  'started_at': _now(), 'mode': 'live_http', 'stop_reason': None}
        self._save(report)
        try:
            async with httpx.AsyncClient(base_url=self.api_url, timeout=self.request_timeout,
                                         transport=self.transport) as self.client:
                async with asyncio.timeout(self.max_seconds):
                    self.locations = await self._request('GET', '/api/v1/world/locations')
                    created = await self._request('POST', '/api/v1/games', {})
                    self.game_id = str(created['id'])
                    report['game_id'] = self.game_id
                    while True:
                        observation = await self._observe()
                        self._event('observation', step=self.steps, observation=observation)
                        if self.case['status'] != 'active':
                            report.update(status='completed', result=self.case['status'])
                            break
                        if self.steps >= self.max_steps:
                            report.update(status='stopped', stop_reason='step_limit')
                            break
                        decision = await self.agent.decide(observation)
                        self.steps += 1
                        self.actions[decision.get('action', 'invalid')] += 1
                        self._event('decision', step=self.steps, decision=decision)
                        action_started = time.monotonic()
                        try:
                            result = await self._act(decision)
                            entry = {'step': self.steps, 'action': decision['action'], 'result': result}
                        except (ActionRejected, ValueError, KeyError) as error:
                            detail = error.detail if isinstance(error, ActionRejected) else {'code': type(error).__name__}
                            entry = {'step': self.steps, 'action': decision.get('action'), 'error': detail}
                            self.errors.append(entry)
                        duration = time.monotonic() - action_started
                        self.latencies.append(duration)
                        self._event('action_result', duration_seconds=duration, **entry)
                        self.recent.append(entry)
                        self.recent = self.recent[-12:]
                        self._save({**report, 'steps': self.steps, 'duration_seconds': time.monotonic() - started})
                        fatal_code = entry.get('error', {}).get('code')
                        if fatal_code in {'llm_credentials_unavailable', 'llm_credentials_missing', 'llm_authentication_failed'}:
                            report.update(status='error', stop_reason=fatal_code)
                            break
        except TimeoutError:
            report.update(status='stopped', stop_reason='time_limit')
        except asyncio.CancelledError:
            report.update(status='stopped', stop_reason='cancelled')
            raise
        except Exception as error:
            report.update(status='stopped' if type(error).__name__ == 'CallBudgetExceeded' else 'error',
                          stop_reason=getattr(error, 'code', type(error).__name__))
            self._event('session_error', code=report['stop_reason'])
        finally:
            usage = {}
            for key, value in getattr(self.agent, 'stats', {}).items():
                old = baseline.get(key, 0)
                usage[key] = value - old if type(value) in (int, float) and type(old) in (int, float) else value
            report.update(ended_at=_now(), duration_seconds=time.monotonic() - started,
                          day=self.case.get('day') if self.case else None, steps=self.steps,
                          ending=self.case.get('ending') if self.case else None,
                          action_counts=dict(self.actions), http_requests=self.http_requests,
                          http_errors=self.http_errors, action_errors=self.errors,
                          llm_agent_usage=usage, dialogue_turns=self.dialogue_turns,
                          game_llm_usage=None,
                          game_llm_usage_note='Private server usage must be collected separately, never supplied to Floriano.',
                          mean_action_seconds=sum(self.latencies) / len(self.latencies) if self.latencies else 0,
                          final_case=self.case)
            report['stats'] = {key: len(self.case.get(key, [])) for key in
                               ('inventory', 'testimonies', 'accusations', 'achievements', 'crimes')} if self.case else {}
            self._save(report)
            self._event('session_finished', status=report['status'], result=report['result'], stop_reason=report['stop_reason'])
        return report
