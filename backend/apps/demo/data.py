"""Посевные данные из прототипа ГДеволна v14, уже сопоставленные с моделями backend.

Источники: docs/prototype/frontend-port/seed_public.json и seed_cabinet.json (контейнер backend видит только ./backend,
поэтому данные перенесены сюда). Правила (TZ 12.2, PL-02, ATX-33, BR-08):
- всё, что создаётся из этого модуля, помечается is_demo=True;
- демо-рейтинги, число отзывов, отзывы, обращения, сообщения, статистика просмотров и сертификаты прототипа
  НЕ переносятся — их здесь намеренно нет;
- цены — «пример цены» прототипа и живут только в демо-записях.
"""

DATA_SOURCE = "Прототип ГДеволна v14 (посевные данные)"
DATA_STATUS_NOTE = "Информация требует проверки на месте (TZ SPT-11: хранить дату подтверждения и источник)"
PASSWORD = "Demo-2026!"
TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
EMAIL_DOMAIN = "demo.gdevolna.local"

# --- Регионы -----------------------------------------------------------------------------------------------------
# Первые пять — публичная часть прототипа (центр карты и zoom оттуда), остальные — список регионов профиля
# шейпера (seed_cabinet.json → shapers.options.profileRegions) + Мурманская область (Териберка).
# (slug, название, IANA-зона, широта, долгота, zoom)
REGIONS = [
    ("kamchatskiy-kray", "Камчатский край", "Asia/Kamchatka", "53.05", "158.82", 6),
    ("krym", "Крым", "Europe/Moscow", "44.95", "34.10", 6),
    ("sakhalin", "Сахалин", "Asia/Sakhalin", "46.96", "142.75", 6),
    ("ladozhskoe-ozero", "Ладожское озеро", "Europe/Moscow", "61.40", "30.80", 6),
    ("primorskiy-kray", "Приморский край", "Asia/Vladivostok", "43.12", "131.90", 6),
    ("kaliningradskaya-oblast", "Калининградская область", "Europe/Kaliningrad", "54.71", "20.51", 8),
    ("krasnodarskiy-kray", "Краснодарский край", "Europe/Moscow", "44.72", "37.77", 7),
    ("murmanskaya-oblast", "Мурманская область", "Europe/Moscow", "68.97", "33.07", 6),
    ("leningradskaya-oblast", "Ленинградская область", "Europe/Moscow", "59.94", "30.31", 7),
    ("moskva", "Москва и Московская область", "Europe/Moscow", "55.75", "37.62", 8),
]

# Сезон прототипа → лучшие месяцы.
SEASON_MONTHS = {
    "Весна — лето": [3, 4, 5, 6, 7, 8],
    "Лето — осень": [6, 7, 8, 9, 10, 11],
    "Осень": [9, 10, 11],
    "Осень — зима": [9, 10, 11, 12, 1, 2],
}

