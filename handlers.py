from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import html
import re
import tempfile
from pathlib import Path
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards import (
    get_main_menu, get_categories_keyboard, get_settings_menu,
    get_settings_action_menu, get_delete_category_keyboard, get_cancel_keyboard,
    get_undo_keyboard, get_subscriptions_menu, get_delete_subscription_keyboard,
    get_templates_keyboard, get_templates_settings_menu, get_delete_template_keyboard,
    get_recent_records_keyboard, get_record_actions_keyboard, get_record_delete_confirm_keyboard
)
from storage import storage
from subscriptions_storage import sub_storage
from templates_storage import templates_storage
from database import records_db
from excel_utils import export_filename, write_records_xlsx
from filters import PrivateUserFilter

undo_cache = {}


def h(value) -> str:
    return html.escape(str(value), quote=False)

def format_money(amount: float) -> str:
    return f"{float(amount):,.2f}".replace(",", " ")

def format_record_details(record: dict) -> str:
    sign = "+" if record["type"] == "Доход" else "-"
    comment = h(record.get("comment") or "-")
    return (
        f"<b>Операция #{record['id']}</b>\n\n"
        f"Дата: <b>{h(record['date'])}</b>\n"
        f"Время: <b>{h(record['time'])}</b>\n"
        f"Тип: <b>{h(record['type'])}</b>\n"
        f"Сумма: <b>{sign}{format_money(record['amount'])}</b>\n"
        f"Категория: <b>{h(record['category'])}</b>\n"
        f"Комментарий: <i>{comment}</i>"
    )

router = Router()
router.message.filter(PrivateUserFilter())
router.callback_query.filter(PrivateUserFilter())

# States
class OperationState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()

class SettingsState(StatesGroup):
    waiting_for_new_category = State()

class TemplateUseState(StatesGroup):
    waiting_for_amount = State()

class TemplateState(StatesGroup):
    waiting_for_name = State()
    waiting_for_comment = State()
    waiting_for_type = State()
    waiting_for_category = State()

class RecentRecordState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_comment = State()

class SubState(StatesGroup):
    waiting_for_name = State()
    waiting_for_amount = State()
    waiting_for_type = State()
    waiting_for_category = State()
    waiting_for_date = State()

# --- General Handlers ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Добро пожаловать в финансовый бот! Выберите действие:", reply_markup=get_main_menu())

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "cancel_operation")
async def cb_cancel_inline(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()

@router.message(F.text == "Отмена ❌")
async def cmd_cancel(message: Message, state: FSMContext):
    try: await message.delete()
    except Exception: pass
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_main_menu())

# --- Operations (Income / Expense) ---

@router.message(F.text == "Баланс 💰")
async def cmd_show_balance(message: Message, state: FSMContext):
    try: await message.delete()
    except Exception: pass
    await state.clear()
    msg = await message.answer("⏳ Подсчет баланса...")
    balance = await records_db.get_balance()
    
    if balance is not None:
        # Форматируем число (например: 21 810.01)
        formatted_balance = f"{balance:,.2f}".replace(',', ' ')
        await msg.edit_text(f"💰 Текущий баланс: <b>{formatted_balance}</b>", parse_mode="HTML")
    else:
        await msg.edit_text("❌ Ошибка при получении баланса.")

# --- Recent Records ---

async def show_recent_records(message: Message):
    records = await records_db.list_recent_records(10)
    if not records:
        await message.answer("Операций пока нет.")
        return
    await message.answer(
        "Последние операции:",
        reply_markup=get_recent_records_keyboard(records)
    )

async def edit_recent_records(callback: CallbackQuery):
    records = await records_db.list_recent_records(10)
    if not records:
        await callback.message.edit_text("Операций пока нет.")
        return
    await callback.message.edit_text(
        "Последние операции:",
        reply_markup=get_recent_records_keyboard(records)
    )

async def edit_record_details(message: Message, record_id: int):
    record = await records_db.get_record(record_id)
    if not record:
        await message.edit_text("Операция не найдена.")
        return
    await message.edit_text(
        format_record_details(record),
        parse_mode="HTML",
        reply_markup=get_record_actions_keyboard(record_id)
    )

@router.message(F.text == "Последние 🧾")
async def cmd_recent_records(message: Message, state: FSMContext):
    try: await message.delete()
    except Exception: pass
    await state.clear()
    await show_recent_records(message)

