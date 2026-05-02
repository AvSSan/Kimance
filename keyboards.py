from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

def get_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="Доход")
    builder.button(text="Расход")
    builder.button(text="Баланс 💰")
    builder.button(text="Выгрузка Excel 📤")
    builder.button(text="Настройки")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="Отмена ❌")
    return builder.as_markup(resize_keyboard=True)

def get_categories_keyboard(categories: list[str], prefix: str = "cat_") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=cat, callback_data=f"{prefix}{cat}")
    
    builder.button(text="Отмена ❌", callback_data="cancel_operation")
    builder.adjust(2)
    return builder.as_markup()

def get_settings_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Категории: Доход", callback_data="set_income")
    builder.button(text="Категории: Расход", callback_data="set_expense")
    builder.button(text="Подписки 📅", callback_data="subs_menu")
    builder.button(text="Назад 🔙", callback_data="main_menu")
    builder.adjust(2, 1, 1)
    return builder.as_markup()

def get_settings_action_menu(cat_type: str) -> InlineKeyboardMarkup:
    # cat_type determines contextual actions: add/del
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить", callback_data=f"add_{cat_type}")
    builder.button(text="Удалить", callback_data=f"del_{cat_type}")
    builder.button(text="Назад 🔙", callback_data="settings_menu")
    builder.adjust(2, 1)
    return builder.as_markup()

def get_delete_category_keyboard(categories: list[str], cat_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=f"🗑 {cat}", callback_data=f"rm_{cat_type}_{cat}")
    builder.button(text="Назад 🔙", callback_data=f"set_{cat_type}")
    builder.adjust(2)
    return builder.as_markup()

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена ❌", callback_data="cancel_operation")
    return builder.as_markup()

def get_undo_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Меню", callback_data="main_menu")
    builder.button(text="Отменить ↩️", callback_data="undo_last")
    builder.adjust(2)
    return builder.as_markup()

def get_subscriptions_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Список подписок", callback_data="subs_list")
    builder.button(text="Добавить", callback_data="subs_add")
    builder.button(text="Удалить", callback_data="subs_del")
    builder.button(text="Назад 🔙", callback_data="settings_menu")
    builder.adjust(1, 2, 1)
    return builder.as_markup()
    
def get_delete_subscription_keyboard(subs: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in subs:
        builder.button(text=f"🗑 {s['name']}", callback_data=f"rmsub_{s['id']}")
    builder.button(text="Назад 🔙", callback_data="subs_menu")
    builder.adjust(1)
    return builder.as_markup()
    
def get_reminder_keyboard(sub_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Записать ✅", callback_data=f"pay_sub_{sub_id}")
    builder.button(text="Пропустить ❌", callback_data=f"skip_sub_{sub_id}")
    builder.adjust(2)
    return builder.as_markup()
