"""Offline tests: no Home Assistant or Telegram connections."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch

BUNDLE = Path(__file__).resolve().parents[1] / "compitapp"
spec = importlib.util.spec_from_file_location('ha_telegram_bridge', BUNDLE/'ha_telegram_bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

def event(cmd='/voti', chat=11, args=None):
    return {'event_type':'telegram_command','data':{'command':cmd,'chat_id':chat,'args':[] if args is None else args}}

class BridgeTests(unittest.TestCase):
    def test_commands_and_arguments(self):
        for cmd in ['/voti','/orario','/resoconto']:
            self.assertEqual(bridge.to_update(event(cmd),{11})['message']['text'],cmd)
        self.assertEqual(bridge.to_update(event('/orario',args=['lunedi']),{11})['message']['text'],'/orario lunedi')
    def test_reject_unrelated_or_malformed(self):
        for item in [None,{},[],event('/comando_ha'),event('/clima'),event(chat=22),event(chat=True),event(chat=11.5),event(chat=None),event(args='lunedi'),event(args=[{}])]:
            self.assertIsNone(bridge.to_update(item,{11}))
    def test_sse(self):
        expected=event('/orario',args=['lunedì'])
        frames=[b'data: ping',b'',b'data: broken',b'',('data: '+json.dumps(expected,ensure_ascii=False)).encode(),b'']
        self.assertEqual(list(bridge.sse_events(frames)),[expected])
    def test_parent_ids(self):
        with patch.dict(os.environ,{'TELEGRAM_CHAT_IDS':'11,22,broken'}):
            self.assertEqual(bridge.parent_chat_ids(),{11,22})
    def test_startup_modes(self):
        tree=ast.parse((BUNDLE/'bot.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='avvia_bot')
        calls=[]
        class Thread:
            def __init__(self,**kw): calls.append(kw['target'])
            def start(self): pass
        env={'os':os,'threading':types.SimpleNamespace(Thread=Thread),'TELEGRAM_TOKEN':'synthetic','set_comandi_bot':lambda:calls.append('commands'),'polling_loop':lambda:None,'handle_update':lambda x:None,'print':lambda *args,**kwargs:None}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'startup','exec'),env)
        with patch.dict('sys.modules',{'ha_telegram_bridge':bridge}):
            with patch.dict(os.environ,{'TELEGRAM_RICEZIONE':'home_assistant'}):
                env['avvia_bot']();self.assertEqual(calls,[bridge.run_bridge])
            calls.clear()
            with patch.dict(os.environ,{'TELEGRAM_RICEZIONE':'polling'}):
                env['avvia_bot']();self.assertEqual(calls,['commands',env['polling_loop']])
            calls.clear()
            with patch.dict(os.environ,{'TELEGRAM_RICEZIONE':'invalid'}):
                env['avvia_bot']();self.assertEqual(calls,[])
    def check_stream(self, headers, status=200, expected=1):
        class StopTest(BaseException): pass
        class Response:
            status_code=status
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def raise_for_status(self): pass
            def iter_lines(self,**kw):
                for item in [event('/comando_ha'),event(chat=22),event('/orario',args=['lunedi'])]:
                    yield ('data: '+json.dumps(item)).encode();yield b''
        Response.headers=headers
        received=[]
        with patch.dict(os.environ,{'SUPERVISOR_TOKEN':'synthetic','TELEGRAM_CHAT_IDS':'11'}), patch.object(bridge.requests,'get',return_value=Response()) as get, patch.object(bridge.time,'sleep',side_effect=StopTest):
            with self.assertRaises(StopTest): bridge.run_bridge(received.append)
        self.assertEqual(len(received),expected)
        if expected:
            self.assertEqual(received[0]['message']['text'],'/orario lunedi')
        self.assertEqual(get.call_args.args,(bridge.STREAM_URL,))
        self.assertEqual(get.call_args.kwargs['params'],{'restrict':'telegram_command'})
    def test_stream_connection_dispatch(self):
        for headers in [{'Content-Type':'text/event-stream'}, {'Content-Type':'text/event-stream; charset=utf-8'}, {'Content-Type':''}, {}]:
            with self.subTest(headers=headers): self.check_stream(headers)
    def test_reject_explicit_wrong_content_type_or_status(self):
        self.check_stream({'Content-Type':'application/json'},expected=0)
        self.check_stream({},status=404,expected=0)
        self.check_stream({},status=204,expected=0)

class BackwardsCompatibilityTests(unittest.TestCase):
    def test_polling_is_default(self):
        tree=ast.parse((BUNDLE/'bot.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='avvia_bot')
        calls=[]
        class Thread:
            def __init__(self,**kw): calls.append(kw['target'])
            def start(self): pass
        env={'os':os,'threading':types.SimpleNamespace(Thread=Thread),'TELEGRAM_TOKEN':'synthetic','set_comandi_bot':lambda:calls.append('commands'),'polling_loop':lambda:None,'handle_update':lambda x:None,'print':lambda *args,**kwargs:None}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'startup','exec'),env)
        with patch.dict(os.environ,{},clear=True): env['avvia_bot']()
        self.assertEqual(calls,['commands',env['polling_loop']])

    def test_wsgi_preserves_existing_options_default(self):
        tree=ast.parse((BUNDLE/'wsgi.py').read_text())
        matches=[]
        for node in ast.walk(tree):
            if not isinstance(node,ast.Assign):continue
            for target in node.targets:
                if isinstance(target,ast.Subscript) and isinstance(target.slice,ast.Constant) and target.slice.value=='TELEGRAM_RICEZIONE':matches.append(node)
        self.assertEqual(len(matches),1)
        for cfg,expected in [({},'polling'),({'telegram_ricezione':'polling'},'polling'),({'telegram_ricezione':'home_assistant'},'home_assistant')]:
            with patch.dict(os.environ,{},clear=True):
                exec(compile(ast.Module(body=matches,type_ignores=[]),'wsgi-option','exec'),{'os':os,'cfg':cfg})
                self.assertEqual(os.environ['TELEGRAM_RICEZIONE'],expected)

    def test_no_parents_disables_bridge(self):
        with patch.dict(os.environ,{'TELEGRAM_CHAT_IDS':''}), patch.object(bridge.requests,'get') as get:
            bridge.run_bridge(lambda update:self.fail('Unauthorized dispatch'))
        get.assert_not_called()

    def test_missing_supervisor_token_does_not_poll(self):
        class StopTest(BaseException): pass
        with patch.dict(os.environ,{'TELEGRAM_CHAT_IDS':'11','SUPERVISOR_TOKEN':''}), patch.object(bridge.requests,'get') as get, patch.object(bridge.time,'sleep',side_effect=StopTest):
            with self.assertRaises(StopTest): bridge.run_bridge(lambda update:self.fail('Unexpected dispatch'))
        get.assert_not_called()

if __name__=='__main__': unittest.main()