@router.callback_query(F.data == "recent_ops")
async def cb_recent_records(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_recent_records(callback)
    await callback.answer()

@router.callback_query(F.data.startswith("rec_view_"))
async def cb_record_view(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    record_id = int(callback.data.replace("rec_view_", ""))
    await edit_record_details(callback.message, record_id)
    await callback.answer()

@router.callback_query(F.data.startswith("rec_delete_"))
async def cb_record_delete(callback: CallbackQuery):
    record_id = int(callback.data.replace("rec_delete_", ""))
    record = await records_db.get_record(record_id)
    if not record:
        await callback.answer("Операция не найдена.", show_alert=True)
        return
    await callback.message.edit_text(
        f"Удалить операцию?\n\n{format_record_details(record)}",
        parse_mode="HTML",
        reply_markup=get_record_delete_confirm_keyboard(record_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rec_confirm_delete_"))
async def cb_record_confirm_delete(callback: CallbackQuery):
    record_id = int(callback.data.replace("rec_confirm_delete_", ""))
    success = await records_db.delete_record(record_id)
    if success:
        for user_id, cached_record_id in list(undo_cache.items()):
            if cached_record_id == record_id:
                del undo_cache[user_id]
        await callback.answer("Удалено.")
        await edit_recent_records(callback)
    else:
        await callback.answer("Операция не найдена.", show_alert=True)

@router.callback_query(F.data.startswith("rec_edit_amount_"))
async def cb_record_edit_amount(callback: CallbackQuery, state: FSMContext):
    record_id = int(callback.data.replace("rec_edit_amount_", ""))
    record = await records_db.get_record(record_id)
    if not record:
        await callback.answer("Операция не найдена.", show_alert=True)
        return
    await state.update_data(recent_record_id=record_id, recent_msg_id=callback.message.message_id)
    await state.set_state(RecentRecordState.waiting_for_amount)
    await callback.message.edit_text(
        f"{format_record_details(record)}\n\nВведите новую сумму:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(RecentRecordState.waiting_for_amount)
async def process_record_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    record_id = data.get("recent_record_id")
    msg_id = data.get("recent_msg_id")
    match = re.match(r'^([\d.,]+)$', message.text or "")

    try: await message.delete()
    except Exception: pass

    if not match:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text="❌ Введите новую сумму числом:",
            reply_markup=get_cancel_keyboard()
        )
        return

    try:
        amount = float(match.group(1).replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text="❌ Сумма должна быть положительным числом. Введите новую сумму:",
            reply_markup=get_cancel_keyboard()
        )
        return

    success = await records_db.update_record_amount(record_id, amount)
    await state.clear()
    if success:
        record = await records_db.get_record(record_id)
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text=format_record_details(record),
            parse_mode="HTML",
            reply_markup=get_record_actions_keyboard(record_id)
        )
    else:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text="❌ Операция не найдена."
        )

@router.callback_query(F.data.startswith("rec_edit_cat_"))
async def cb_record_edit_category(callback: CallbackQuery, state: FSMContext):
    record_id = int(callback.data.replace("rec_edit_cat_", ""))
    record = await records_db.get_record(record_id)
    if not record:
        await callback.answer("Операция не найдена.", show_alert=True)
        return

    cats_type = "income" if record["type"] == "Доход" else "expense"
    categories = storage.get_categories(cats_type)
    await state.update_data(recent_record_id=record_id)
    await state.set_state(RecentRecordState.waiting_for_category)
    await callback.message.edit_text(
        f"{format_record_details(record)}\n\nВыберите новую категорию:",
        parse_mode="HTML",
        reply_markup=get_categories_keyboard(categories, prefix="recentcat_")
    )
    await callback.answer()

@router.callback_query(RecentRecordState.waiting_for_category, F.data.startswith("recentcat_"))
async def process_record_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("recentcat_", "")
    data = await state.get_data()
    record_id = data.get("recent_record_id")
    success = await records_db.update_record_category(record_id, category)
    await state.clear()
    if success:
        await edit_record_details(callback.message, record_id)
        await callback.answer("Категория изменена.")
    else:
        await callback.message.edit_text("❌ Операция не найдена.")
        await callback.answer()

@router.callback_query(F.data.startswith("rec_edit_comment_"))
async def cb_record_edit_comment(callback: CallbackQuery, state: FSMContext):
    record_id = int(callback.data.replace("rec_edit_comment_", ""))
    record = await records_db.get_record(record_id)
    if not record:
        await callback.answer("Операция не найдена.", show_alert=True)
        return
    await state.update_data(recent_record_id=record_id, recent_msg_id=callback.message.message_id)
    await state.set_state(RecentRecordState.waiting_for_comment)
    await callback.message.edit_text(
        f"{format_record_details(record)}\n\nВведите новый комментарий или «-», чтобы очистить:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(RecentRecordState.waiting_for_comment)
async def process_record_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    record_id = data.get("recent_record_id")
    msg_id = data.get("recent_msg_id")
    comment = (message.text or "").strip()
    if comment == "-":
        comment = ""

    try: await message.delete()
    except Exception: pass

    success = await records_db.update_record_comment(record_id, comment)
    await state.clear()
    if success:
        record = await records_db.get_record(record_id)
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text=format_record_details(record),
            parse_mode="HTML",
            reply_markup=get_record_actions_keyboard(record_id)
        )
    else:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text="❌ Операция не найдена."
        )

async def send_excel_export(message: Message):
    msg = await message.answer("⏳ Готовлю Excel-файл...")
    records = await records_db.list_records()
    balance = await records_db.get_balance()
    if balance is None:
        await msg.edit_text("❌ Не удалось посчитать баланс для выгрузки.")
        return

    output_path = Path(tempfile.gettempdir()) / export_filename()
    write_records_xlsx(records, balance, output_path)
    await msg.edit_text("✅ Выгрузка готова.")
    await message.answer_document(FSInputFile(output_path), caption="Excel-выгрузка финансов")

@router.callback_query(F.data == "export_excel")
async def cb_export_excel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await send_excel_export(callback.message)

@router.message(F.text == "Выгрузка Excel 📤")
async def cmd_export_excel(message: Message, state: FSMContext):
    try: await message.delete()
    except Exception: pass
    await state.clear()
    await send_excel_export(message)

# --- Templates ---

@router.message(F.text == "Шаблоны")
async def cmd_templates(message: Message, state: FSMContext):
    try: await message.delete()
    except Exception: pass
    await state.clear()

    templates = templates_storage.get_all()
    if not templates:
        await message.answer("Шаблонов пока нет.", reply_markup=get_templates_keyboard(templates))
        return

    await message.answer("Выберите шаблон:", reply_markup=get_templates_keyboard(templates))

@router.callback_query(F.data.startswith("use_tpl_"))
async def cb_use_template(callback: CallbackQuery, state: FSMContext):
    template_id = callback.data.replace("use_tpl_", "")
    template = templates_storage.get(template_id)
    if not template:
        await callback.answer("Шаблон не найден.", show_alert=True)
        return

    await state.update_data(template_id=template_id, template_msg_id=callback.message.message_id)
    await state.set_state(TemplateUseState.waiting_for_amount)
    await callback.message.edit_text(
        (
            f"Шаблон: <b>{h(template['name'])}</b>\n"
            f"Тип: <b>{h(template['type'])}</b>\n"
            f"Категория: <b>{h(template['category'])}</b>\n"
            f"Комментарий: <i>{h(template['comment'])}</i>\n\n"
            f"Введите сумму:"
        ),
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(TemplateUseState.waiting_for_amount)
async def process_template_amount(message: Message, state: FSMContext):
    match = re.match(r'^([\d.,]+)\s*(.*)$', message.text or "")
    data = await state.get_data()
    template_id = data.get("template_id")
    template = templates_storage.get(template_id)
    template_msg_id = data.get("template_msg_id")

    if not template:
        await state.clear()
        await message.answer("Шаблон не найден.", reply_markup=get_main_menu())
        return

    try: await message.delete()
    except Exception: pass

    if not match:
        text = f"Шаблон: <b>{h(template['name'])}</b>\n❌ Не удалось распознать сумму. Введите число:"
        if template_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=template_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=get_cancel_keyboard()
            )
        return

    amount_text = match.group(1).replace(",", ".")
    extra_comment = match.group(2).strip()
    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        text = f"Шаблон: <b>{h(template['name'])}</b>\n❌ Сумма должна быть положительным числом. Введите сумму:"
        if template_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=template_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=get_cancel_keyboard()
            )
        return

    comment = template["comment"]
    if extra_comment:
        comment = f"{comment} | {extra_comment}" if comment else extra_comment

    if template_msg_id:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=template_msg_id,
            text="⏳ Сохранение..."
        )

    success, record = await records_db.add_record(
        template["type"],
        amount,
        template["category"],
        comment
    )

    if success:
        undo_cache[message.from_user.id] = record["id"]
        text = f"✅ Сохранено: {h(template['type'])} {amount} -> {h(template['category'])}"
        if template_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=template_msg_id,
                text=text,
                parse_mode="HTML",
                reply_markup=get_undo_keyboard()
            )
        else:
            await message.answer(text, parse_mode="HTML", reply_markup=get_undo_keyboard())
    else:
        if template_msg_id:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=template_msg_id,
                text="❌ Ошибка сохранения. Попробуйте еще раз."
            )
        else:
            await message.answer("❌ Ошибка сохранения. Попробуйте еще раз.")

    await state.clear()