# --- Споты (seed_public.json → spots) -------------------------------------------------------------------------------
# Фото: файлы из seed_assets/spots. Фото Сахалина №1 (контейнеровоз с логотипами MAERSK / Hamburg Süd) не используется
# (ASSETS.md: сторонние бренды) — обложкой становится фото №2.
SPOTS = [
    {
        "prototype_id": "english",
        "slug": "zaliv-anglichanka",
        "name": "Залив Англичанка",
        "region": "kamchatskiy-kray",
        "lat": "52.934860", "lng": "158.779867", "precision": "exact",
        "short_description": "Дикий пляж, маршрут пешком от конного клуба «Донской». Подъезд ограничен. "
                             "Информация требует проверки на месте.",
        "nature": ["Вулканы", "Горы", "Дикий пляж"],
        "difficulty": "beginner", "bottom_type": "sand", "break_type": "beach",
        "wave_character": "Правая",
        "season": "Весна — лето",
        "wind": ["NW"], "wind_text": "северо-запад",
        "swell": ["SE"], "swell_text": "юго-восток",
        "bottom_text": "песок",
        "hazards": ["rocks"],
        "hazard_notes": "Камни. Обстановка и доступ могут меняться.",
        "access": "Маршрут пешком от конного клуба «Донской». Подъезд ограничен.",
        "entry_exit": "Вход и выход с песчаного пляжа. Информация требует проверки на месте.",
        "infrastructure": [("trail", "Пеший подход"), ("camping", "Палатка")],
        "photos": [
            ("spot-zaliv-anglichanka-1.jpg", "Общий вид спота", "Залив Англичанка — фото 1"),
            ("spot-zaliv-anglichanka-2.jpg", "Линия волны и берег", "Залив Англичанка — фото 2"),
        ],
    },
    {
        "prototype_id": "halak",
        "slug": "khalaktyrskiy-plyazh",
        "name": "Халактырский пляж",
        "region": "kamchatskiy-kray",
        "lat": "53.059000", "lng": "158.822000", "precision": "exact",
        "short_description": "Тихоокеанское побережье, вулканы на горизонте и километры чёрного песка.",
        "nature": ["Вулканы", "Морские котики", "Пляж"],
        "difficulty": "intermediate", "bottom_type": "sand", "break_type": "beach",
        "wave_character": "Левая и правая",
        "season": "Лето — осень",
        "wind": [], "wind_text": "зависит от участка",
        "swell": [], "swell_text": "тихоокеанский",
        "bottom_text": "чёрный песок",
        "hazards": ["cold_water", "strong_current", "weather_change"],
        "hazard_notes": "Холодная вода, течения, резкие изменения погоды.",
        "access": "Подъезд на автомобиле к пляжу.",
        "entry_exit": "Вход и выход с пляжа чёрного песка; у берега следите за течениями.",
        "infrastructure": [("other", "Подъезд"), ("cafe", "Кафе в районе")],
        "photos": [
            ("spot-khalaktyrskiy-plyazh-1.webp", "Общий вид спота", "Халактырский пляж — фото 1"),
            ("spot-khalaktyrskiy-plyazh-2.jpg", "Линия волны и берег", "Халактырский пляж — фото 2"),
            ("spot-khalaktyrskiy-plyazh-3.jpg", "Дополнительный ракурс", "Халактырский пляж — фото 3"),
        ],
    },
    {
        "prototype_id": "ladoga",
        "slug": "ladozhskie-shkhery",
        "name": "Ладожские шхеры",
        "region": "ladozhskoe-ozero",
        "lat": "61.600000", "lng": "30.800000", "precision": "approximate",
        "short_description": "Северная вода, сосны и суровые ветровые волны. Локальные условия сильно различаются.",
        "nature": ["Сосновый лес", "Скалы", "Озеро"],
        # «Озёрный спот» в прототипе — в справочнике брейков такого нет; ближайший — бич-брейк, тип волны в тексте.
        "difficulty": "intermediate", "bottom_type": "rock", "break_type": "beach",
        "wave_character": "Ветровая волна (озёрный спот)",
        "season": "Осень",
        "wind": ["N", "NW"], "wind_text": "север, северо-запад",
        "swell": [], "swell_text": "не применяется — только ветровая волна",
        "bottom_text": "камни",
        "hazards": ["rocks", "cold_water", "weather_change"],
        "hazard_notes": "Камни, холодная вода, непредсказуемый ветер.",
        "access": "Подъезд на автомобиле, парковка.",
        "entry_exit": "Вход с каменистого берега — осторожно на скользких камнях.",
        "infrastructure": [("parking", "Парковка"), ("other", "Баня в регионе")],
        "photos": [
            ("spot-ladozhskie-shkhery-1.jpg", "Общий вид спота", "Ладожские шхеры — фото 1"),
            ("spot-ladozhskie-shkhery-2.jpg", "Линия волны и берег", "Ладожские шхеры — фото 2"),
        ],
    },
    {
        "prototype_id": "crimea",
        "slug": "olenevka",
        "name": "Оленевка",
        "region": "krym",
        "lat": "45.380000", "lng": "32.530000", "precision": "approximate",
        "short_description": "Прозрачная вода, открытый берег и красивое море под подходящие штормовые прогнозы.",
        "nature": ["Пляж", "Море", "Закаты"],
        # «Риф / пляж» → риф-брейк, пляжная часть — в характере волны.
        "difficulty": "intermediate", "bottom_type": "mixed", "break_type": "reef",
        "wave_character": "Левая и правая; риф и пляж",
        "season": "Осень — зима",
        "wind": [], "wind_text": "по прогнозу",
        "swell": [], "swell_text": "Чёрное море, работает в штормовые прогнозы",
        "bottom_text": "смешанное",
        "hazards": ["rocks", "other", "weather_change"],
        "hazard_notes": "Камни, подводные препятствия, штормовая погода.",
        "access": "Подъезд на автомобиле, парковка.",
        "entry_exit": "Вход с берега между камнями; лучше в гидрообуви.",
        "infrastructure": [("shop", "Магазин"), ("parking", "Парковка")],
        "photos": [
            ("spot-olenevka-1.jpg", "Общий вид спота", "Оленевка — фото 1"),
            ("spot-olenevka-2.jpg", "Линия волны и берег", "Оленевка — фото 2"),
            ("spot-olenevka-3.jpg", "Дополнительный ракурс", "Оленевка — фото 3"),
        ],
    },
    {
        "prototype_id": "sakh",
        "slug": "poberezhye-sakhalina",
        "name": "Побережье Сахалина",
        "region": "sakhalin",
        "lat": "46.950000", "lng": "142.740000", "precision": "approximate",
        "short_description": "Островные пейзажи, суровый океанский характер и требовательные условия.",
        "nature": ["Горы", "Морские котики", "Море"],
        "difficulty": "advanced", "bottom_type": "mixed", "break_type": "beach",
        "wave_character": "Левая и правая",
        "season": "Лето — осень",
        "wind": [], "wind_text": "по прогнозу",
        "swell": [], "swell_text": "Охотское море",
        "bottom_text": "песок и камни",
        "hazards": ["strong_current", "cold_water", "difficult_access"],
        "hazard_notes": "Течения, холодная вода, сложная логистика.",
        "access": "Нужна машина: споты разбросаны по побережью, логистика сложная.",
        "entry_exit": "Вход с пляжа; у кромки воды встречаются камни.",
        "infrastructure": [("other", "Машина необходима")],
        "photos": [
            ("spot-poberezhye-sakhalina-2.jpg", "Линия волны и берег", "Побережье Сахалина — фото"),
        ],
    },
    {
        "prototype_id": "prim",
        "slug": "poberezhye-primorya",
        "name": "Побережье Приморья",
        "region": "primorskiy-kray",
        "lat": "43.120000", "lng": "131.900000", "precision": "approximate",
        "short_description": "Красивые бухты, морской воздух и споты на разный уровень катания.",
        "nature": ["Лес", "Море", "Скалы"],
        "difficulty": "beginner", "bottom_type": "sand", "break_type": "beach",
        "wave_character": "Левая и правая",
        "season": "Лето — осень",
        "wind": [], "wind_text": "по прогнозу",
        "swell": [], "swell_text": "Японское море",
        "bottom_text": "песок",
        "hazards": ["rocks", "other", "strong_current"],
        "hazard_notes": "Скалы, лодочное движение, сезонные течения.",
        "access": "Подъезд на автомобиле.",
        "entry_exit": "Вход и выход с песчаного пляжа бухты.",
        "infrastructure": [("other", "Подъезд"), ("shop", "Магазин")],
        "photos": [
            ("spot-poberezhye-primorya-1.jpg", "Общий вид спота", "Побережье Приморья — фото 1"),
            ("spot-poberezhye-primorya-2.jpg", "Линия волны и берег", "Побережье Приморья — фото 2"),
        ],
    },
]

