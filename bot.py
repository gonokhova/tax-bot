import os
import json
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8614524803:AAEbZ8fEaPps1j3wr09eCAa8eolvrF7nDxc"
DATA_FILE = "/app/data.json"
GOAL = 183
YEAR = 2026
TODAY = date(2026, 6, 3)

MONTHS_RU = ["Январь","Февраль","Март","Апрель","Май","Июнь",
             "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
MONTHS_SHORT = ["Янв","Фев","Мар","Апр","Май","Июн",
                "Июл","Авг","Сен","Окт","Ноя","Дек"]

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def load() -> dict:
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def dim(m: int) -> int:
    if m == 12:
        return 31
    return (date(YEAR, m + 1, 1) - timedelta(days=1)).day

def dkey(m: int, d: int) -> str:
    return f"{YEAR}-{m:02d}-{d:02d}"

def count_in_ru(absent: dict) -> int:
    today_str = TODAY.isoformat()
    total = 0
    for m in range(1, 13):
        for d in range(1, dim(m) + 1):
            k = dkey(m, d)
            if k > today_str:
                return total
            if not absent.get(k, False):
                total += 1
    return total

def stats_text(absent: dict) -> str:
    total = count_in_ru(absent)
    remaining = max(0, GOAL - total)
    pct = min(100, round(total / GOAL * 100))
    days_left = (date(YEAR, 12, 31) - TODAY).days
    months_left = days_left / 30
    per_month = -(-remaining // round(months_left)) if months_left > 0 and remaining > 0 else 0
    filled = round(pct / 5)
    bar = "█" * filled + "░" * (20 - filled)
    lines = [
        "🗓 *Трекер налогового резидентства РФ 2026*", "",
        f"✅ В стране: *{total}* из {GOAL} дней",
        f"⏳ Осталось набрать: *{remaining}* дней",
        f"📆 До 31 декабря: *{days_left}* дней",
        f"📊 Норма в месяц: *{per_month}* дней", "",
        f"`{bar}` {pct}%",
    ]
    if remaining == 0:
        lines.append("\n🎉 Цель достигнута!")
    return "\n".join(lines)

def cal_keyboard(absent: dict, m: int) -> InlineKeyboardMarkup:
    today_str = TODAY.isoformat()
    rows = []
    prev_m = 12 if m == 1 else m - 1
    next_m = 1 if m == 12 else m + 1
    rows.append([
        InlineKeyboardButton(f"◀ {MONTHS_SHORT[prev_m-1]}", callback_data=f"m_{prev_m}"),
        InlineKeyboardButton(f"· {MONTHS_RU[m-1]} ·", callback_data="noop"),
        InlineKeyboardButton(f"{MONTHS_SHORT[next_m-1]} ▶", callback_data=f"m_{next_m}"),
    ])
    rows.append([InlineKeyboardButton(d, callback_data="noop") for d in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]])
    first_dow = date(YEAR, m, 1).weekday()
    row = [InlineKeyboardButton(" ", callback_data="noop")] * first_dow
    for d in range(1, dim(m) + 1):
        k = dkey(m, d)
        is_future = k > today_str
        is_absent = absent.get(k, False)
        if is_future:
            label = f"▪️{d}"
            cb = "noop"
        elif is_absent:
            label = f"🔴{d}"
            cb = f"t_{m}_{d}"
        else:
            label = f"🟢{d}"
            cb = f"t_{m}_{d}"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 7:
            rows.append(row)
            row = []
    if row:
        row += [InlineKeyboardButton(" ", callback_data="noop")] * (7 - len(row))
        rows.append(row)
    rows.append([
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("🔄 Обновить", callback_data=f"m_{m}"),
    ])
    return InlineKeyboardMarkup(rows)

def cal_text(m: int) -> str:
    return f"📅 *{MONTHS_RU[m-1]} {YEAR}*\n🟢 в РФ   🔴 не в РФ   ▪️ будущее"

async def send_calendar(chat_id, m, absent, bot):
    """Always send a fresh message — never edit, so state is always clear."""
    await bot.send_message(
        chat_id=chat_id,
        text=cal_text(m),
        parse_mode="Markdown",
        reply_markup=cal_keyboard(absent, m)
    )

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    absent = load()
    await update.message.reply_text(
        stats_text(absent),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📅 Открыть календарь", callback_data=f"m_{TODAY.month}")
        ]])
    )

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    absent = load()
    await update.message.reply_text(
        stats_text(absent),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📅 Открыть календарь", callback_data=f"m_{TODAY.month}")
        ]])
    )

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data == "noop":
        return

    absent = load()

    if data == "stats":
        await ctx.bot.send_message(
            chat_id=chat_id,
            text=stats_text(absent),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📅 Открыть календарь", callback_data=f"m_{TODAY.month}")
            ]])
        )
        return

    if data.startswith("m_"):
        m = int(data[2:])
        await send_calendar(chat_id, m, absent, ctx.bot)
        return

    if data.startswith("t_"):
        _, ms, ds = data.split("_")
        m, d = int(ms), int(ds)
        k = dkey(m, d)
        absent[k] = not absent.get(k, False)
        save(absent)
        # Send fresh calendar so state is 100% clear
        await send_calendar(chat_id, m, absent, ctx.bot)
        return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(on_button))
    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