@router.callback_query(F.data == "tpl_settings")
async def cb_templates_settings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Шаблоны:", reply_markup=get_templates_settings_menu())
    await callback.answer()

@router.callback_query(F.data == "tpl_list")
async def cb_templates_list(callback: CallbackQuery):
    templates = templates_storage.get_all()
    if not templates:
        await callback.message.edit_text("Шаблонов пока нет.", reply_markup=get_templates_settings_menu())
        await callback.answer()
        return

    lines = ["<b>Ваши шаблоны:</b>\n"]
    for template in templates:
        comment = f" | {h(template['comment'])}" if template.get("comment") else ""
        lines.append(
            f"• <b>{h(template['name'])}</b> — {h(template['type'])}, {h(template['category'])}{comment}"
        )

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=get_templates_settings_menu())
    await callback.answer()

@router.callback_query(F.data == "tpl_add")
async def cb_template_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TemplateState.waiting_for_name)
    await state.update_data(template_msg_id=callback.message.message_id)
    await callback.message.edit_text("Введите название шаблона:", reply_markup=get_cancel_keyboard())
    await callback.answer()

@router.message(TemplateState.waiting_for_name)
async def process_template_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    try: await message.delete()
    except Exception: pass

    if not name:
        await message.answer("Название не может быть пустым.", reply_markup=get_cancel_keyboard())
        return

    await state.update_data(template_name=name)
    await state.set_state(TemplateState.waiting_for_comment)
    data = await state.get_data()
    template_msg_id = data.get("template_msg_id")
    text = f"Название: <b>{h(name)}</b>\nВведите комментарий для операции или «-», чтобы оставить пустым:"
    if template_msg_id:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=template_msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
    else:
        msg = await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
        await state.update_data(template_msg_id=msg.message_id)

