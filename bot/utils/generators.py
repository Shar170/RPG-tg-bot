import random
import uuid

def generate_emoji_puzzle(puzzle_category: str = None):
    """
    Генерирует процедурную головоломку.
    Категории:
    - math_classic: символьные уравнения с эмодзи
    - math_weight: алхимические весы (пропорции)
    - sequence: арифметические / геометрические / фибоначчи ряды
    - magic_square: магический квадрат 3х3 с пропущенным числом
    - matrix_rule: руническая матрица 3х3 с математическим законом строк
    - clock_angle: вычисление наименьшего угла между часовыми стрелками
    """
    all_categories = ["math_classic", "math_weight", "sequence", "magic_square", "matrix_rule", "clock_angle"]
    puzzle_type = puzzle_category if puzzle_category in all_categories else random.choice(all_categories)

    if puzzle_type == "math_classic":
        emojis = random.sample(["🍎", "🍄", "💎", "🛡️", "🗡️", "🦇", "💀", "🧪"], 3)
        e1, e2, e3 = emojis
        a = random.randint(2, 10)
        b = random.randint(2, 10)
        c = random.randint(2, 10)
        text = (
            f"📜 **Древние руны:**\n\n"
            f"{e1} + {e1} = {a+a}\n"
            f"{e1} + {e2} = {a+b}\n"
            f"{e2} - {e3} = {b-c}\n\n"
            f"{e1} + {e2} × {e3} = ?"
        )
        correct = a + b * c

    elif puzzle_type == "math_weight":
        emojis = random.sample(["💎", "🪙", "🔮", "📜", "🍖", "⚙️"], 3)
        e1, e2, e3 = emojis
        m1 = random.randint(2, 5)
        m2 = random.randint(2, 5)
        text = (
            f"⚖️ **Алхимические весы находятся в равновесии:**\n\n"
            f"1 {e1} = {m1} {e2}\n"
            f"1 {e2} = {m2} {e3}\n\n"
            f"Сколько {e3} уравновесят 1 {e1}?"
        )
        correct = m1 * m2

    elif puzzle_type == "sequence":
        seq_type = random.choice(["arithmetic", "geometric", "fibonacci"])
        if seq_type == "arithmetic":
            start, step = random.randint(1, 15), random.randint(2, 7)
            seq = [start + i * step for i in range(5)]
        elif seq_type == "geometric":
            start, step = random.randint(1, 4), random.choice([2, 3])
            seq = [start * (step ** i) for i in range(5)]
        else:
            seq = [random.randint(1, 4), random.randint(1, 4)]
            for _ in range(3):
                seq.append(seq[-1] + seq[-2])
        correct = seq[-1]
        seq_str = ", ".join(map(str, seq[:-1])) + ", ?"
        text = f"🔢 **Продолжите последовательность, высеченную на стене:**\n\n`{seq_str}`"

    elif puzzle_type == "magic_square":
        base = [[8, 1, 6], [3, 5, 7], [4, 9, 2]]
        offset = random.randint(1, 15)
        square = [[c + offset for c in row] for row in base]
        coords = [(r, c) for r in range(3) for c in range(3)]
        random.shuffle(coords)
        tr, tc = coords[0]
        correct = square[tr][tc]
        hr1, hc1 = coords[1]
        hr2, hc2 = coords[2]
        grid = []
        for r in range(3):
            row_strs = []
            for c in range(3):
                if r == tr and c == tc:
                    row_strs.append("[ ? ]")
                elif r == hr1 and c == hc1:
                    row_strs.append("[ X ]")
                elif r == hr2 and c == hc2:
                    row_strs.append("[ Y ]")
                else:
                    row_strs.append(f"[{str(square[r][c]).center(3)}]")
            grid.append("".join(row_strs))
        grid_text = "\n".join(grid)
        text = (
            f"🔲 **Магический квадрат:**\n"
            f"Сумма чисел в каждой строке, столбце и по диагоналям одинакова. Часть стёрта временем.\n\n"
            f"`{grid_text}`\n\n"
            f"Какое число скрыто под `[ ? ]`?"
        )

    elif puzzle_type == "matrix_rule":
        rule = random.choice(["add_first_two", "diff_first_two", "sum_edges"])
        rows = []
        for _ in range(3):
            if rule == "add_first_two":
                a = random.randint(1, 9)
                b = random.randint(1, 9)
                c = a + b
            elif rule == "diff_first_two":
                b = random.randint(1, 7)
                diff = random.randint(1, 6)
                a = b + diff
                c = a - b
            else:
                a = random.randint(1, 8)
                c = random.randint(1, 8)
                b = a + c
            rows.append([a, b, c])

        correct = rows[2][2] if rule != "sum_edges" else rows[2][1]
        grid_text = (
            f"`{rows[0][0]:>2}  {rows[0][1]:>2}  {rows[0][2]:>2}`\n"
            f"`{rows[1][0]:>2}  {rows[1][1]:>2}  {rows[1][2]:>2}`\n"
        )
        if rule != "sum_edges":
            grid_text += f"`{rows[2][0]:>2}  {rows[2][1]:>2}   ?`"
        else:
            grid_text += f"`{rows[2][0]:>2}   ?  {rows[2][2]:>2}`"

        text = (
            f"🧩 **Руническая Таблица Чисел:**\n"
            f"Найдите закономерность в строках и вычислите скрытое число:\n\n"
            f"{grid_text}"
        )

    else:  # clock_angle
        h = random.randint(1, 12)
        m = random.choice([0, 10, 15, 20, 30, 40, 45, 50])
        raw_angle = abs(30 * h - 5.5 * m) % 360
        if raw_angle > 180:
            raw_angle = 360 - raw_angle
        
        # Для часов формируем строковый ответ с градусами
        ans_str = f"{int(raw_angle)}°" if raw_angle.is_integer() else f"{raw_angle}°"
        wrongs = set()
        shifts = [-25, -15, -10, 10, 15, 20, 25, 30]
        random.shuffle(shifts)
        for s in shifts:
            fake = raw_angle + s
            if 0 < fake <= 180 and fake != raw_angle:
                fake_str = f"{int(fake)}°" if fake.is_integer() else f"{fake}°"
                wrongs.add(fake_str)
            if len(wrongs) == 3:
                break
        options = list(wrongs) + [ans_str]
        random.shuffle(options)
        return {
            "text": f"🕰️ **Хроно-Алтарь Времени:**\nКакой наименьший угол образуют часовая и минутная стрелки в **{h:02d}:{m:02d}**?",
            "options": options,
            "correct": ans_str
        }

    # Генерация ложных вариантов для числовых загадок
    options = {correct}
    while len(options) < 4:
        noise = random.randint(-6, 6)
        if noise == 0:
            continue
        wrong = correct + noise
        if wrong > 0:
            options.add(wrong)

    options_list = [str(x) for x in options]
    random.shuffle(options_list)

    return {
        "text": text,
        "options": options_list,
        "correct": str(correct)
    }

