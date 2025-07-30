<h1 align="center">💅 nails.simple telegram bot </h1>
<p align="center">
Запись на ноготочки только тут. Красиво, как всегда
</p><p align="center">
<img src="https://img.shields.io/badge/made%20by-CSSSensei-FF00FF" >
<img src="https://img.shields.io/badge/Phasalopedia-FF69B4">
<img src="https://img.shields.io/badge/version-v1.0.1-C71585">
</p>

> ### SMI Core
> powered by [**aiogram**](https://docs.aiogram.dev/) | Clean UX | Async swag\
> FSM-driven logic | Modular callbacks | Fully scalable  
> Type-safe handlers, sleek keyboards, zero spaghetti 🧘\
> Plug & play architecture with room for growth\
> Swagger not included — it’s built-in 😎

---

## ⚙️ Tech Stack

- 🐍 Python 3.11+
- 🤖 [aiogram 3.x](https://docs.aiogram.dev/) — async-first Telegram framework  
- 🛠️ SQLite — lightweight DB, backed by SQLAlchemy-style abstractions  
- 📚 FSM — finely tuned state management  
- 🔗 YAML — for phrases and i18n vibes  
- 🧪 Pytest — tested like your frontend should be

---

## ✨ Features

- ⚡ **Asynchronous & fast** — all interactions are non-blocking
- 📍 **Finite State Machine (FSM)** — context-aware user flows
- 🔘 **Callback modularity** — handlers cleanly split by role & domain
- 🎛️ **Keyboard system** — inline, reply, contextual, structured
- 🧩 **Scalable project layout** — plug in your modules, stay zen
- 🗂️ **YAML phrasebook** — simple i18n/phrasing in `phrases/`
- 🧪 **Testable** — separated `tests/`, with ready-to-run Pytest

---

## 📁 Project Structure

```
manicureBot/
│
├── bot/                       # Core bot logic
│   ├── handlers/              # All handlers & callbacks
│   │   ├── callbacks/         # Split by feature: admin, master, user
│   │   └── ...
│   ├── keyboards/             # Structured Telegram keyboards
│   │   ├── admin/
│   │   ├── master/
│   │   └── default/
│   ├── middlewares/             # Custom middlewares for bot processing
│   │   ├── get_user.py
│   │   ├── shadow_ban.py
│   │   └── logging_query.py
│   └── ...
│
├── DB/                        # SQLite interface & models
│   ├── tables/                # One file per table
│   ├── models.py              # Data models (DTO-like)
│   └── ...
│
├── config/                    # Bot configuration (env, consts, etc.)
├── logs/                      # Logging setup (TBD)
├── phrases/                   # YAML-based phrasebook
├── temp/                      # Temp data / states / dumps
├── tests/                     # Pytest modules
├── utils/                     # Shared formatting utilities
├── main.py                    # Entry point
├── .env / .env.example        # Environment variables
└── README.md                  # You're here 😎
```

---

## 🧪 How to Run

### 1. 📦 Install dependencies
```bash
pip install -r requirements.txt
```

### 2. ⚙️ Set up .env
Copy and edit your variables:
```bash
cp .env.example .env
```

### 3. 🚀 Run the bot
```bash
python main.py
```

### 4. 🧪 Run tests
```bash
pytest
```

---

## 🌀 Work in Progress

ManicureBot is constantly evolving. New FSM flows, modules, and UX enhancements are always brewing in `dev`.

<p align="center">
  <img src="https://yan-toples.ru/Phasalo/phasalopedia_logo_negative.png" width="1500" alt="Phasalo">
</p>

<p align="center">
<b>Phasalopedia</b><br>
<i>Делаем красиво!</i><br><br>
2025
</p>