@router.message(TemplateState.waiting_for_comment)
async def process_template_comment(message: Message, state: FSMContext):
    comment = (message.text or "").strip()
    if comment == "-":
        comment = ""
    try: await message.delete()
    except Exception: pass

    await state.update_data(template_comment=comment)
    await state.set_state(TemplateState.waiting_for_type)
    data = await state.get_data()

    builder = InlineKeyboardBuilder()
    builder.button(text="Доход", callback_data="tpltype_Доход")
    builder.button(text="Расход", callback_data="tpltype_Расход")
    builder.adjust(2)

    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=data["template_msg_id"],
        text=f"Название: <b>{h(data['template_name'])}</b>\nКомментарий: <i>{h(comment)}</i>\nЭто доход или расход?",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(TemplateState.waiting_for_type, F.data.startswith("tpltype_"))
async def process_template_type(callback: CallbackQuery, state: FSMContext):
    type_ = callback.data.replace("tpltype_", "")
    await state.update_data(template_type=type_)
    data = await state.get_data()
    cats_type = "income" if type_ == "Доход" else "expense"
    categories = storage.get_categories(cats_type)

    await state.set_state(TemplateState.waiting_for_category)
    await callback.message.edit_text(
        (
            f"Название: <b>{h(data['template_name'])}</b>\n"
            f"Комментарий: <i>{h(data['template_comment'])}</i>\n"
            f"Тип: <b>{h(type_)}</b>\n"
            f"Выберите категорию:"
        ),
        parse_mode="HTML",
        reply_markup=get_categories_keyboard(categories, prefix="tplcat_")
    )
    await callback.answer()

