import os
import json
import logging
from datetime import date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest, RetryAfter
import asyncio
import redis

BOT_TOKEN = "8614524803:AAEbZ8fEaPps1j3wr09eCAa8eolvrF7nDxc"
REDIS_URL = "rediss://default:gQAAAAAAAbWlAAIgcDEwYjYyODk2ZmIyMDY0YWZkYTMzZjY0M2QyZmM0OTYwOA@lucky-tapir-112037.upstash.io:6379"
REDIS_KEY = "tax-absent-2026"

GOAL = 183
YEAR = 2026
TODAY = date(2026, 6, 3)

MONTHS_RU = ["Январь","Февраль","Март","Апрель","Май","Июнь",
             "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
MONTHS_SHORT = ["Янв","Фев","Мар","Апр","Май","Июн",
                "Июл","Авг","Сен","Окт","Ноя","Дек"]

FIXED_TEXT = "📅 Трекер дней РФ 2026\n🟢 в РФ   🔴 не в РФ   ▪️ будущее"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

rdb = redis.from_url(REDIS_URL, decode_responses=True)


def load() -> dict:
    try:
        val = rdb.get(REDIS_KEY)
        return json.loads(val) if val else {}
    except Exception as e:
        logger.error(f"Redis load error: {e}")
        return {}

def save(data: dict):
    try:
        rdb.set(REDIS_KEY, json.dumps(data))
    except Exception as e:
        logger.error(f"Redis save error: {e}")

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
    total = count_in_ru(absent)
    remaining = max(0, GOAL - total)
    rows = []

    rows.append([
        InlineKeyboardButton(f"✅ {total}/183   ⏳ осталось {remaining}", callback_data="noop"),
    ])

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
    ])

    return InlineKeyboardMarkup(rows)

async def update_keyboard(query, m: int, absent: dict):
    try:
        await query.edit_message_reply_markup(reply_markup=cal_keyboard(absent, m))
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after + 0.5)
        try:
            await query.edit_message_reply_markup(reply_markup=cal_keyboard(absent, m))
        except Exception as ex:
            logger.warning(f"retry failed: {ex}")
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            logger.warning(f"update_keyboard: {e}")

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    absent = load()
    await update.message.reply_text(
        FIXED_TEXT,
        reply_markup=cal_keyboard(absent, TODAY.month)
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

    if data == "noop":
        return

    absent = load()

    if data == "stats":
        await ctx.bot.send_message(
            chat_id=query.message.chat_id,
            text=stats_text(absent),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀ Назад к календарю", callback_data=f"m_{TODAY.month}")
            ]])
        )
        return

    if data.startswith("m_"):
        m = int(data[2:])
        await update_keyboard(query, m, absent)
        return

    if data.startswith("t_"):
        _, ms, ds = data.split("_")
        m, d = int(ms), int(ds)
        k = dkey(m, d)
        absent[k] = not absent.get(k, False)
        save(absent)
        await update_keyboard(query, m, absent)
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
