import asyncio
import gc
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bot'))
sys.path.insert(0, str(ROOT / 'scripts'))
tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
config = types.ModuleType('config')
config.DB_PATH = os.path.join(tmp.name, 'test.db')
config.BOT_TOKEN = '123456:placeholder'
config.ADMIN_ID = 0
sys.modules['config'] = config

import database
from handlers import collection, dungeon, minigames, story, trading_post
from migrate_story_fixes import migrate


class Message:
    def __init__(self):
        self.text = None
        self.reply_markup = None

    async def edit_text(self, text, **kwargs):
        self.text = text
        self.reply_markup = kwargs.get('reply_markup')


class Callback:
    def __init__(self, data, user_id=111):
        self.data = data
        self.from_user = types.SimpleNamespace(id=user_id)
        self.message = Message()
        self.answers = []

    async def answer(self, *args, **kwargs):
        self.answers.append((args, kwargs))


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        database.seed_all()

    @classmethod
    def tearDownClass(cls):
        gc.collect()

    def setUp(self):
        with database.get_connection() as conn:
            conn.execute('DELETE FROM users WHERE user_id=111')
            conn.execute("INSERT INTO users (user_id,username,state,hp,max_hp,gold,inventory,home_data,story_progress,level) VALUES (111,'tester','STATE_STORY',100,100,0,'{}','{}','{}',1)")
            conn.execute("INSERT OR REPLACE INTO stories VALUES ('test_arc','Test','',0,'test_begin')")
            conn.execute("INSERT OR REPLACE INTO story_chapters VALUES ('test_ch','test_arc','Test')")
            conn.execute("INSERT OR REPLACE INTO story_nodes VALUES ('test_begin','test_ch','text','Begin','{}')")
            conn.execute("INSERT OR REPLACE INTO story_nodes VALUES ('test_end','test_ch','text','End','{}')")
            conn.execute("INSERT OR REPLACE INTO story_choices (id,node_id,text,req_cond,action_data,next_node_id) VALUES (900001,'test_begin','Go','{}',?, 'test_end')", (json.dumps({'give_gold': 100}),))
        database.update_user(111, story_progress={'current_story': 'test_arc', 'active_nodes': {'test_arc': 'test_begin'}, 'flags': {}})

    def test_choice_replay_is_rejected(self):
        cb = Callback('story_choice:900001')
        asyncio.run(story.handle_story_choice(cb))
        asyncio.run(story.handle_story_choice(cb))
        user = database.get_user(111)
        self.assertEqual(user['gold'], 100)
        self.assertEqual(user['story_progress']['active_nodes']['test_arc'], 'test_end')
        self.assertTrue(cb.answers)

    def test_gold_requirements_and_cost(self):
        user = database.get_user(111)
        self.assertTrue(story._requirements_error(user, {'req_gold': 50, 'req_level': 1}))
        self.assertFalse(story._apply_effects(user, {'take_gold': 50}))
        user['gold'] = 50
        self.assertFalse(story._requirements_error(user, {'req_gold': 50, 'req_level': 1}))
        self.assertTrue(story._apply_effects(user, {'take_gold': 50}))
        self.assertEqual(user['gold'], 0)

    def test_text_effects_are_applied_once(self):
        with database.get_connection() as conn:
            conn.execute("UPDATE story_nodes SET extra_data=? WHERE id='test_begin'", (json.dumps({'set_flag': 'clue', 'take_hp': 10, 'give_gold': 5}),))
        cb = Callback('test')
        asyncio.run(story.render_story_node(cb, database.get_user(111), 'test_begin'))
        asyncio.run(story.render_story_node(cb, database.get_user(111), 'test_begin'))
        user = database.get_user(111)
        self.assertTrue(user['story_progress']['flags']['clue'])
        self.assertEqual((user['hp'], user['gold']), (90, 5))

    def test_story_render_uses_latest_saved_health(self):
        stale_user = database.get_user(111)
        database.update_user(111, hp=10)
        stale_user['hp'] = -5
        asyncio.run(story.render_story_node(Callback('test'), stale_user, 'test_begin'))
        self.assertEqual(database.get_user(111)['hp'], 10)

    def test_reward_node_can_show_its_choice(self):
        with database.get_connection() as conn:
            conn.execute("UPDATE story_nodes SET node_type='reward', extra_data=? WHERE id='test_begin'", (json.dumps({'gold': 1}),))
        cb = Callback('test')
        asyncio.run(story.render_story_node(cb, database.get_user(111), 'test_begin'))
        callbacks = [button.callback_data for row in cb.message.reply_markup.inline_keyboard for button in row]
        self.assertIn('story_choice:900001', callbacks)
        self.assertNotIn('story_goto:None', callbacks)

    def test_completed_arc_two_unlocks_flag(self):
        database.update_user(111, story_progress={'completed_stories': ['arc2_ice_prison'], 'active_nodes': {}, 'flags': {}})
        asyncio.run(story.render_story_node(Callback('test'), database.get_user(111), 'test_begin'))
        self.assertTrue(database.get_user(111)['story_progress']['flags']['a2_arc2_complete'])

    def test_finished_lock_does_not_pay_twice(self):
        database.update_user(111, home_data={'lock_code': '123', 'lock_input': '12', 'lock_used': 0, 'lock_active': True}, gold=0)
        cb = Callback('mg_lock_btn_3')
        with patch.object(minigames.random, 'random', return_value=1), patch.object(minigames.random, 'randint', return_value=150), patch.object(minigames, 'roll_card', return_value=None):
            asyncio.run(minigames.lock_input(cb))
            asyncio.run(minigames.lock_input(cb))
        self.assertEqual(database.get_user(111)['gold'], 150)
        self.assertFalse(database.get_user(111)['home_data']['lock_active'])

    def test_dungeon_rejects_invalid_transition(self):
        data = {'current_node': 'a', 'nodes': {'a': {'type': 'empty', 'next': ['b']}, 'b': {'type': 'empty', 'next': []}, 'c': {'type': 'treasure', 'next': []}}}
        database.update_user(111, state='STATE_DUNGEON', dungeon_data=data)
        cb = Callback('dungeon_go_c')
        asyncio.run(dungeon.go_to_node(cb))
        self.assertEqual(database.get_user(111)['dungeon_data']['current_node'], 'a')
        self.assertTrue(cb.answers)

    def test_seed_preserves_existing_story_choices_and_loot(self):
        with database.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO story_nodes VALUES ('node_custom','test_ch','text','Custom','{}')")
            conn.execute("INSERT OR REPLACE INTO story_choices (id,node_id,text,req_cond,action_data,next_node_id) VALUES (900002,'node_custom','Custom','{}','{}','town')")
            conn.execute("INSERT INTO loot_tables (location_id,item_id,chance,min_amount,max_amount) VALUES ('custom','custom',1,1,1)")
        database.seed_all()
        with database.get_connection() as conn:
            self.assertTrue(conn.execute('SELECT 1 FROM story_choices WHERE id=900002').fetchone())
            self.assertTrue(conn.execute("SELECT 1 FROM loot_tables WHERE location_id='custom'").fetchone())

    def test_trade_purchase_is_atomic_and_cannot_repeat(self):
        database.update_user(111, gold=100, inventory={'materials': {'iron_ingot': 1}})
        with database.get_connection() as conn:
            conn.execute('DELETE FROM trading_post WHERE seller_id=111')
            conn.execute('DELETE FROM users WHERE user_id=222')
            conn.execute("INSERT INTO users (user_id,username,state,hp,max_hp,gold,inventory,home_data,level) VALUES (222,'buyer','STATE_TOWN',100,100,1000,'{}','{}',1)")
        trading_post._create_lot(111, 'iron_ingot', 'material', 100)
        with database.get_connection() as conn:
            lot_id = conn.execute('SELECT lot_id FROM trading_post WHERE seller_id=111').fetchone()[0]
        trading_post._buy_lot(lot_id, 222)
        with self.assertRaises(trading_post.TradeError):
            trading_post._buy_lot(lot_id, 222)
        self.assertEqual(database.get_user(222)['gold'], 900)
        self.assertEqual(database.get_user(222)['inventory']['materials']['iron_ingot'], 1)
        self.assertEqual(database.get_user(111)['gold'], 189)

    def test_trade_error_rolls_back_gold_and_lot(self):
        with database.get_connection() as conn:
            conn.execute('DELETE FROM users WHERE user_id=222')
            conn.execute("INSERT INTO users (user_id,username,state,hp,max_hp,gold,inventory,home_data,level) VALUES (222,'buyer','STATE_TOWN',100,100,1000,'{}','{}',1)")
            lot_id = conn.execute("INSERT INTO trading_post (seller_id,item_id,item_type,price) VALUES (111,'bad','unsupported',100)").lastrowid
        with self.assertRaises(trading_post.TradeError):
            trading_post._buy_lot(lot_id, 222)
        self.assertEqual(database.get_user(222)['gold'], 1000)
        self.assertEqual(database.get_user(111)['gold'], 0)
        with database.get_connection() as conn:
            self.assertTrue(conn.execute('SELECT 1 FROM trading_post WHERE lot_id=?', (lot_id,)).fetchone())

    def test_cancel_restores_item_once(self):
        database.update_user(111, gold=100, inventory={'materials': {'iron_ingot': 1}})
        with database.get_connection() as conn:
            conn.execute('DELETE FROM trading_post WHERE seller_id=111')
        trading_post._create_lot(111, 'iron_ingot', 'material', 100)
        with database.get_connection() as conn:
            lot_id = conn.execute('SELECT lot_id FROM trading_post WHERE seller_id=111').fetchone()[0]
        self.assertEqual(trading_post._cancel_lot(lot_id, 111), 1)
        with self.assertRaises(trading_post.TradeError):
            trading_post._cancel_lot(lot_id, 111)
        self.assertEqual(database.get_user(111)['gold'], 98)
        self.assertEqual(database.get_user(111)['inventory']['materials']['iron_ingot'], 1)

    def test_box_open_and_failure_are_atomic(self):
        with database.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO loot_boxes VALUES ('test_box','Test','mats','common',?,0,0)", (json.dumps({'gold': 50, 'count': 1}),))
            conn.execute("INSERT OR REPLACE INTO user_boxes VALUES (111,'test_box',1)")
        with patch.object(collection.random, 'choices', side_effect=RuntimeError('simulated failure')):
            with self.assertRaises(RuntimeError):
                collection._open_box(111, 'test_box')
        self.assertEqual(collection.get_user_boxes_dict(111)['test_box'], 1)
        self.assertEqual(database.get_user(111)['gold'], 0)
        collection._open_box(111, 'test_box')
        self.assertEqual(database.get_user(111)['gold'], 50)
        self.assertNotIn('test_box', collection.get_user_boxes_dict(111))
        with self.assertRaises(ValueError):
            collection._open_box(111, 'test_box')


