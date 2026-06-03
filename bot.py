import os
import json
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8614524803:AAEbZ8fEaPps1j3wr09eCAa8eolvrF7nDxc"
DATA_FILE = "data.json"
GOAL = 183
YEAR = 2026
TODAY = "2026-06-03"

MONTHS_RU = ["Январь","Февраль","Март","Апрель","Май","Июнь",
             "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
MONTHS_SHORT = ["Янв","Фев","Мар","Апр","Май","Июн",
                "Июл","Авг","Сен","Окт","Ноя","Дек"]

logging.basicConfig(level=logging.INFO)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_days_in_month(m):
    if m == 12:
        return 31
    return (date(YEAR, m+1, 1) - timedelta(days=1)).day

def count_in_ru(absent):
    total = 0
    for m in range(1, 13):
        for d in range(1, get_days_in_month(m)+1):
            key = f"{YEAR}-{m:02d}-{d:02d}"
            if key > TODAY:
                return total
            if not absent.get(key):
                total += 1
    return total

def make_stats_text(absent):
    total = count_in_ru(absent)
    remaining = max(0, GOAL - total)
    pct = min(100, int(total / GOAL * 100))
    today_date = date(2026, 6, 3)
    dec31 = date(2026, 12, 31)
    days_left = (dec31 - today_date).days
    per_month = -(-remaining // (days_left // 30)) if days_left > 0 and remaining > 0 else 0

    bar_filled = int(pct / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    lines = [
        f"🗓 *Трекер налогового резидентства РФ 2026*",
        f"",
        f"В стране: *{total}* из {GOAL} дней",
        f"Осталось набрать: *{remaining}* дней",
        f"До 31 декабря: *{days_left}* дней",
        f"Норма в месяц: *{per_month}* дней",
        f"",
        f"`{bar}` {pct}%",
    ]
    if remaining == 0:
        lines.append("✅ Цель достигнута!")
    return "\n".join(lines)

def make_calendar_keyboard(absent, month):
    keyboard = []
    # Month navigation row
    prev_m = month - 1 if month > 1 else 12
    next_m = month + 1 if month < 12 else 1
    keyboard.append([
        InlineKeyboardButton(f"◀ {MONTHS_SHORT[prev_m-1]}", callback_data=f"month:{prev_m}"),
        InlineKeyboardButton(f"📅 {MONTHS_RU[month-1]}", callback_data="noop"),
        InlineKeyboardButton(f"{MONTHS_SHORT[next_m-1]} ▶", callback_data=f"month:{next_m}"),
    ])
    # Day of week header
    keyboard.append([InlineKeyboardButton(d, callback_data="noop") for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]])
    # Days
    dim = get_days_in_month(month)
    first_dow = date(YEAR, month, 1).weekday()  # 0=Mon
    row = [InlineKeyboardButton(" ", callback_data="noop")] * first_dow
    for d in range(1, dim+1):
        key = f"{YEAR}-{month:02d}-{d:02d}"
        is_future = key > TODAY
        is_absent = absent.get(key, False)
        is_today = key == TODAY
        if is_future:
            label = f"·{d}"
        elif is_absent:
            label = f"✗{d}"
        elif is_today:
            label = f"[{d}]"
        else:
            label = f"✓{d}"
        cb = "noop" if is_future else f"toggle:{month}:{d}"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        while len(row) < 7:
            row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)
    # Bottom buttons
    keyboard.append([
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("🔄 Обновить", callback_data=f"month:{month}"),
    ])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    absent = load_data()
    text = make_stats_text(absent)
    keyboard = [[InlineKeyboardButton("📅 Открыть календарь", callback_data="month:1")]]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    absent = load_data()

    if data == "noop":
        return

    if data == "stats":
        text = make_stats_text(absent)
        keyboard = [[InlineKeyboardButton("📅 Календарь", callback_data="month:1")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("month:"):
        month = int(data.split(":")[1])
        kb = make_calendar_keyboard(absent, month)
        try:
            await query.edit_message_text(f"📅 *{MONTHS_RU[month-1]} {YEAR}*\n✓ в РФ  ✗ не в РФ  · будущее", parse_mode="Markdown", reply_markup=kb)
        except:
            pass
        return

    if data.startswith("toggle:"):
        _, month, day = data.split(":")
        key = f"{YEAR}-{int(month):02d}-{int(day):02d}"
        absent[key] = not absent.get(key, False)
        save_data(absent)
        month = int(month)
        kb = make_calendar_keyboard(absent, month)
        try:
            await query.edit_message_reply_markup(reply_markup=kb)
        except:
            pass
        return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == "__main__":
    main()