def generate_dungeon_graph(dungeon_type="solo", mobs_pool=None, boss_id=None):
    """
    Генерирует направленный граф подземелья (слои комнат).
    Принимает опциональный mobs_pool и boss_id для ивентов и Войны за Камарию.
    """
    if mobs_pool is None:
        mobs_pool = ["temple_guard", "living_idol", "khmer_priest", "poison_slime"]
    if boss_id is None:
        boss_id = "temple_guard" if dungeon_type == "solo" else "bone_dragon"

    def get_id():
        return str(uuid.uuid4())[:6]

    start_id = get_id()
    nodes = {start_id: {"type": "empty", "next": []}}
    current_layer = [start_id]

    # 3 слоя случайных комнат перед костром/привалом
    for i in range(3):
        next_layer = []
        num_rooms = random.choice([1, 2])
        for _ in range(num_rooms):
            r_id = get_id()
            types = ["combat", "combat", "puzzle", "treasure", "empty"]
            # Сразу после входа всегда битва или загадка
            r_type = random.choice(["combat", "puzzle"]) if i == 0 else random.choice(types)
            
            node_data = {"type": r_type, "next": []}
            if r_type == "combat":
                node_data["mob_id"] = random.choice(mobs_pool)
            elif r_type == "puzzle":
                # Для войны за Камарию выше шанс на новые математические загадки
                p_cat = random.choice(["matrix_rule", "clock_angle"]) if dungeon_type == "war" else None
                node_data["puzzle"] = generate_emoji_puzzle(p_cat)

            nodes[r_id] = node_data
            next_layer.append(r_id)

        # Связываем предыдущий слой с новым
        for c_id in current_layer:
            nodes[c_id]["next"] = next_layer.copy()
        current_layer = next_layer

    # Привал (костёр) перед боссом
    camp_id = get_id()
    nodes[camp_id] = {"type": "campfire", "next": []}
    for c_id in current_layer:
        nodes[c_id]["next"] = [camp_id]

    # Финальный Босс
    b_id = get_id()
    nodes[b_id] = {"type": "boss", "mob_id": boss_id, "next": []}
    nodes[camp_id]["next"] = [b_id]

    return {
        "current_node": start_id,
        "dungeon_type": dungeon_type,
        "nodes": nodes,
        "gathered_gold": 0,
        "gathered_materials": {},
        "gathered_equipment": []
    }