class MigrationTests(unittest.TestCase):
    def test_migration_is_idempotent(self):
        conn = sqlite3.connect(':memory:')
        conn.executescript('''CREATE TABLE story_choices(id INTEGER,node_id TEXT,next_node_id TEXT,action_data TEXT);
        CREATE TABLE story_nodes(id TEXT,extra_data TEXT); CREATE TABLE users(user_id INTEGER,inventory TEXT);
        INSERT INTO story_nodes VALUES('a1_18e_rats','{}');
        INSERT INTO story_nodes VALUES('a4_17_drunk_clue','{"take_gold":10,"set_flag":"clue"}');
        INSERT INTO story_nodes VALUES('a5_t07','{"give_items":[{"id":"healing_potion"}]}');
        INSERT INTO story_choices VALUES(154,'a1_18c_mother','a1_18d_rats','{}');
        INSERT INTO story_choices VALUES(428,'a4_16_drunk','next','{}');
        INSERT INTO users VALUES(1,'{"potions":["healing_potion"]}');''')
        first = migrate(conn)
        second = migrate(conn)
        self.assertEqual(first['arc1_transition'], 1)
        self.assertEqual(first['inventories'], 1)
        self.assertFalse(any(second.values()))
        self.assertEqual(conn.execute('SELECT next_node_id FROM story_choices WHERE id=154').fetchone()[0], 'a1_18e_rats')


if __name__ == '__main__':
    unittest.main()