@router.callback_query(TemplateState.waiting_for_category, F.data.startswith("tplcat_"))
async def process_template_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("tplcat_", "")
    data = await state.get_data()
    templates_storage.add_template(
        name=data["template_name"],
        comment=data["template_comment"],
        type_=data["template_type"],
        category=category,
    )

    await callback.message.edit_text(
        f"✅ Шаблон «{h(data['template_name'])}» добавлен.",
        parse_mode="HTML",
        reply_markup=get_templates_settings_menu()
    )
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "tpl_del")
async def cb_template_delete(callback: CallbackQuery):
    templates = templates_storage.get_all()
    if not templates:
        await callback.message.edit_text("Нет шаблонов для удаления.", reply_markup=get_templates_settings_menu())
        await callback.answer()
        return
    await callback.message.edit_text("Выберите шаблон для удаления:", reply_markup=get_delete_template_keyboard(templates))
    await callback.answer()

@router.callback_query(F.data.startswith("rmtpl_"))
async def cb_remove_template(callback: CallbackQuery):
    template_id = callback.data.replace("rmtpl_", "")
    if templates_storage.remove_template(template_id):
        await callback.answer("Шаблон удален.")
        await callback.message.edit_text("Шаблоны:", reply_markup=get_templates_settings_menu())
    else:
        await callback.answer("Ошибка при удалении.", show_alert=True)


from keyboards import get_cancel_reply_keyboard

@router.message(F.text.in_(["Доход", "Расход"]))
async def cmd_operation_start(message: Message, state: FSMContext):
    op_type = message.text
    try: await message.delete()
    except Exception: pass
    msg = await message.answer(f"Выбран: <b>{op_type}</b>\nВведите сумму (например, 100 или 100.50):", parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())
    # Save the bot message ID so we can edit it later
    await state.update_data(op_type=op_type, main_msg_id=msg.message_id)
    await state.set_state(OperationState.waiting_for_amount)

@router.message(OperationState.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    # Parse format "100.5 comment"
    match = re.match(r'^([\d.,]+)\s*(.*)$', message.text)
    if not match:
        await message.answer("Ошибка: не удалось распознать сумму. Введите число (например, 100 или 100.5).", reply_markup=get_cancel_keyboard())
        return

    text = match.group(1).replace(",", ".")
    comment = match.group(2).strip()
    
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except ValueError:
        await message.answer("Ошибка: сумма должна быть положительным числом.", reply_markup=get_cancel_keyboard())
        return

    data = await state.get_data()
    op_type = data['op_type']
    main_msg_id = data.get('main_msg_id')
    
    # Try to delete user message (the amount)
    try:
        await message.delete()
    except Exception:
        pass
    
    await state.update_data(amount=amount, comment=comment)
    
    # Load categories for this type
    cats_type = "income" if op_type == "Доход" else "expense"
    categories = storage.get_categories(cats_type)
    
    await state.set_state(OperationState.waiting_for_category)
    
    msg_text = f"Сумма: <b>{amount}</b>"
    if comment:
        msg_text += f"\nКомментарий: <i>{h(comment)}</i>"
    msg_text += "\nВыберите категорию:"
    
    if main_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=main_msg_id,
                text=msg_text,
                parse_mode="HTML",
                reply_markup=get_categories_keyboard(categories, prefix="selcat_")
            )
            # Restore the main reply keyboard in chat background
            await message.answer("Продолжаем в меню...", reply_markup=get_main_menu(), disable_notification=True)
            return
        except Exception:
            pass
            
    await message.answer(
        msg_text, 
        parse_mode="HTML", 
        reply_markup=get_categories_keyboard(categories, prefix="selcat_")
    )
    await message.answer("Клавиатура возвращена:", reply_markup=get_main_menu(), disable_notification=True)

