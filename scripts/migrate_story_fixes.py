"""Apply narrow, idempotent fixes to an existing Kamaria SQLite database.

Run without --apply for a preview; back up the live database before --apply.
Only the exact legacy values found in the supplied backup are changed.
"""
import argparse
import json
import sqlite3
from pathlib import Path


def migrate(conn):
    changes = {}
    cur = conn.execute(
        "UPDATE story_choices SET next_node_id=? WHERE id=? AND node_id=? AND next_node_id=? "
        "AND EXISTS (SELECT 1 FROM story_nodes WHERE id=?)",
        ('a1_18e_rats', 154, 'a1_18c_mother', 'a1_18d_rats', 'a1_18e_rats'),
    )
    changes['arc1_transition'] = cur.rowcount

    row = conn.execute("SELECT action_data FROM story_choices WHERE id=428 AND node_id='a4_16_drunk'").fetchone()
    if row:
        action = json.loads(row[0])
        if 'take_gold' not in action:
            action['take_gold'] = 10
            conn.execute("UPDATE story_choices SET action_data=? WHERE id=428", (json.dumps(action, ensure_ascii=False),))
            changes['ale_price'] = 1
        else:
            changes['ale_price'] = 0
    row = conn.execute("SELECT extra_data FROM story_nodes WHERE id='a4_17_drunk_clue'").fetchone()
    if row:
        extra = json.loads(row[0])
        if extra.get('take_gold') == 10:
            del extra['take_gold']
            conn.execute("UPDATE story_nodes SET extra_data=? WHERE id='a4_17_drunk_clue'", (json.dumps(extra, ensure_ascii=False),))
            changes['avoid_double_ale_charge'] = 1

    row = conn.execute("SELECT extra_data FROM story_nodes WHERE id='a5_t07'").fetchone()
    if row:
        extra = json.loads(row[0])
        fixed = 0
        for item in extra.get('give_items', []):
            if item.get('id') == 'healing_potion':
                item['id'] = 'health_potion'
                fixed += 1
        if fixed:
            conn.execute("UPDATE story_nodes SET extra_data=? WHERE id='a5_t07'", (json.dumps(extra, ensure_ascii=False),))
        changes['potion_reward'] = fixed

    fixed_users = 0
    for user_id, raw in conn.execute("SELECT user_id, inventory FROM users WHERE inventory LIKE '%healing_potion%'").fetchall():
        inv = json.loads(raw or '{}')
        potions = inv.get('potions', [])
        if 'healing_potion' in potions:
            inv['potions'] = ['health_potion' if p == 'healing_potion' else p for p in potions]
            conn.execute("UPDATE users SET inventory=? WHERE user_id=?", (json.dumps(inv, ensure_ascii=False), user_id))
            fixed_users += 1
    changes['inventories'] = fixed_users
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error('Database does not exist')
    with sqlite3.connect(str(args.database), timeout=10) as conn:
        conn.execute('BEGIN IMMEDIATE')
        changes = migrate(conn)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    print(json.dumps({'applied': args.apply, 'changes': changes}, ensure_ascii=False))


if __name__ == '__main__':
    main()
