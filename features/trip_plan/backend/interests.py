"""Интересы гостя: чем хочет заняться и как это превращается в места и время дня.

specs — фильтры «рядом» (features/nearby/specs.json), из которых берём места; slot — когда в дне;
stay — сколько минут на месте (и сколько должно быть открыто); named — только места с названием.
Новый интерес — новая запись здесь, без нового кода.
"""

INTERESTS = [
    {"id": "sea", "title": "Плавать", "icon": "waves", "slot": "10:00", "stay": 180, "specs": [],
     "none": "пляжа и бассейна", "none_title": "Пляж и бассейн пешком не близко"},
    {"id": "culture", "title": "Культура", "icon": "landmark", "slot": "15:00", "stay": 90, "limit": 20,
     "specs": ["sights", "church"], "named": True, "none": "музеев и достопримечательностей",
     "none_title": "Музеев рядом нет"},
    {"id": "party", "title": "Тусить", "icon": "glass", "slot": "22:00", "stay": 90, "specs": ["bar"], "named": True,
     "none": "баров", "none_title": "Баров пешком нет"},
    {"id": "walk", "title": "Гулять", "icon": "tree", "slot": "18:00", "stay": 60, "specs": ["park", "viewpoint"],
     "none": "парков и смотровых", "none_title": "Парков рядом нет"},
    {"id": "food", "title": "Вкусно поесть", "icon": "fork", "slot": "20:00", "stay": 90,
     "specs": ["restaurant", "cafe"], "named": True, "none": "ресторанов", "none_title": "Ресторанов рядом нет"},
    {"id": "sport", "title": "Спорт", "icon": "bike", "slot": "07:30", "stay": 60, "specs": ["bike", "workout", "gym"],
     "none": "проката и спортплощадок", "none_title": "Спортплощадок рядом нет"},
    {"id": "kids", "title": "С детьми", "icon": "child", "slot": "16:30", "stay": 90,
     "specs": ["playground", "zoo", "waterpark"], "none": "детских площадок", "none_title": "Детских площадок рядом нет"},
    {"id": "quiet", "title": "Выспаться", "icon": "moon", "slot": "23:00", "stay": 0, "specs": []},
]
BY_ID = {i["id"]: i for i in INTERESTS}
ORDER = ["sport", "sea", "culture", "kids", "walk", "food", "party", "quiet"]

# тег OSM → (что это, «до чего» идём)
KIND = {
    "beach": ("Пляж", "до пляжа"),
    "hotel_pool": ("Бассейн отеля", "до бассейна"),
    "tourism=museum": ("Музей", "до музея"),
    "tourism=attraction": ("Достопримечательность", "до места"),
    "tourism=gallery": ("Галерея", "до галереи"),
    "amenity=theatre": ("Театр", "до театра"),
    "amenity=place_of_worship": ("Храм", "до храма"),
    "amenity=bar": ("Бар", "до бара"),
    "amenity=pub": ("Паб", "до паба"),
    "amenity=nightclub": ("Клуб", "до клуба"),
    "leisure=park": ("Парк", "до парка"),
    "leisure=garden": ("Сад", "до сада"),
    "tourism=viewpoint": ("Смотровая", "до смотровой"),
    "amenity=restaurant": ("Ресторан", "до ресторана"),
    "amenity=cafe": ("Кафе", "до кафе"),
    "amenity=fast_food": ("Закусочная", "до закусочной"),
    "amenity=bicycle_rental": ("Прокат велосипедов", "до проката"),
    "leisure=fitness_station": ("Уличные тренажёры", "до тренажёров"),
    "leisure=pitch": ("Спортплощадка", "до площадки"),
    "leisure=fitness_centre": ("Фитнес-клуб", "до фитнес-клуба"),
    "leisure=sports_centre": ("Спортцентр", "до спортцентра"),
    "leisure=playground": ("Детская площадка", "до площадки"),
    "tourism=zoo": ("Зоопарк", "до зоопарка"),
    "tourism=aquarium": ("Океанариум", "до океанариума"),
    "tourism=theme_park": ("Парк развлечений", "до парка"),
    "leisure=water_park": ("Аквапарк", "до аквапарка"),
    "leisure=swimming_pool": ("Бассейн", "до бассейна"),
}