# --- Инструкторы и участники GG Surfer (seed_public.json → instructors, ggMembers) ----------------------------------
# Рейтинги/отзывы/сертификаты прототипа не переносятся. «Пример цены» → price_from демо-профиля.
# spot_slugs — споты каталога, к которым привязываем профиль; исходный список спотов прототипа остаётся в «О себе».
# Интересы, флаги приватности и любимые споты GG — в прототипе их нет у конкретных людей, заданы для проверки COM-02/03.
INSTRUCTORS = [
    {
        "prototype_id": "alex", "handle": "aleksey-morozov", "first_name": "Алексей", "last_name": "Морозов",
        "region": "kamchatskiy-kray", "city": "Петропавловск-Камчатский",
        "spots_text": ["Халактырский пляж", "Авачинская бухта", "Паратунка"],
        "spot_slugs": ["khalaktyrskiy-plyazh", "zaliv-anglichanka"],
        "board_types": ["shortboard", "longboard"], "riding_level": "advanced",
        "student_levels": ["beginner", "intermediate"], "students_text": "Начинающий, средний",
        "experience_years": 8, "price_from": 3800,
        "fact": "Однажды поймал волну на фоне извержения вулкана. Это было страшно и невероятно красиво одновременно!",
        "avatar": "avatar-instructor-aleksey-morozov.webp",
        "gg": True, "gg_status": "Покажу споты",
        "interests": ["Сёрфинг", "Походы", "Фотография"],
        "favorite_spots": ["khalaktyrskiy-plyazh", "zaliv-anglichanka"],
        "offers": ["individual", "group"],
    },
    {
        "prototype_id": "maria", "handle": "mariya-volkova", "first_name": "Мария", "last_name": "Волкова",
        "region": "ladozhskoe-ozero", "city": "Санкт-Петербург",
        "spots_text": ["Ладожские шхеры", "бухта Кирьявалахти", "Сортавала"],
        "spot_slugs": ["ladozhskie-shkhery"],
        "board_types": ["longboard", "funboard"], "riding_level": "intermediate",
        "student_levels": ["beginner", "intermediate"], "students_text": "Начинающий, средний",
        "experience_years": 5, "price_from": 2900,
        "fact": "Обожаю кататься в снегу и на льду. Зимой на Ладоге можно поймать ледяную волну — это не только "
                "холодно, но и про кайф!",
        "avatar": "avatar-instructor-mariya-volkova.webp",
        "gg": True, "gg_status": "Ищу компанию",
        "interests": ["Сёрфинг", "Сноуборд", "Йога", "Кофе у океана"],
        "favorite_spots": ["ladozhskie-shkhery"],
        "offers": ["individual", "pair"],
    },
    {
        "prototype_id": "dima", "handle": "dmitriy-kovalev", "first_name": "Дмитрий", "last_name": "Ковалев",
        "region": "krym", "city": "Судак",
        "spots_text": ["Балаклава", "Судак", "Оленевка"],
        "spot_slugs": ["olenevka"],
        "board_types": ["shortboard", "longboard"], "riding_level": "advanced",
        "student_levels": ["beginner", "intermediate", "advanced"], "students_text": "Любой уровень",
        "experience_years": 7, "price_from": 3400,
        "fact": "Люблю сёрфить на рассвете. В Крыму это особенно волшебно — горы, море и полное безлюдье.",
        "avatar": "avatar-instructor-dmitriy-kovalev.webp",
        "gg": True, "gg_status": "Могу подвезти",
        "interests": ["Сёрфинг", "Путешествия", "Кемпинг"],
        "favorite_spots": ["olenevka"],
        "offers": ["individual", "group"],
    },
    {
        "prototype_id": "katya", "handle": "ekaterina-sokolova", "first_name": "Екатерина", "last_name": "Соколова",
        "region": "sakhalin", "city": "Южно-Сахалинск",
        "spots_text": ["Пильтун", "Охотское море", "Южно-Сахалинск"],
        "spot_slugs": ["poberezhye-sakhalina"],
        "board_types": ["shortboard", "funboard"], "riding_level": "advanced",
        "student_levels": ["beginner", "intermediate"], "students_text": "Начинающий, средний",
        "experience_years": 6, "price_from": 3200,
        "fact": "Сёрфинг — это не только про волны, но и про знакомства. На Сахалине я нашла лучших друзей "
                "именно в воде!",
        "avatar": "avatar-instructor-ekaterina-sokolova.webp",
        "gg": True, "gg_status": "Покажу споты",
        "interests": ["Сёрфинг", "Путешествия", "Экология"],
        "favorite_spots": ["poberezhye-sakhalina"],
        # Возраст показан, поздравления разрешены — для проверки ATX-34 (дата рождения не раскрывается).
        "gg_show_age": True, "birth_date": "1994-07-14", "birthday_greetings_consent": True,
        "offers": ["individual"],
    },
    {
        "prototype_id": "ivan", "handle": "ivan-petrov", "first_name": "Иван", "last_name": "Петров",
        "region": "kamchatskiy-kray", "city": "Елизово",
        "spots_text": ["Авачинская бухта", "Тихий океан"],
        "spot_slugs": ["khalaktyrskiy-plyazh"],
        "board_types": ["shortboard", "longboard"], "riding_level": "advanced",
        "student_levels": ["intermediate", "advanced"], "students_text": "Средний, продвинутый",
        "experience_years": 10, "price_from": 3600,
        "fact": "У меня есть коллекция камней с пляжей Камчатки. Каждый — как сувенир с новой волны.",
        "avatar": "avatar-instructor-ivan-petrov.webp",
        "gg": True, "gg_status": "Могу подвезти",
        "interests": ["Сёрфинг", "Шейпинг", "Походы"],
        "favorite_spots": ["khalaktyrskiy-plyazh", "zaliv-anglichanka"],
        "offers": ["individual", "pair"],
    },
    {
        "prototype_id": "anna", "handle": "anna-lebedeva", "first_name": "Анна", "last_name": "Лебедева",
        "region": "krym", "city": "Севастополь",
        "spots_text": ["Новый Свет", "Орджоникидзе", "Кача"],
        "spot_slugs": ["olenevka"],
        "board_types": ["funboard", "longboard"], "riding_level": "intermediate",
        "student_levels": ["beginner", "intermediate"], "students_text": "Начинающий, средний",
        "experience_years": 5, "price_from": 2600,
        "fact": "В детстве мечтала стать вулканологом, а теперь изучаю волны. Наверное, всё дело в любви к стихии.",
        "avatar": "avatar-instructor-anna-lebedeva.webp",
        "gg": False, "gg_status": "Ищу компанию",
        "interests": ["Сёрфинг", "Йога", "Экология"],
        "favorite_spots": ["olenevka"],
        "offers": ["individual"],
    },
]