@router.callback_query(OperationState.waiting_for_category, F.data.startswith("selcat_"))
async def process_category_selection(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("selcat_", "")
    data = await state.get_data()
    op_type = data['op_type']
    amount = data['amount']
    comment = data.get('comment', '')
    
    # Send processing message
    await callback.message.edit_text("⏳ Сохранение...")
    
    success, record = await records_db.add_record(op_type, amount, category, comment)
    
    if success:
        undo_cache[callback.from_user.id] = record["id"]
        await callback.message.edit_text(
            f"✅ Сохранено: {h(op_type)} {amount} -> {h(category)}",
            reply_markup=get_undo_keyboard()
        )
    else:
        await callback.message.edit_text(
            f"❌ Ошибка сохранения. Попробуйте еще раз."
        )
        
    await state.clear()
    await callback.answer()

# --- Settings ---

@router.message(F.text == "Настройки")
async def cmd_settings(message: Message, state: FSMContext):
    try: await message.delete()
    except Exception: pass
    await state.clear()
    await message.answer("Настройки. Выберите раздел:", reply_markup=get_settings_menu())

@router.callback_query(F.data == "settings_menu")
async def cb_settings_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Настройки. Выберите раздел:", reply_markup=get_settings_menu())
    await callback.answer()

@router.callback_query(F.data.in_(["set_income", "set_expense"]))
async def cb_settings_type(callback: CallbackQuery, state: FSMContext):
    cat_type = "income" if callback.data == "set_income" else "expense"
    type_name = "Доход" if cat_type == "income" else "Расход"
    
    categories = storage.get_categories(cat_type)
    cats_str = "\n".join([f"- {h(c)}" for c in categories])
    
    await callback.message.edit_text(
        f"Категории ({type_name}):\n{cats_str}\n\nВыберите действие:",
        reply_markup=get_settings_action_menu(cat_type)
    )
    await callback.answer()

# --- Add Category ---

@router.callback_query(F.data.startswith("add_"))
async def cb_add_category_start(callback: CallbackQuery, state: FSMContext):
    cat_type = callback.data.replace("add_", "")
    type_name = "Доход" if cat_type == "income" else "Расход"
    
    await state.update_data(settings_cat_type=cat_type)
    await state.set_state(SettingsState.waiting_for_new_category)
    
    await callback.message.edit_text(
        f"Отправьте название новой категории для раздела <b>{type_name}</b>:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(SettingsState.waiting_for_new_category)
async def process_new_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("Имя категории не может быть пустым.", reply_markup=get_cancel_keyboard())
        return
        
    data = await state.get_data()
    cat_type = data['settings_cat_type']
    type_name = "Доход" if cat_type == "income" else "Расход"
    
    added = storage.add_category(cat_type, category)
    if added:
        await message.answer(
            f"Категория «{h(category)}» успешно добавлена в {type_name}.",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            f"Категория «{h(category)}» уже существует в {type_name}.",
            reply_markup=get_main_menu()
        )
    
    await state.clear()

# --- Delete Category ---

@router.callback_query(F.data.startswith("del_"))
async def cb_del_category_start(callback: CallbackQuery):
    cat_type = callback.data.replace("del_", "")
    type_name = "Доход" if cat_type == "income" else "Расход"
    
    categories = storage.get_categories(cat_type)
    
    await callback.message.edit_text(
        f"Выберите категорию ({type_name}) для удаления:",
        reply_markup=get_delete_category_keyboard(categories, cat_type)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rm_"))
async def cb_rm_category_process(callback: CallbackQuery):
    # data format: rm_{cat_type}_{category}
    # find second underscore
    parts = callback.data.split("_", 2)
    cat_type = parts[1]
    category = parts[2]
    
    removed = storage.remove_category(cat_type, category)
    
    type_name = "Доход" if cat_type == "income" else "Расход"
    
    if removed:
        # Re-render the settings menu for this type
        categories = storage.get_categories(cat_type)
        cats_str = "\n".join([f"- {h(c)}" for c in categories])
        await callback.message.edit_text(
            f"Категория «{h(category)}» удалена.\n\nКатегории ({type_name}):\n{cats_str}\n\nВыберите действие:",
            reply_markup=get_settings_action_menu(cat_type)
        )
        await callback.answer("Удалено!")
    else:
        await callback.answer("Невозможно удалить последнюю категорию или категория не найдена!", show_alert=True)

# --- Undo Operation ---
@router.callback_query(F.data == "undo_last")
async def cb_undo_last(callback: CallbackQuery):
    user_id = callback.from_user.id
    record_id = undo_cache.get(user_id)
    if not record_id:
        await callback.answer("Нет данных для отмены (возможно, прошло слишком много времени).", show_alert=True)
        return
        
    await callback.message.edit_text("⏳ Отмена операции...", reply_markup=None)
    success = await records_db.delete_record(record_id)
    
    if success:
        del undo_cache[user_id]
        await callback.message.edit_text("✅ Последняя операция отменена.")
    else:
        await callback.message.edit_text("❌ При отмене произошла ошибка (запись не найдена).")

# --- Subscriptions ---
@router.callback_query(F.data == "subs_menu")
async def cb_subs_menu(callback: CallbackQuery, state: FSMContext | None = None):
    if state:
        await state.clear()
    await callback.message.edit_text("Регулярные платежи (Подписки):", reply_markup=get_subscriptions_menu())

@router.callback_query(F.data == "subs_list")
async def cb_subs_list(callback: CallbackQuery):
    subs = sub_storage.get_all()
    if not subs:
        await callback.message.edit_text("У вас нет добавленных регулярных платежей/подписок.", reply_markup=get_subscriptions_menu())
        return
        
    lines = ["<b>Ваши подписки:</b>\n"]
    for s in subs:
        lines.append(f"• {h(s['name'])} — {s['amount']} ({h(s['category'])}) | Дата: {h(s['date'])}")
        
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=get_subscriptions_menu())

@router.callback_query(F.data == "subs_add")
async def cb_subs_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SubState.waiting_for_name)
    await callback.message.edit_text("Введите название подписки/регулярного платежа:", reply_markup=get_cancel_keyboard())
    await state.update_data(sub_msg_id=callback.message.message_id)

@router.message(SubState.waiting_for_name)
async def sub_process_name(message: Message, state: FSMContext):
    if not message.text:
        return
    try: await message.delete()
    except Exception: pass
    
    await state.update_data(sub_name=message.text.strip())
    await state.set_state(SubState.waiting_for_amount)
    
    data = await state.get_data()
    sub_msg_id = data.get('sub_msg_id')
    
    text = f"Название: <b>{h(message.text.strip())}</b>\nВведите сумму (например, 150.0):"
    
    if sub_msg_id:
        try:
            await message.bot.edit_message_text(chat_id=message.chat.id, message_id=sub_msg_id, text=text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
            return
        except Exception: pass
    msg = await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
    await state.update_data(sub_msg_id=msg.message_id)

@router.message(SubState.waiting_for_amount)
async def sub_process_amount(message: Message, state: FSMContext):
    try: await message.delete()
    except Exception: pass

    data = await state.get_data()
    sub_msg_id = data.get('sub_msg_id')

    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0: raise ValueError
    except ValueError:
        text = f"Название: <b>{h(data.get('sub_name', ''))}</b>\n❌ Ошибка: сумма должна быть числом.\nВведите сумму:"
        if sub_msg_id:
            try:
                await message.bot.edit_message_text(chat_id=message.chat.id, message_id=sub_msg_id, text=text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
                return
            except Exception: pass
        msg = await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
        await state.update_data(sub_msg_id=msg.message_id)
        return
        
    await state.update_data(sub_amount=amount)
    data['sub_amount'] = amount
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Доход", callback_data="subtype_Доход")
    builder.button(text="Расход", callback_data="subtype_Расход")
    builder.adjust(2)
    
    await state.set_state(SubState.waiting_for_type)
    text = f"Название: <b>{h(data['sub_name'])}</b>\nСумма: <b>{amount}</b>\nЭто доход или расход?"
    
    if sub_msg_id:
        try:
            await message.bot.edit_message_text(chat_id=message.chat.id, message_id=sub_msg_id, text=text, parse_mode="HTML", reply_markup=builder.as_markup())
            return
        except Exception: pass
    msg = await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await state.update_data(sub_msg_id=msg.message_id)

@router.callback_query(SubState.waiting_for_type, F.data.startswith("subtype_"))
async def sub_process_type(callback: CallbackQuery, state: FSMContext):
    type_ = callback.data.replace("subtype_", "")
    await state.update_data(sub_type=type_)
    data = await state.get_data()
    
    cats_type = "income" if type_ == "Доход" else "expense"
    categories = storage.get_categories(cats_type)
    
    await state.set_state(SubState.waiting_for_category)
    text = f"Название: <b>{h(data['sub_name'])}</b>\nСумма: <b>{data['sub_amount']}</b>\nТип: <b>{h(type_)}</b>\nВыберите категорию:"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_categories_keyboard(categories, prefix="subcat_"))

@router.callback_query(SubState.waiting_for_category, F.data.startswith("subcat_"))
async def sub_process_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("subcat_", "")
    await state.update_data(sub_category=category)
    data = await state.get_data()
    
    await state.set_state(SubState.waiting_for_date)
    text = f"Название: <b>{h(data['sub_name'])}</b>\nСумма: <b>{data['sub_amount']}</b>\nКатегория: <b>{h(category)}</b>\nВведите дату платежа (ДД.ММ.ГГГГ):"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())

@router.message(SubState.waiting_for_date)
async def sub_process_date(message: Message, state: FSMContext):
    try: await message.delete()
    except Exception: pass

    import datetime
    date_str = message.text.strip()
    data = await state.get_data()
    sub_msg_id = data.get('sub_msg_id')
    
    try:
        dt = datetime.datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        text = f"Название: <b>{h(data['sub_name'])}</b>\nСумма: <b>{data['sub_amount']}</b>\nКатегория: <b>{h(data['sub_category'])}</b>\n❌ Неверный формат. Дата (ДД.ММ.ГГГГ):"
        if sub_msg_id:
            try:
                await message.bot.edit_message_text(chat_id=message.chat.id, message_id=sub_msg_id, text=text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
                return
            except Exception: pass
        msg = await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_keyboard())
        await state.update_data(sub_msg_id=msg.message_id)
        return
        
    sub_storage.add_subscription(
        name=data['sub_name'],
        amount=data['sub_amount'],
        category=data['sub_category'],
        type_=data['sub_type'],
        date_str=date_str
    )
    
    text = f"✅ Подписка «{h(data['sub_name'])}» добавлена на {h(date_str)}!"
    if sub_msg_id:
        try:
            await message.bot.edit_message_text(chat_id=message.chat.id, message_id=sub_msg_id, text=text, parse_mode="HTML", reply_markup=get_subscriptions_menu())
        except Exception:
            await message.answer(text, reply_markup=get_subscriptions_menu())
    else:
        await message.answer(text, reply_markup=get_subscriptions_menu())
        
    await state.clear()

@router.callback_query(F.data == "subs_del")
async def cb_subs_del(callback: CallbackQuery):
    subs = sub_storage.get_all()
    if not subs:
        await callback.message.edit_text("Нет подписок для удаления.", reply_markup=get_subscriptions_menu())
        return
    await callback.message.edit_text("Выберите подписку для удаления:", reply_markup=get_delete_subscription_keyboard(subs))
    
@router.callback_query(F.data.startswith("rmsub_"))
async def cb_rmsub_process(callback: CallbackQuery):
    sub_id = callback.data.replace("rmsub_", "")
    if sub_storage.remove_subscription(sub_id):
        await callback.answer("Подписка удалена!")
        await cb_subs_menu(callback)
    else:
        await callback.answer("Ошибка при удалении.", show_alert=True)

# Reminder Handlers
@router.callback_query(F.data.startswith("pay_sub_"))
async def cb_pay_sub(callback: CallbackQuery):
    sub_id = callback.data.replace("pay_sub_", "")
    subs = sub_storage.get_all()
    sub = next((s for s in subs if s['id'] == sub_id), None)
    
    if not sub:
        await callback.message.edit_text("Подписка больше не существует.")
        return
        
    await callback.message.edit_text("⏳ Сохранение...")
    success, _row = await records_db.add_record(sub['type'], sub['amount'], sub['category'], f"Подписка: {sub['name']}")
    import datetime
    
    # Calculate next month date roughly
    old_date = datetime.datetime.strptime(sub['date'], "%d.%m.%Y")
    month = old_date.month + 1
    year = old_date.year
    if month > 12:
        month = 1
        year += 1
    day = old_date.day
    while True:
        try:
            new_date = datetime.datetime(year, month, day)
            break
        except ValueError:
            day -= 1 # adjust for end of month (e.g. 31 to 30)

    if success:
        new_date_str = new_date.strftime("%d.%m.%Y")
        sub_storage.update_subscription_date(sub_id, new_date_str)
        await callback.message.edit_text(f"✅ Успешно записано!\nСледующее списание перенесено на {new_date_str}.")
    else:
        await callback.message.edit_text("❌ Ошибка при сохранении.")

@router.callback_query(F.data.startswith("skip_sub_"))
async def cb_skip_sub(callback: CallbackQuery):
    sub_id = callback.data.replace("skip_sub_", "")
    subs = sub_storage.get_all()
    sub = next((s for s in subs if s['id'] == sub_id), None)
    
    if not sub:
        await callback.message.edit_text("Подписка больше не существует.")
        return
        
    import datetime
    old_date = datetime.datetime.strptime(sub['date'], "%d.%m.%Y")
    month = old_date.month + 1
    year = old_date.year
    if month > 12:
        month = 1
        year += 1
    day = old_date.day
    while True:
        try:
            new_date = datetime.datetime(year, month, day)
            break
        except ValueError:
            day -= 1

    new_date_str = new_date.strftime("%d.%m.%Y")
    sub_storage.update_subscription_date(sub_id, new_date_str)
    
    await callback.message.edit_text(f"Пропущено ❌\nСледующее списание: {new_date_str}")
