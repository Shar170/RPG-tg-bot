import random
import uuid

def generate_emoji_puzzle():
    """Генерирует случайную головоломку из 4 разных категорий"""
    puzzle_type = random.choice(["math_classic", "math_weight", "magic_square", "sequence"])
    
    if puzzle_type == "math_classic":
        # Вариант 1: Классические символьные уравнения
        emojis = random.sample(["🍎", "🍄", "💎", "🛡️", "🗡️", "🦇", "💀", "🧪"], 3)
        e1, e2, e3 = emojis
        a = random.randint(2, 10)
        b = random.randint(2, 10)
        c = random.randint(2, 10)
        
        text = (f"📜 **Древние руны:**\n\n"
                f"{e1} + {e1} = {a+a}\n"
                f"{e1} + {e2} = {a+b}\n"
                f"{e2} - {e3} = {b-c}\n\n"
                f"{e1} + {e2} × {e3} = ?")
        correct = a + b * c
        
    elif puzzle_type == "math_weight":
        # Вариант 2: Балансировка весов
        emojis = random.sample(["💎", "🪙", "🔮", "📜", "🍖", "⚙️"], 3)
        e1, e2, e3 = emojis
        m1 = random.randint(2, 5)
        m2 = random.randint(2, 5)
        
        text = (f"⚖️ **Алхимические весы находятся в равновесии:**\n\n"
                f"1 {e1} = {m1} {e2}\n"
                f"1 {e2} = {m2} {e3}\n\n"
                f"Сколько {e3} уравновесят 1 {e1}?")
        correct = m1 * m2
        
    elif puzzle_type == "sequence":
        # Вариант 3: Математические последовательности
        seq_type = random.choice(["arithmetic", "geometric", "fibonacci"])
        if seq_type == "arithmetic":
            start, step = random.randint(1, 15), random.randint(2, 7)
            seq = [start + i*step for i in range(5)]
        elif seq_type == "geometric":
            start, step = random.randint(1, 4), random.choice([2, 3])
            seq = [start * (step**i) for i in range(5)]
        else:
            seq = [random.randint(1, 4), random.randint(1, 4)]
            for _ in range(3): seq.append(seq[-1] + seq[-2])
        
        correct = seq[-1]
        seq_str = ", ".join(map(str, seq[:-1])) + ", ?"
        text = f"🔢 **Продолжите последовательность, выбитую на стене:**\n\n`{seq_str}`"
        
    else: 
        # Вариант 4: Магический квадрат
        # Базовый магический квадрат (сумма 15)
        base = [[8, 1, 6], [3, 5, 7], [4, 9, 2]]
        offset = random.randint(1, 15) # Смещаем числа, чтобы квадрат всегда был новым
        square = [[c + offset for c in row] for row in base]
        
        coords = [(r, c) for r in range(3) for c in range(3)]
        random.shuffle(coords)
        
        tr, tc = coords[0] # Искомая ячейка
        correct = square[tr][tc]
        hr1, hc1 = coords[1] # Скрытая ячейка 1
        hr2, hc2 = coords[2] # Скрытая ячейка 2
        
        grid = []
        for r in range(3):
            row_strs = []
            for c in range(3):
                if r == tr and c == tc: row_strs.append("[ ? ]")
                elif r == hr1 and c == hc1: row_strs.append("[ X ]")
                elif r == hr2 and c == hc2: row_strs.append("[ Y ]")
                else: 
                    # Выравниваем числа по центру для красивой отрисовки сетки
                    row_strs.append(f"[{str(square[r][c]).center(3)}]")
            grid.append("".join(row_strs))
            
        grid_text = "\n".join(grid)
        text = (f"🔲 **Магический квадрат**\n"
                f"Сумма чисел в каждой строке, столбце и по обеим диагоналям абсолютно одинакова. Часть символов стерта временем.\n\n"
                f"`{grid_text}`\n\n"
                f"Какое число должно быть на месте `[ ? ]`?")
    
    # Генерируем 3 правдоподобных неправильных ответа
    options = {correct}
    while len(options) < 4:
        noise = random.randint(-6, 6)
        if noise == 0: continue
        wrong = correct + noise
        if wrong > 0: options.add(wrong) # Только положительные ответы
    
    options_list = list(options)
    random.shuffle(options_list)
    
    return {
        "text": text,
        "options": options_list,
        "correct": correct
    }


def generate_dungeon_graph(dungeon_type="solo"):
    """
    Генерирует направленный граф подземелья (слои комнат).
    Возвращает dict с узлами и стартовой комнатой.
    """
    def get_id(): return str(uuid.uuid4())[:6]
    
    start_id = get_id()
    nodes = {start_id: {"type": "empty", "next": []}}
    current_layer = [start_id]
    
    # 3 слоя случайных комнат перед костром
    for i in range(3):
        next_layer = []
        num_rooms = random.choice([1, 2])
        for _ in range(num_rooms):
            r_id = get_id()
            types = ["combat", "combat", "puzzle", "treasure", "empty"]
            # Сразу после входа всегда битва или загадка
            r_type = random.choice(["combat", "puzzle"]) if i == 0 else random.choice(types)
            nodes[r_id] = {"type": r_type, "next": []}
            next_layer.append(r_id)
            
        # Связываем предыдущий слой с новым
        for c_id in current_layer:
            nodes[c_id]["next"] = next_layer.copy()
        current_layer = next_layer
        
    camp_id = get_id()
    nodes[camp_id] = {"type": "campfire", "next": []}
    for c_id in current_layer: 
        nodes[c_id]["next"] = [camp_id]
    
    boss_id = get_id()
    nodes[boss_id] = {"type": "boss", "next": []}
    nodes[camp_id]["next"] = [boss_id]
    
    return {"current_node": start_id, "dungeon_type": dungeon_type, "nodes": nodes}