# Шаблоны предложений (INS-08). Цена — от «примера цены» прототипа.
OFFER_TEMPLATES = {
    "individual": {"title": "Индивидуальное занятие", "format": "individual", "capacity": 1, "price_factor": 1.0,
                   "text": "Персональное занятие: разминка и техника безопасности на берегу, затем работа в воде "
                           "с разбором каждой волны."},
    "pair": {"title": "Занятие вдвоём с другом", "format": "group", "capacity": 2, "price_factor": 0.85,
             "text": "Занятие для двоих: общая программа и внимание к каждому. Цена указана за одного участника."},
    "group": {"title": "Групповое занятие", "format": "group", "capacity": 4, "price_factor": 0.7,
              "text": "Небольшая группа до четырёх человек одного уровня. Цена указана за одного участника."},
}
LESSON_SLOTS = ["09:00", "12:00", "15:00"]  # booking.standardSlots прототипа
CLOSED_WEEKDAYS = {0, 3}  # «Пн», «Чт» — defaultClosedWeekdays
LESSON_PRICE_NOTE = "Стоимость — по договорённости с инструктором"

# --- Сёрфер (seed_cabinet.json → account.exampleUser) ------------------------------------------------------------
SURFER = {
    "email": "surfer", "handle": "sasha_wave", "first_name": "Саша", "last_name": "Волнов",
    "region": "kamchatskiy-kray", "city": "Петропавловск-Камчатский", "riding_level": "intermediate",
    "board_types": ["shortboard"], "interests": ["Сёрфинг", "Кемпинг", "Фотография"],
    "experience_years": 3,
    "bio": "Катаюсь третий сезон, ищу компанию на рассветные сессии и всегда рад подсказать дорогу к споту.",
    "favorite_spots": ["khalaktyrskiy-plyazh", "zaliv-anglichanka"],
}
# Дневник катания (COM-04/06): (дней назад, спот, мин, доска, условия, волна м, настроение, заметка, видимость)
DIARY = [
    (3, "khalaktyrskiy-plyazh", 120, "Шортборд 6'0\"", "Свелл около 1,2 м, утром офшор", "1.2", 5,
     "Чистые линии утром, к обеду раздуло. Взял пару длинных правых.", "community"),
    (10, "zaliv-anglichanka", 90, "Фанборд 7'2\"", "Мелкая волна, ветер с северо-запада", "0.6", 4,
     "Отрабатывал повороты на малой волне, дошли пешком от конного клуба.", "public"),
    (17, "khalaktyrskiy-plyazh", 150, "Шортборд 6'0\"", "Тихоокеанский свелл до 1,5 м", "1.5", 5,
     "Лучшая сессия сезона — вулканы в облаках и почти пустой лайнап.", "private"),
    (31, "poberezhye-primorya", 60, "Прокатный лонгборд 9'0\"", "Небольшая волна в бухте", "0.5", 3,
     "Поездка во Владивосток: волна маленькая, зато тёплая вода.", "public"),
]

