from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item, get_item_name
from i18n import t
from utils.potions import get_potion_display_name

router = Router()


def _equipped_name(item_id) -> str:
    item = get_item(item_id) if item_id else None
    return item["name"] if item else t("common.none")


@router.callback_query(F.data == "inv_open")
async def open_inventory(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    inv = user.get('inventory', {})
    eq = inv.get('equipment', {})

    w_name = _equipped_name(eq.get('weapon'))
    a_name = _equipped_name(eq.get('armor'))
    art_name = _equipped_name(eq.get('artifact'))

    text = (
        t("inv.title")
        + t("inv.gold", gold=user['gold'])
        + t("inv.gems", gems=user.get('gems', 0))
        + t("inv.equipment")
        + t("inv.weapon", name=w_name)
        + t("inv.armor", name=a_name)
        + t("inv.artifact", name=art_name)
        + t("inv.choose")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("inv.btn.weapon"), callback_data="inv_list_weapon"),
         InlineKeyboardButton(text=t("inv.btn.armor"), callback_data="inv_list_armor")],
        [InlineKeyboardButton(text=t("inv.btn.artifacts"), callback_data="inv_list_artifact")],
        [InlineKeyboardButton(text=t("inv.btn.potions"), callback_data="inv_list_potions"),
         InlineKeyboardButton(text=t("inv.btn.materials"), callback_data="inv_list_materials")],
        [InlineKeyboardButton(text=t("inv.btn.back"), callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


async def render_category(callback: CallbackQuery, cat: str):
    """Вспомогательная функция для отрисовки категории без подмены коллбэка"""
    user = get_user(callback.from_user.id)
    inv = user.get('inventory', {})
    eq = inv.get('equipment', {})

    buttons = []
    if cat in ["weapon", "armor", "artifact"]:
        cat_map = {
            "weapon": t("inv.cat.weapon"),
            "armor": t("inv.cat.armor"),
            "artifact": t("inv.cat.artifact"),
        }
        source = inv.get("artifacts", []) if cat == "artifact" else [i for i in inv.get("backpack", []) if get_item(i) and get_item(i)['type'] == cat]

        unique_items = list(dict.fromkeys(source))
        for i_id in unique_items:
            count = source.count(i_id)
            item = get_item(i_id)
            if not item:
                continue

            is_equipped = t("inv.equipped") if eq.get(cat) == i_id else ""
            stats_str = ""
            stats = item.get('stats', {})

            req_lvl = int(stats.get('req_lvl', 1))
            if req_lvl > 1:
                stats_str += t("inv.level_short", level=req_lvl)

            if 'dmg' in stats: stats_str += f"⚔️{stats['dmg']} "
            if 'def' in stats: stats_str += f"🛡{stats['def']} "
            if 'dodge' in stats: stats_str += f"💨{int(stats['dodge']*100)}% "
            if 'crit_chance' in stats: stats_str += f"💥{int(stats['crit_chance']*100)}% "
            if 'vamp_chance' in stats: stats_str += f"🩸{int(stats['vamp_chance']*100)}% "

            btn_text = f"{item['name']} {stats_str}(x{count}){is_equipped}"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"inv_eq_{cat}_{i_id}")])

        text = t("inv.hint", cat=cat_map[cat])
        if not unique_items:
            text = t("inv.empty_category", cat=cat_map[cat])

    elif cat == "potions":
        pots = inv.get("potions", [])
        counts = {p: pots.count(p) for p in dict.fromkeys(pots)}
        lines = []
        for p_id, c in counts.items():
            name = get_potion_display_name(p_id)
            lines.append(f"• {name} (x{c})")

        text = t("inv.potions.title") + "\n".join(lines) if pots else t("inv.potions.empty")

    elif cat == "materials":
        mats = inv.get("materials", {})
        text = (
            t("inv.materials.title") + "\n".join(f"• {get_item_name(m)} (x{c})" for m, c in mats.items() if c > 0)
            if mats else t("inv.materials.empty")
        )

    buttons.append([InlineKeyboardButton(text=t("inv.back"), callback_data="inv_open")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")


@router.callback_query(F.data.startswith("inv_list_"))
async def inv_list_category(callback: CallbackQuery):
    cat = callback.data.replace("inv_list_", "")
    await render_category(callback, cat)


@router.callback_query(F.data.startswith("inv_eq_"))
async def inv_equip_item(callback: CallbackQuery):
    parts = callback.data.split("_", 3)
    cat = parts[2]
    item_id = parts[3]

    user = get_user(callback.from_user.id)
    inv = user.get('inventory', {})
    eq = inv.setdefault('equipment', {})

    if eq.get(cat) != item_id:
        item = get_item(item_id)
        if item:
            req_lvl = int(item.get('stats', {}).get('req_lvl', 1))
            user_lvl = user.get('level', 1)

            if user_lvl < req_lvl:
                return await callback.answer(
                    t("inv.level_too_low", level=req_lvl), show_alert=True
                )

    if eq.get(cat) == item_id:
        del eq[cat]
        await callback.answer(t("inv.unequipped"), show_alert=False)
    else:
        eq[cat] = item_id
        await callback.answer(t("inv.equipped_alert"), show_alert=False)

    update_user(user['user_id'], inventory=inv)
    # Вызываем отрисовку напрямую
    await render_category(callback, cat)
