import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_user, update_user, get_item, get_item_name

router = Router()

@router.callback_query(F.data == "inv_open")
async def open_inventory(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    inv = user.get('inventory', {})
    eq = inv.get('equipment', {})
    
    w_id = eq.get('weapon')
    a_id = eq.get('armor')
    art_id = eq.get('artifact')
    
    w_name = get_item(w_id)['name'] if w_id else "Нет"
    a_name = get_item(a_id)['name'] if a_id else "Нет"
    art_name = get_item(art_id)['name'] if art_id else "Нет"
    
    text = (
        f"🎒 **Инвентарь**\n\n"
        f"💰 Золото: {user['gold']} 🪙\n"
        f"💎 Алмазы: {user.get('gems', 0)} 💎\n\n"
        f"**👕 Экипировка:**\n"
        f"🗡️ Оружие: {w_name}\n"
        f"🛡️ Броня: {a_name}\n"
        f"💍 Артефакт: {art_name}\n\n"
        f"Выберите раздел сумки:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗡️ Оружие", callback_data="inv_list_weapon"), 
         InlineKeyboardButton(text="🛡️ Броня", callback_data="inv_list_armor")],
        [InlineKeyboardButton(text="💍 Артефакты", callback_data="inv_list_artifact")],
        [InlineKeyboardButton(text="🧪 Зелья и Бомбы", callback_data="inv_list_potions"), 
         InlineKeyboardButton(text="📦 Ресурсы", callback_data="inv_list_materials")],
        [InlineKeyboardButton(text="🔙 В лагерь", callback_data="town_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("inv_list_"))
async def inv_list_category(callback: CallbackQuery):
    cat = callback.data.replace("inv_list_", "")
    user = get_user(callback.from_user.id)
    inv = user.get('inventory', {})
    eq = inv.get('equipment', {})
    
    buttons = []
    if cat in ["weapon", "armor", "artifact"]:
        cat_map = {"weapon": "🗡️ Оружие", "armor": "🛡️ Броня", "artifact": "💍 Артефакты"}
        source = inv.get("artifacts", []) if cat == "artifact" else [i for i in inv.get("backpack", []) if get_item(i) and get_item(i)['type'] == cat]
            
        unique_items = list(set(source))
        for i_id in unique_items:
            count = source.count(i_id)
            item = get_item(i_id)
            if not item: continue
            
            is_equipped = " ✅ (Надето)" if eq.get(cat) == i_id else ""
            stats_str = ""
            stats = item.get('stats', {})
            if 'dmg' in stats: stats_str += f"⚔️{stats['dmg']} "
            if 'def' in stats: stats_str += f"🛡️️{stats['def']} "
            if 'dodge' in stats: stats_str += f"💨{int(stats['dodge']*100)}% "
            if 'crit_chance' in stats: stats_str += f"💥{int(stats['crit_chance']*100)}% "
            if 'vamp_chance' in stats: stats_str += f"🩸{int(stats['vamp_chance']*100)}% "
            
            btn_text = f"{item['name']} {stats_str}(x{count}){is_equipped}"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"inv_eq_{cat}_{i_id}")])
            
        text = f"{cat_map[cat]}\nНажмите на предмет, чтобы надеть или снять его:"
        if not unique_items: text = f"У вас нет предметов в категории {cat_map[cat]}."
        
    elif cat == "potions":
        pots = inv.get("potions", [])
        counts = {p: pots.count(p) for p in set(pots)}
        text = "🧪 **Ваши зелья и расходники:**\n\n" + "\n".join([f"• {p} (x{c})" for p, c in counts.items()]) if pots else "🧪 У вас нет зелий."
    elif cat == "materials":
        mats = inv.get("materials", {})
        text = "📦 **Ваши ресурсы:**\n\n" + "\n".join([f"• {get_item_name(m)} (x{c})" for m, c in mats.items() if c > 0]) if mats else "📦 У вас нет ресурсов."
        
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="inv_open")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("inv_eq_"))
async def inv_equip_item(callback: CallbackQuery):
    parts = callback.data.split("_", 3)
    cat = parts[2]
    item_id = parts[3]
    
    user = get_user(callback.from_user.id)
    inv = user.get('inventory', {})
    eq = inv.setdefault('equipment', {})
    
    if eq.get(cat) == item_id:
        del eq[cat]
        await callback.answer("Предмет снят!", show_alert=False)
    else:
        eq[cat] = item_id
        await callback.answer("Предмет надет!", show_alert=False)
        
    update_user(user['user_id'], inventory=inv)
    callback.data = f"inv_list_{cat}"
    await inv_list_category(callback)