# --- Шейперы (seed_cabinet.json → shapers.shapers) ---------------------------------------------------------------
# «Kamchatka Boards» — собственная мастерская демо-пользователя прототипа; её мастер «Иван Петров» из того же региона,
# что и инструктор Иван Петров, поэтому это один аккаунт с двумя направлениями (TZ: один пользователь — несколько
# направлений). Ширина у досок демо-мастерских в прототипе не задана — указана типичная для типа
# (отмечено в DEMO_DATA.md).
SHAPER_TYPE_CODES = {"Лонгборд": "longboard", "Шортборд": "shortboard", "Фанборд": "funboard", "Фиш": "fish",
                     "Ган": "gun", "SUP": "sup"}
AVAILABILITY = {"В наличии": "in_stock", "Под заказ": "made_to_order", "Нет в наличии": "out_of_stock"}
SHAPERS = [
    {
        "slug": "kamchatka-boards", "workshop": "Kamchatka Boards", "shaper_code": "KBA01",
        "owner": "ivan-petrov",  # аккаунт инструктора
        "region": "kamchatskiy-kray",
        "about": "Авторские доски для разных волн и стилей катания. Можно познакомиться с моделями и обсудить "
                 "параметры.",
        "experience_years": None, "specialization": ["Шортборд"],
        "custom_orders": True, "repair": False, "rental": False, "lead_time": "",
        "delivery": ["Самовывоз", "Транспортная компания"], "materials": ["Стекловолокно", "Карбон"],
        "custom_types": [],
        "models": [
            {"name": "Kamchatka Classic", "type": "Лонгборд", "length": 110, "width": "22", "thickness": "2.8",
             "volume": 65, "price": 75000, "status": "В наличии", "render": "render-longboard-wood.png"},
            {"name": "Volcano", "type": "Шортборд", "length": 73, "width": "18.5", "thickness": "2.4",
             "volume": 32, "price": 68000, "status": "В наличии", "render": "render-board-cream.png"},
            {"name": "Pacific Fish", "type": "Фиш", "length": 68, "width": "20.5", "thickness": "2.6",
             "volume": 38, "price": 62000, "status": "Под заказ", "render": "render-board-blue.png"},
            {"name": "Lava Mid", "type": "Фанборд", "length": 84, "width": "21.5", "thickness": "2.9",
             "volume": 48, "price": 69000, "status": "Нет в наличии", "render": "render-longboard-wood-2.png"},
        ],
    },
    {
        "slug": "volna-craft", "workshop": "Volna Craft", "shaper_code": "VLC01",
        "owner": {"email": "andrey.volkov", "handle": "andrey-volkov", "first_name": "Андрей", "last_name": "Волков"},
        "region": "primorskiy-kray",
        "about": "Мастерская на побережье Японского моря. Создаём доски для спокойного круизинга, повседневных волн и "
                 "индивидуальных задач райдера.",
        "experience_years": 5, "specialization": ["Лонгборд", "Фиш"],
        "custom_orders": True, "repair": True, "rental": False, "lead_time": "2–4 недели", "lead_days": 28,
        "delivery": ["Самовывоз", "Транспортная компания"], "materials": ["Стекловолокно", "Эпоксидная смола"],
        # customTypeExamples прототипа — пользовательский тип мастерской (SHP-05, ATX-07)
        "custom_types": [("mini-malibu", "Мини-малибу", "midlength")],
        "models": [
            {"name": "Ocean Soul", "type": "Лонгборд", "length": 108, "width": "22.75", "thickness": None,
             "volume": 62, "price": 79000, "status": "В наличии", "render": "render-longboard-wood.png"},
            {"name": "Marea Fish", "type": "Фиш", "length": 67, "width": "20.75", "thickness": None,
             "volume": 35, "price": 61000, "status": "Под заказ", "render": "render-board-blue.png"},
        ],
    },
    {
        "slug": "baltic-surf-lab", "workshop": "Baltic Surf Lab", "shaper_code": "BSL02",
        "owner": {"email": "evgeniya.sergeeva", "handle": "evgeniya-sergeeva", "first_name": "Евгения",
                  "last_name": "Сергеева"},
        "region": "kaliningradskaya-oblast",
        "about": "Небольшая мастерская в Калининградской области. Работаем над сбалансированными шейпами и подбираем "
                 "размеры под стиль и опыт сёрфера.",
        "experience_years": 3, "specialization": ["Шортборд", "Фанборд"],
        "custom_orders": True, "repair": False, "rental": False, "lead_time": "1–2 месяца", "lead_days": 60,
        "delivery": ["Самовывоз", "Транспортная компания"], "materials": ["Карбон", "Стекловолокно"],
        "custom_types": [],
        "models": [
            {"name": "Baltic Blue", "type": "Шортборд", "length": 74, "width": "19.25", "thickness": None,
             "volume": 34, "price": 67500, "status": "В наличии", "render": "render-board-cream.png"},
            {"name": "White Coast", "type": "Фанборд", "length": 88, "width": "21.5", "thickness": None,
             "volume": 49, "price": 72000, "status": "Под заказ", "render": "render-board-white.png"},
        ],
    },
    {
        "slug": "sakhalinskie-doski", "workshop": "Сахалинские доски", "shaper_code": "KSP03",
        "owner": {"email": "mikhail.kim", "handle": "mikhail-kim", "first_name": "Михаил", "last_name": "Ким"},
        "region": "sakhalin",
        "about": "Доски для северных побережий: устойчивость, прочность и внимание к деталям. Делаем SUP и помогаем с "
                 "подбором под условия катания.",
        "experience_years": 10, "specialization": ["SUP"],
        "custom_orders": False, "repair": True, "rental": False, "lead_time": "По договорённости",
        "delivery": ["Самовывоз"], "materials": ["Стекловолокно", "EPS / PU"],
        "custom_types": [],
        "models": [
            {"name": "North Point", "type": "SUP", "length": 120, "width": "32", "thickness": None,
             "volume": 160, "price": 93000, "status": "В наличии", "render": "render-board-blue.png"},
        ],
    },
]

