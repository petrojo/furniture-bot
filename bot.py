# bot.py
import asyncio
import os
import math
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

# ========== CONFIG ==========
TOKEN = "8282353074:AAGSK7Vqs1s3zFJF5C6wZdmM7i3TnTrIsmI"
MANAGER_CHAT_ID = 1732149

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "images")  # line.png, l_shape.png, u_shape.png

# ========== PRICES (СУМЫ) ==========
KITCHEN_PRICE_PER_M = {
    "ЛДСП": 3_400_000,
    "ЛДСП премиум (суперматовые и акриловые декоры)": 3_900_000,
    "Плёночные фасады": 4_900_000,
    "Эмаль": 7_100_000,
    "Шпонированные фасады": 9_100_000,
}

TOP_PRICES = {
    "Не нужна": 0,
    "ЛДСП": None,
    "Акриловая": 1_850_000,
    "Кварцевый агломерат": 2_500_000,
    "Керамогранит (формат 1800×600)": 2_500_000,
}

LDSP_TOP_SMALL_KITCHEN = 1_500_000
LDSP_TOP_LARGE_KITCHEN = 3_000_000

WARDROBE_PRICE_PER_M = {
    "ЛДСП": 4_900_000,
    "ЛДСП премиум (суперматовые и акриловые декоры)": 5_100_000,
    "Плёночные фасады": 7_200_000,
    "Эмаль": 9_300_000,
    "Шпонированные фасады": 10_600_000,
}
WARDROBE_LIGHT_PRICE = 2_400_000

ISLAND_SURCHARGE = 1.15
DEFAULT_ISLAND_LEN_CM = 210

# ========== FSM ==========
class KStates(StatesGroup):
    choose_form = State()
    len_a = State()
    len_b = State()
    len_c = State()
    facade = State()
    upper_q = State()
    top = State()
    island_q = State()
    island_type = State()
    island_len = State()
    phone = State()


class WStates(StatesGroup):
    length = State()
    height = State()
    facade = State()
    light = State()
    phone = State()


# ========== Keyboards ==========
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Кухня"), KeyboardButton(text="Шкаф")]],
        resize_keyboard=True,
    )


def shape_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Прямая"), KeyboardButton(text="Угловая"), KeyboardButton(text="П-образная")],
            [KeyboardButton(text="Начать сначала")],
        ],
        resize_keyboard=True,
    )


def restart_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Начать сначала")]],
        resize_keyboard=True,
    )


def yes_no_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
        resize_keyboard=True,
    )


def facade_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=x)] for x in KITCHEN_PRICE_PER_M.keys()],
        resize_keyboard=True,
    )


def top_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=x)] for x in TOP_PRICES.keys()],
        resize_keyboard=True,
    )


def wardrobe_facade_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=x)] for x in WARDROBE_PRICE_PER_M.keys()],
        resize_keyboard=True,
    )


def phone_request_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Оставить номер", request_contact=True)],
            [KeyboardButton(text="Начать сначала")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ========== Helpers ==========
def parse_int_cm(text: str):
    if not text:
        return None
    s = text.strip()
    return int(s) if s.isdigit() else None


def round_thousand(n: float) -> int:
    return int(math.ceil(n / 1000.0) * 1000)


def img_path(name: str) -> str:
    return os.path.join(IMAGES_DIR, name)


# ========== Bot setup ==========
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)


# ========== Handlers ==========
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! 👋\n"
        "Я бот компании «Честная мебель» и помогу рассчитать ориентировочную стоимость твоей мебели.\n\n"
        "Что считаем?",
        reply_markup=main_kb(),
    )


@router.message(F.text == "Начать сначала")
async def global_restart(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message, state)


# --- Kitchen flow ---
@router.message(F.text == "Кухня")
async def kitchen_start(message: Message, state: FSMContext):
    # clear any previous FSM state so кнопка всегда работает
    await state.clear()
    await state.set_state(KStates.choose_form)
    await message.answer("Выберите форму кухни:", reply_markup=shape_kb())


