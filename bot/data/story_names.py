"""Английские названия и тексты сюжетных историй.

Русские тексты живут в БД и остаются fallback-значением. Переводы привязаны
к стабильным ID историй и узлов, поэтому не зависят от порядка вставки строк.
"""

from __future__ import annotations

from i18n import get_language

STORY_TITLES = {
    "test_story_1": "The Dark Alley",
}

NODE_TEXTS = {
    "node_start": "You meet a suspicious elf. His hand drifts toward a dagger.",
    "node_listen": 'The elf wheezes: "I have been poisoned... Do you have a healing potion?"',
    "node_reward": "You have passed the trial! The elf (or his corpse) leaves you a reward.",
    "node_fail": "You were beaten and thrown into a ditch.",
    "node_epilogue": "You turn to leave, but something makes you look back.",
    "node_secret": "In gratitude for saving him, the elf whispers the secret of a hiding place!",
}

# Ключ — (node_id, русский текст из БД). Так перевод не зависит от autoincrement
# id строки story_choices и продолжает работать на существующих базах.
CHOICE_TEXTS = {
    ("node_start", "🗡 Напасть первым"): "🗡 Attack first",
    ("node_start", "💬 Выслушать"): "💬 Listen",
    ("node_listen", "🧪 Отдать зелье"): "🧪 Give the potion",
    ("node_fail", "Отползти в лагерь"): "Crawl back to camp",
    ("node_epilogue", "Уйти в лагерь"): "Leave for camp",
    ("node_epilogue", "Секрет спасенного эльфа"): "Secret of the saved elf",
}


def _translated(mapping: dict, key, fallback: str) -> str:
    if get_language() == "ru":
        return fallback
    return mapping.get(key, fallback)


def story_title(story_id: str, fallback: str) -> str:
    return _translated(STORY_TITLES, story_id, fallback)


def node_text(node_id: str, fallback: str) -> str:
    return _translated(NODE_TEXTS, node_id, fallback)


def choice_text(node_id: str, fallback: str) -> str:
    return _translated(CHOICE_TEXTS, (node_id, fallback), fallback)