# --- Школа (кабинет прототипа: примеры со скриншотов «Kamchatka Surf School», «Первое знакомство с волной») ----
SCHOOL = {
    "slug": "kamchatka-surf-school", "name": "Kamchatka Surf School", "region": "kamchatskiy-kray",
    "city": "Петропавловск-Камчатский", "spots": ["khalaktyrskiy-plyazh", "zaliv-anglichanka"],
    "short_description": "Групповые и индивидуальные занятия на Халактырском пляже и в заливе Англичанка.",
    "description": "Школа для тех, кто впервые встаёт на доску, и для продолжающих. Занятия проходят на тихоокеанском "
                   "побережье Камчатки, доска и гидрокостюм включены. Расписание переносится по погоде — инструкторы "
                   "предупредят заранее.",
    "owner": {"email": "school", "handle": "olga-severina", "first_name": "Ольга", "last_name": "Северина"},
    "manager": {"email": "manager", "handle": "pavel-gromov", "first_name": "Павел", "last_name": "Громов"},
    "instructors": ["aleksey-morozov", "ivan-petrov"],
    "cover": "hero-home.webp",
    # (название, описание, уровень, возраст, формат, мин, занятий в курсе, цена, мест)
    "programs": [
        ("Первое знакомство с волной", "Пробное занятие для тех, кто встаёт на доску впервые: безопасность, разминка "
         "на берегу и первые волны в пене.", "beginner", "all", "group", 90, 1, 4500, 6),
        ("Курс «Уверенный старт»", "Четыре занятия: от гребли и подъёма на доску до самостоятельного выбора волны.",
         "beginner", "adults", "group", 120, 4, 16000, 6),
        ("Индивидуальная тренировка", "Разбор техники один на один для продолжающих: повороты, выбор позиции в "
         "лайнапе.", "intermediate", "adults", "individual", 90, 1, 6500, 1),
        ("Детская сёрф-группа", "Игровое занятие для детей 8–13 лет на мягких досках у берега.", "beginner", "kids",
         "group", 90, 1, 3500, 5),
    ],
    "session_times": ["10:00", "13:00", "16:30"],  # sessionDefaults.time прототипа = 10:00
}

