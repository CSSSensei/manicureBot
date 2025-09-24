<h1 align="center">💅 <a href="https://t.me/Nude_n_red_bot">nails.simple</a> Telegram bot </h1>
<p align="center">
<b>Запись на ноготочки только тут. Красиво, как всегда</b>

</p><p align="center">
<img src="https://img.shields.io/badge/made%20by-CSSSensei-FF00FF" >
<img src="https://img.shields.io/badge/Phasalopedia-FF69B4">
<img src="https://img.shields.io/badge/version-v1.5.1-C71585">
</p>

<p><p align="center">
Русский | [English](README.md)
</p>

> ### SMI Core
> powered by [**aiogram**](https://docs.aiogram.dev/) | Clean UX | Async swag\
> FSM-driven logic | Modular callbacks | Fully scalable  
> Type-safe handlers, sleek keyboards, zero spaghetti 🧘\
> Plug & play architecture with room for growth\
> Swagger not included — it’s built-in 😎

---

## ⚙️ Стэк

- 🐍 Python 3.11+
- 🤖 [aiogram 3.x](https://docs.aiogram.dev/) — асинхронный Telegram-фреймворк  
- 🛠️ SQLite — лёгкая база данных, с абстракциями в стиле SQLAlchemy  
- 📚 FSM — тонкая настройка управления состояниями  
- 🔗 YAML — для фраз и i18n  
- 🧪 Pytest — тесты, как положено

---

## ✨ Фичи

- ⚡ **Асинхронный и быстрый** — все взаимодействия неблокирующие
- 📍 **FSM (конечный автомат состояний)** — контекстно-зависимые сценарии пользователя
- 🔘 **Модульность коллбэков** — хендлеры разделены по ролям и доменам
- 🎛️ **Система клавиатур** — inline, reply, контекстные, структурированные
- 🧩 **Масштабируемая структура проекта** — удобно подключать модули
- 🗂️ **YAML-фразник** — простой i18n/фразинг в `phrases/`
- 🧪 **Тестируемый** — отдельная папка `tests/` с готовым Pytest

---

## 📁 Структура проекта

```
manicureBot/
│
├── bot/                       # Основная логика бота
│   ├── handlers/              # Все хендлеры и коллбэки
│   │   ├── callbacks/         # По фичам: админ, мастер, пользователь
│   │   └── ...
│   ├── keyboards/             # Клавиатуры Telegram
│   │   ├── admin/
│   │   ├── master/
│   │   └── default/
│   ├── middlewares/           # Кастомные миддлвары
│   │   ├── get_user.py
│   │   ├── shadow_ban.py
│   │   └── logging_query.py
│   ├── bot_utils/             # Вспомогательные файлы бота
│   └── ...
│
├── DB/                        # SQLite интерфейс и модели
│   ├── tables/                # По файлу на таблицу
│   ├── models.py              # Data models (DTO-подобные)
│   └── ...
│
├── config/                    # Конфигурация бота (env, константы и т.д.)
├── logs/                      # Логи (TBD)
├── phrases/                   # Фразы на YAML
├── temp/                      # Временные данные / состояния / дампы
├── tests/                     # Тесты на Pytest
├── utils/                     # Общие утилиты
├── main.py                    # Точка входа
├── .env / .env.example        # Переменные окружения
└── README.md                  # Ты здесь 😎
```

---

## 🧪 Как запустить

### 1. 📦 Установите зависимости
```bash
pip install -r requirements.txt
```

### 2. ⚙️ Настройте .env
Скопируйте и отредактируйте переменные:
```bash
cp .env.example .env
```

### 3. 🚀 Запустите бота
```bash
python main.py
```

### 4. 🧪 Запустите тесты
```bash
pytest
```

---

## 🌀 В разработке

ManicureBot постоянно развивается. Новые FSM-сценарии, модули и улучшения UX всегда в процессе разработки.

<p align="center">
  <img width="1248" height="592" alt="Phasalo" src="https://github.com/user-attachments/assets/6e508ad9-b9f9-4af6-8322-9756c589d39f" />
</p>

<p align="center">
<b>Phasalo</b><br>
<i>Делаем красиво!</i><br><br>
2025
</p>