@router.message(KStates.choose_form)
async def kitchen_choose_form(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text not in ("Прямая", "Угловая", "П-образная"):
        await message.answer("Выберите форму кнопкой.", reply_markup=shape_kb())
        return

    await state.update_data(form=text)

    mapping = {
        "Прямая": "line.png",
        "Угловая": "l_shape.png",
        "П-образная": "u_shape.png",
    }
    name = mapping[text]
    path = img_path(name)
    if not os.path.exists(path):
        await message.answer(
            "Ошибка: не найдена картинка для этой формы. Убедитесь, что файлы line.png, l_shape.png, u_shape.png лежат в папке images рядом с bot.py."
        )
        return

    await message.answer_photo(
        FSInputFile(path),
        caption="Схема кухни — обозначены стороны. После выбора формы введите длину стороны A (в сантиметрах).",
        reply_markup=restart_kb(),
    )

    await state.set_state(KStates.len_a)


@router.message(KStates.len_a)
async def kitchen_len_a(message: Message, state: FSMContext):
    if message.text == "Начать сначала":
        await global_restart(message, state)
        return

    v = parse_int_cm(message.text)
    if v is None:
        await message.answer("Введите только цифры, без букв. Например: 180")
        return

    await state.update_data(A_cm=v)
    data = await state.get_data()
    form = data.get("form")

    # For straight kitchen -> go to facade selection
    if form == "Прямая":
        await message.answer("Выберите материал фасадов:", reply_markup=facade_kb())
        await state.set_state(KStates.facade)
        return

    # For corner and U-shape -> ask B
    await message.answer("Введите длину стороны B в сантиметрах:", reply_markup=restart_kb())
    await state.set_state(KStates.len_b)


@router.message(KStates.len_b)
async def kitchen_len_b(message: Message, state: FSMContext):
    if message.text == "Начать сначала":
        await global_restart(message, state)
        return

    v = parse_int_cm(message.text)
    if v is None:
        await message.answer("Введите только цифры, без букв. Например: 180")
        return

    await state.update_data(B_cm=v)
    data = await state.get_data()
    form = data.get("form")

    # If corner -> proceed to facade selection
    if form == "Угловая":
        await message.answer("Выберите материал фасадов:", reply_markup=facade_kb())
        await state.set_state(KStates.facade)
        return

    # If U-shape -> ask C
    await message.answer("Введите длину стороны C в сантиметрах:", reply_markup=restart_kb())
    await state.set_state(KStates.len_c)


@router.message(KStates.len_c)
async def kitchen_len_c(message: Message, state: FSMContext):
    if message.text == "Начать сначала":
        await global_restart(message, state)
        return

    v = parse_int_cm(message.text)
    if v is None:
        await message.answer("Введите только цифры, без букв. Например: 180")
        return

    await state.update_data(C_cm=v)
    await message.answer("Выберите материал фасадов:", reply_markup=facade_kb())
    await state.set_state(KStates.facade)


@router.message(KStates.facade)
async def kitchen_facade(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text not in KITCHEN_PRICE_PER_M:
        await message.answer("Выберите фасад кнопкой.", reply_markup=facade_kb())
        return

    await state.update_data(facade=text)
    await message.answer("Будут ли верхние шкафы? (Да/Нет)", reply_markup=yes_no_kb())
    await state.set_state(KStates.upper_q)


@router.message(KStates.upper_q)
async def kitchen_upper(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text not in ("Да", "Нет"):
        await message.answer("Выберите Да или Нет.", reply_markup=yes_no_kb())
        return

    await state.update_data(upper=(text == "Да"))
    await message.answer("Выберите столешницу:", reply_markup=top_kb())
    await state.set_state(KStates.top)


@router.message(KStates.top)
async def kitchen_top(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text not in TOP_PRICES:
        await message.answer("Выберите столешницу кнопкой.", reply_markup=top_kb())
        return

    await state.update_data(top=text)
    await message.answer("Нужен остров/полуостров? (Да/Нет)", reply_markup=yes_no_kb())
    await state.set_state(KStates.island_q)


@router.message(KStates.island_q)
async def kitchen_island_q(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text not in ("Да", "Нет"):
        await message.answer("Выберите Да или Нет.", reply_markup=yes_no_kb())
        return

    has_island = (text == "Да")
    await state.update_data(has_island=has_island)
    if not has_island:
        await compute_and_send_kitchen_result(message, state)
        # DO NOT clear state here: keep data until user shares contact
        await state.set_state(KStates.phone)
        return

    # ask island type
    await message.answer(
        "Остров или полуостров?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Остров"), KeyboardButton(text="Полуостров")]],
            resize_keyboard=True,
        ),
    )
    await state.set_state(KStates.island_type)


@router.message(KStates.island_type)
async def kitchen_island_type(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text not in ("Остров", "Полуостров"):
        await message.answer("Выберите Остров или Полуостров.")
        return

    await state.update_data(island_type=text)
    await message.answer(
        f"Укажите длину {text.lower()}а в сантиметрах (например {DEFAULT_ISLAND_LEN_CM}):",
        reply_markup=restart_kb(),
    )
    await state.set_state(KStates.island_len)


@router.message(KStates.island_len)
async def kitchen_island_len(message: Message, state: FSMContext):
    v = parse_int_cm(message.text)
    if v is None:
        await message.answer("Введите только цифры, без букв. Например: 180")
        return

    await state.update_data(island_len_cm=v)
    await compute_and_send_kitchen_result(message, state)
    # keep state so user can send contact
    await state.set_state(KStates.phone)


async def compute_and_send_kitchen_result(message: Message, state: FSMContext):
    data = await state.get_data()
    a = data.get("A_cm", 0) or 0
    b = data.get("B_cm", 0) or 0
    c = data.get("C_cm", 0) or 0
    total_cm = a + b + c
    total_m = total_cm / 100.0

    facade = data.get("facade")
    base_price_per_m = KITCHEN_PRICE_PER_M.get(facade, 0)

    upper = data.get("upper", True)
    effective_price_per_m = base_price_per_m * 0.75 if not upper else base_price_per_m

    kitchen_cost = effective_price_per_m * total_m

    top_choice = data.get("top")
    top_cost = 0
    if top_choice == "Не нужна":
        top_cost = 0
    elif top_choice == "ЛДСП":
        top_cost = LDSP_TOP_SMALL_KITCHEN if total_cm <= 400 else LDSP_TOP_LARGE_KITCHEN
    else:
        per_m = TOP_PRICES.get(top_choice, 0) or 0
        top_cost = per_m * total_m

    island_cost = 0
    island_top_cost = 0
    if data.get("has_island"):
        island_len_cm = data.get("island_len_cm", DEFAULT_ISLAND_LEN_CM)
        island_len_m = island_len_cm / 100.0
        price_per_m_no_upper = base_price_per_m * 0.75
        island_base = price_per_m_no_upper * island_len_m
        island_cost = island_base * ISLAND_SURCHARGE
        if top_choice == "Не нужна":
            island_top_cost = 0
        elif top_choice == "ЛДСП":
            island_top_cost = island_len_m * (LDSP_TOP_SMALL_KITCHEN if total_cm <= 400 else LDSP_TOP_LARGE_KITCHEN)
        else:
            per_m = TOP_PRICES.get(top_choice, 0) or 0
            island_top_cost = per_m * island_len_m

    total = kitchen_cost + top_cost + island_cost + island_top_cost
    total = round_thousand(total)

    # prepare lines exactly like before
    lines = [
        "— Результат расчёта кухни —",
        f"Форма: {data.get('form')}",
        f"A: {a} см, B: {b} см, C: {c} см",
        f"Суммарно: {total_cm} см ({total_m:.2f} м)",
        f"Фасады: {facade} (базовая цена {base_price_per_m:,} сум/м)".replace(",", " "),
        f"Верхние шкафы: {'Да' if upper else 'Нет'}",
        f"Базовая стоимость по фасаду: {int(kitchen_cost):,} сум".replace(",", " "),
        f"Столешница ({top_choice}): {int(top_cost):,} сум".replace(",", " "),
    ]
    if island_cost:
        lines.append(f"Остров (базовая+{int((ISLAND_SURCHARGE-1)*100)}%): {int(island_cost):,} сум".replace(",", " "))
        lines.append(f"Столешница острова: {int(island_top_cost):,} сум".replace(",", " "))
    lines.append(f"ИТОГО: {int(total):,} сум".replace(",", " "))

    # Save summary and total to state so contact handler can send full info
    await state.update_data(calc_lines=lines, calc_total=int(total))

    # prompt for phone — use request_contact button
    await message.answer("\n".join(lines) + "\n\nЕсли хотите более точный расчёт и обсуждение проекта, оставьте номер телефона.", reply_markup=phone_request_kb())


# --- Wardrobe flow ---
@router.message(F.text == "Шкаф")
async def wardrobe_start(message: Message, state: FSMContext):
    # clear any previous FSM state so кнопка всегда работает
    await state.clear()
    await state.set_state(WStates.length)
    await message.answer("Введите длину шкафа в сантиметрах (см):", reply_markup=ReplyKeyboardRemove())


@router.message(WStates.length)
async def wardrobe_length(message: Message, state: FSMContext):
    if message.text == "Начать сначала":
        await global_restart(message, state)
        return
    v = parse_int_cm(message.text)
    if v is None:
        await message.answer("Введите только цифры, без букв. Например: 120")
        return
    await state.update_data(length_cm=v)
    await message.answer("Введите высоту шкафа в сантиметрах (см):")
    await state.set_state(WStates.height)


@router.message(WStates.height)
async def wardrobe_height(message: Message, state: FSMContext):
    if message.text == "Начать сначала":
        await global_restart(message, state)
        return
    v = parse_int_cm(message.text)
    if v is None:
        await message.answer("Введите только цифры, без букв. Например: 240")
        return
    await state.update_data(height_cm=v)
    await message.answer("Выберите фасады для шкафа:", reply_markup=wardrobe_facade_kb())
    await state.set_state(WStates.facade)


@router.message(WStates.facade)
async def wardrobe_facade(message: Message, state: FSMContext):
    if message.text not in WARDROBE_PRICE_PER_M:
        await message.answer("Выберите фасад кнопкой.", reply_markup=wardrobe_facade_kb())
        return
    await state.update_data(facade=message.text)
    await message.answer("Нужна подсветка? (Да/Нет)", reply_markup=yes_no_kb())
    await state.set_state(WStates.light)


@router.message(WStates.light)
async def wardrobe_light(message: Message, state: FSMContext):
    if message.text == "Начать сначала":
        await global_restart(message, state)
        return
    if message.text not in ("Да", "Нет"):
        await message.answer("Выберите Да или Нет.", reply_markup=yes_no_kb())
        return
    await state.update_data(light=(message.text == "Да"))

    data = await state.get_data()
    length_m = data["length_cm"] / 100.0
    height_cm = data["height_cm"]
    facade = data["facade"]
    price_per_m = WARDROBE_PRICE_PER_M.get(facade, 0)

    cost = price_per_m * length_m
    if height_cm > 280:
        cost *= 1.20
    if data.get("light"):
        cost += WARDROBE_LIGHT_PRICE

    total = round_thousand(cost)

    lines = [
        "— Результат расчёта шкафа —",
        f"Длина: {data['length_cm']} см",
        f"Высота: {height_cm} см",
        f"Фасады: {facade}",
        f"Подсветка: {'Да' if data.get('light') else 'Нет'}",
        f"ИТОГО: {int(total):,} сум".replace(",", " "),
    ]

    # save to state for manager
    await state.update_data(calc_lines=lines, calc_total=int(total))

    await message.answer("\n".join(lines) + "\n\nЕсли хотите более точный расчёт и обсуждение проекта, оставьте номер телефона.", reply_markup=phone_request_kb())
    await state.set_state(WStates.phone)


# ========== CONTACT handler ==========
@router.message(F.contact)
async def handle_contact(message: Message, state: FSMContext):
    data = await state.get_data() or {}
    user = message.from_user
    username = f"@{user.username}" if user.username else f"id:{user.id}"
    phone = message.contact.phone_number

    # Build readable summary
    summary_lines = [f"📥 Заявка от {username}", f"📞 Номер: {phone}", "Параметры:"]

    # include kitchen data if present
    if data.get("form") or data.get("A_cm") is not None:
        summary_lines.append("Тип: Кухня")
        summary_lines.append(f"Форма: {data.get('form', '-')}")
        summary_lines.append(f"A: {data.get('A_cm', '-') } см")
        summary_lines.append(f"B: {data.get('B_cm', '-') } см")
        summary_lines.append(f"C: {data.get('C_cm', '-') } см")
        summary_lines.append(f"Фасад: {data.get('facade', '-')}")
        summary_lines.append(f"Верхние шкафы: {'Да' if data.get('upper') else 'Нет'}")
        summary_lines.append(f"Столешница: {data.get('top', '-')}")
        if data.get('has_island'):
            summary_lines.append(f"Остров: {data.get('island_type', '-')}, длина: {data.get('island_len_cm', DEFAULT_ISLAND_LEN_CM)} см")
    elif data.get("length_cm") is not None:
        summary_lines.append("Тип: Шкаф")
        summary_lines.append(f"Длина: {data.get('length_cm')} см")
        summary_lines.append(f"Высота: {data.get('height_cm')} см")
        summary_lines.append(f"Фасад: {data.get('facade', '-')}")
        summary_lines.append(f"Подсветка: {'Да' if data.get('light') else 'Нет'}")
    else:
        # fallback: if we have calc_lines from earlier, include them
        if data.get("calc_lines"):
            summary_lines.extend(data.get("calc_lines"))

    # include total if present
    if data.get("calc_total") is not None:
        summary_lines.append("")
        summary_lines.append(f"ИТОГО: {data.get('calc_total'):,} сум".replace(",", " "))

    summary_text = "\n".join(summary_lines)

    try:
        await bot.send_message(MANAGER_CHAT_ID, summary_text)
    except Exception as e:
        logging.exception("Failed to send manager message: %s", e)

    await message.answer("Отлично! Мы вам перезвоним в ближайшее время", reply_markup=main_kb())
    await state.clear()


# Fallback
@router.message()
async def fallback(message: Message, state: FSMContext):
    await message.answer("Не распознал ввод. Используй меню.", reply_markup=main_kb())


# ========== Run ==========
async def main():
    print("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