# --- Прокат (seed_public.json → rentals) ----------------------------------------------------------------------------
RENTAL = {
    "slug": "prokat-volna-ryadom", "name": "Прокат «Волна рядом»", "region": "primorskiy-kray", "city": "Владивосток",
    "short_description": "Доски и гидрокостюмы в пяти регионах — точки выдачи рядом со спотами.",
    "description": "Демонстрационный прокат: сёрфборды и гидрокостюмы на Камчатке, в Крыму, на Ладоге, Сахалине и в "
                   "Приморье. Место получения и человек, который выдаёт снаряжение, указаны в каждом объявлении.",
    "owner": {"email": "rental", "handle": "roman-belov", "first_name": "Роман", "last_name": "Белов"},
    "cover": "feature-barrel-surfer.webp",
    # спот каталога рядом с точкой выдачи
    "region_spots": {"kamchatskiy-kray": "khalaktyrskiy-plyazh", "krym": "olenevka", "sakhalin": "poberezhye-sakhalina",
                     "ladozhskoe-ozero": "ladozhskie-shkhery", "primorskiy-kray": "poberezhye-primorya"},
    # (prototypeId, slug, название, kind, регион, город, размер, цена/день, кто выдаёт, описание)
    "items": [
        ("r1", "longbord-92-sea-glass", "Лонгборд 9′2″ · Sea Glass", "board", "kamchatskiy-kray",
         "Петропавловск-Камчатский", "9′2″", 1700, "Алексей",
         "Устойчивая доска для первых длинных волн. Воск включён."),
        ("r2", "gidrokostyum-5-4-mm", "Гидрокостюм 5/4 мм", "wetsuit", "kamchatskiy-kray", "Елизово", "M", 900,
         "Иван", "Тёплый костюм для прохладной воды. Размер M."),
        ("r3", "shortbord-64-blue-current", "Шортборд 6′4″ · Blue Current", "board", "krym", "Судак", "6′4″", 1400,
         "Дмитрий", "Манёвренная доска для уверенного катания."),
        ("r4", "gidrokostyum-4-3-mm", "Гидрокостюм 4/3 мм", "wetsuit", "krym", "Севастополь", "S", 750, "Аня",
         "Мягкий неопрен и удобная посадка. Размер S."),
        ("r5", "fanbord-76-north", "Фанборд 7′6″ · North", "board", "ladozhskoe-ozero", "Сортавала", "7′6″", 1200,
         "Мария", "Комфортный вариант для ветровой волны."),
        ("r6", "gidrokostyum-6-5-mm", "Гидрокостюм 6/5 мм", "wetsuit", "sakhalin", "Южно-Сахалинск", "L", 1300,
         "Екатерина", "Тёплый вариант для холодной воды."),
        ("r7", "shortbord-510-fox", "Шортборд 5′10″ · Fox", "board", "primorskiy-kray", "Владивосток", "5′10″", 1600,
         "Максим", "Для уверенных сёрферов и быстрых поворотов."),
        ("r8", "gidrokostyum-5-4-mm-xl", "Гидрокостюм 5/4 мм · XL", "wetsuit", "primorskiy-kray", "Владивосток", "XL",
         1100, "Роман", "Размер XL, предварительная примерка."),
    ],
}

# --- Служебные аккаунты ----------------------------------------------------------------------------------------------
MODERATOR = {"email": "moderator", "handle": "gdevolna-moderator", "first_name": "Модератор", "last_name": "ГДеволны"}
ADMIN = {"email": "admin", "handle": "gdevolna-admin", "first_name": "Администратор", "last_name": "ГДеволны"}

