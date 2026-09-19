# utils/generators.py
import random

EMOJIS = ["🍎", "🗡️", "🛡️", "🧪", "💎", "📜"]

def generate_emoji_puzzle():
    # ... (код генератора загадок остается без изменений) ...
    selected_emojis = random.sample(EMOJIS, 3)
    e1, e2, e3 = selected_emojis
    
    val1 = random.randint(2, 9)
    val2 = random.randint(2, 9)
    val3 = random.randint(2, 9)
    
    target_answer = val1 + val3
    
    text = (
        f"🧩 **Древняя клинопись на вратах:**\n\n"
        f"{e1} + {e1} = {val1 + val1}\n"
        f"{e1} + {e2} = {val1 + val2}\n"
        f"{e2} + {e3} = {val2 + val3}\n\n"
        f"Чему равно: **{e1} + {e3} = ?**"
    )
    
    answers = {target_answer}
    while len(answers) < 4:
        wrong = target_answer + random.choice([-3, -2, -1, 1, 2, 3])
        if wrong > 0:
            answers.add(wrong)
            
    answers_list = list(answers)
    random.shuffle(answers_list)
    
    return {"text": text, "correct": target_answer, "options": answers_list}


def generate_dungeon_graph(dungeon_type="solo"):
    """
    Генерирует процедурный граф подземелья.
    Случайная глубина (кол-во слоев) и случайная ширина (комнат в слое).
    """
    # Шанс выпадения комнат (пустые комнаты делаем редкими)
    room_types = ["combat", "combat", "combat", "puzzle", "treasure", "empty"]
    
    # Случайная глубина данжа (от 3 до 5 развилок до костра)
    num_layers = random.randint(3, 5)
    
    graph = {}
    layers = []
    
    # Слой 0: Вход
    graph["n_start"] = {"type": "entrance", "next": []}
    layers.append(["n_start"])
    
    # Генерируем "этажи" (слои)
    node_counter = 1
    for depth in range(1, num_layers + 1):
        num_nodes = random.randint(2, 3) # 2 или 3 комнаты на выбор
        current_layer_nodes = []
        
        for _ in range(num_nodes):
            node_id = f"n_{node_counter}"
            node_counter += 1
            graph[node_id] = {"type": random.choice(room_types), "next": []}
            current_layer_nodes.append(node_id)
            
        layers.append(current_layer_nodes)
        
    # Предпоследний слой: Привал
    graph["n_campfire"] = {"type": "campfire", "next": ["n_boss"]}
    layers.append(["n_campfire"])
    
    # Последний слой: Босс
    graph["n_boss"] = {"type": "boss", "next": []}
    layers.append(["n_boss"])
    
    # --- СВЯЗЫВАЕМ УЗЛЫ (Прокладываем пути) ---
    for i in range(len(layers) - 1):
        current_layer = layers[i]
        next_layer = layers[i+1]
        
        # 1. Из каждой комнаты текущего слоя должна вести хотя бы 1 дверь вперед
        for node in current_layer:
            # Выбираем случайное количество дверей (1 или 2, но не больше, чем комнат впереди)
            num_doors = random.randint(1, min(2, len(next_layer)))
            targets = random.sample(next_layer, num_doors)
            graph[node]["next"].extend(targets)
            
        # 2. В каждую комнату следующего слоя должна вести хотя бы 1 дверь (чтобы не было недостижимых комнат)
        # Подсчитываем входящие пути
        incoming = {n: 0 for n in next_layer}
        for node in current_layer:
            for target in graph[node]["next"]:
                incoming[target] += 1
                
        # Если в комнату никто не проложил путь — форсируем связь из случайной комнаты текущего слоя
        for target, count in incoming.items():
            if count == 0:
                source = random.choice(current_layer)
                if target not in graph[source]["next"]:
                    graph[source]["next"].append(target)
    
    return {
        "current_node": "n_start",
        "nodes": graph,
        "dungeon_type": dungeon_type
    }