# --- Клуб: события (через 1–6 недель) и анонсы по мотивам страницы «О нас и клуб» ------------------------------------
# (slug, название, kind, регион, спот, дней от сегодня, начало, длительность ч, мест, место, обложка, мастерская, текст)
CLUB_EVENTS = [
    ("rassvetnoe-katanie-khalaktyr", "Рассветное катание на Халактырском", "ride", "kamchatskiy-kray",
     "khalaktyrskiy-plyazh", 8, "07:00", 3, 12, "Парковка у Халактырского пляжа", "feature-volcano-coast.webp", None,
     "Встречаемся на рассвете, катаемся небольшими группами по уровню и греемся чаем из термосов. "
     "Местные сёрферы покажут, где сегодня лучше заходить в воду."),
    ("vstrecha-kluba-vladivostok", "Встреча клуба во Владивостоке", "meetup", "primorskiy-kray",
     "poberezhye-primorya", 15, "18:30", 2.5, 30, "Кофейня у набережной, точный адрес — после регистрации",
     "feature-coast-aerial.webp", None,
     "Знакомимся, делимся маршрутами по бухтам Приморья и собираем компании на ближайшие выходные. "
     "Здесь никто не чужой — приходите, даже если приехали впервые."),
    ("master-klass-vybor-doski", "Мастер-класс: как выбрать первую доску", "workshop", "kamchatskiy-kray", None, 22,
     "12:00", 3, 15, "Мастерская Kamchatka Boards", "feature-mountain-lake.webp", "kamchatka-boards",
     "Шейпер покажет, чем отличаются лонгборд, фанборд и шортборд, как читать объём и длину и что взять в "
     "аренду на первые сессии."),
    ("foto-chellendzh-olenevka", "Фото-челлендж «Свои на берегу»", "contest", "krym", "olenevka", 29, "10:00", 8,
     40, "Оленевка, сбор у маяка", "footer-landscape.webp", None,
     "Целый день снимаем друг друга в воде и на берегу. Лучшие кадры попадут в истории сообщества."),
    ("serf-trip-ladoga", "Сёрф-трип на Ладогу: осенний ветер", "trip", "ladozhskoe-ozero", "ladozhskie-shkhery", 36,
     "09:00", 57, 10, "Сбор в Сортавале", "hero-catalog.webp", None,
     "Три дня на северной воде: ловим ветровую волну у шхер, вечером — баня и разбор видео. "
     "Нужен гидрокостюм 5/4 мм — можно взять в прокате."),
]
# (название, текст, закреплено, дней назад)
CLUB_ANNOUNCEMENTS = [
    ("Клуб открывает календарь встреч",
     "Совместные катания, встречи и сёрф-трипы теперь в одном календаре. Регистрируйтесь на события — места "
     "ограничены, а за сутки до начала придёт напоминание.", True, 1),
    ("Помогаем друг другу",
     "Местный сёрфер может показать тропу, подвезти или просто составить компанию. Включите GG Surfer в профиле, "
     "чтобы вас нашли свои на берегу.", False, 3),
    ("Скоро: клубные вещи",
     "Нашивки, стикеры, флиски и термосы ГДеволна. Термосы проходят испытания удержания температуры — оставьте "
     "заявку в магазине, и мы сообщим о поступлении.", False, 6),
    ("Истории сообщества",
     "Фото-челленджи, поездки, региональные истории и маленькие победы. Первый челлендж — в Оленевке, "
     "присоединяйтесь!", False, 10),
]

# --- Магазин (TZ 24.2, SHOP-01…04): предзаказ, без оплаты и без изображений -------------------------------------------
PRODUCTS = [
    {
        "slug": "termos-gdevolna-05", "title": "Термос ГДеволна 0,5 л", "category": "thermos", "sort_order": 1,
        "description": "Компактный термос для утренней сессии: помещается в рюкзак и держит чай горячим до обеда.",
        "specs": {"Объём": "0,5 л", "Удержание тепла": "цель — не менее 12 часов",
                  "Материал": "нержавеющая сталь 18/8, двойные стенки с вакуумной изоляцией",
                  "Крышка": "герметичная, с чашкой", "Гарантия": "уточняется",
                  "Испытания": "протокол удержания температуры и герметичности — до старта продаж (SHOP-04)"},
        "variants": [("GDV-TH05-BLUE", "Глубокий синий", 2900), ("GDV-TH05-SAND", "Песочный", 2900)],
    },
    {
        "slug": "termos-gdevolna-1l", "title": "Термос ГДеволна 1 л", "category": "thermos", "sort_order": 2,
        "description": "Большой термос на всю компанию — для долгих дней на берегу и сёрф-трипов.",
        "specs": {"Объём": "1 л", "Удержание тепла": "цель — не менее 24 часов",
                  "Материал": "нержавеющая сталь 18/8, двойные стенки с вакуумной изоляцией",
                  "Крышка": "герметичная, с двумя чашками", "Гарантия": "уточняется",
                  "Испытания": "протокол удержания температуры и герметичности — до старта продаж (SHOP-04)"},
        "variants": [("GDV-TH10-BLUE", "Глубокий синий", 3900)],
    },
    {
        "slug": "fliska-kluba-gdevolna", "title": "Флиска клуба ГДеволна", "category": "apparel", "sort_order": 3,
        "description": "Тёплая флиска, чтобы согреться после воды. Клубная вещь из раздела «Что делает «Гдеволну» "
                       "особенной».",
        "specs": {"Материал": "полартек 300", "Посадка": "унисекс, свободная", "Уход": "стирка при 30 °C"},
        "variants": [("GDV-FLC-S", "Размер S", 5900), ("GDV-FLC-M", "Размер M", 5900),
                     ("GDV-FLC-L", "Размер L", 5900), ("GDV-FLC-XL", "Размер XL", 5900)],
    },
]
PRODUCT_DELIVERY_NOTE = ("Оплата и доставка появятся после запуска магазина — сейчас можно оставить заявку "
                         "«Сообщить о поступлении».")
PRODUCT_RETURNS_NOTE = "Условия возврата будут опубликованы вместе с запуском продаж."
