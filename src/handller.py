from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, filters, ConversationHandler, MessageHandler, \
    CallbackContext
from src.database import get_connection
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import asyncio
import schedule


ASK_BIRTHDAY_NAME: int
ASK_BIRTHDAY_NAME, ASK_BIRTHDAY_DATE, ASK_DELETE_BIRTHDAY, ASK_EDIT_BIRTHDAY_NAME, ASK_EDIT_BIRTHDAY_DATE,ASK_WISH,ASK_DELETE_WISH,SET_REQUISITES_STATE = range(8)


class Commandshendler:
    def __init__(self, app):
        self.app = app
        self.db = get_connection()
        self.scheduler = AsyncIOScheduler()  # Initialize Async Scheduler
        self.setup()
        self.wishlist = {}
        self.schedule_daily_birthday_check()
        self.chat_id = None


    def setup(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CommandHandler("get_requisites", self.get_requisites))
        self.app.add_handler(CommandHandler("view_birthdays", self.view_birthdays))
        self.app.add_handler(CommandHandler("my_wishlist", self.my_wishlist))
        self.app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("view_wishlist", self.view_wishlist)],
            states={
                ASK_BIRTHDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_view_wishlist)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        ))
        self.app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("add_birthday", self.add_birthday)],
            states={
                ASK_BIRTHDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_birthday)],
                ASK_BIRTHDAY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_birthday)]

            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        ))
        self.app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("delete_birthday", self.delete_birthday)],
            states={
                ASK_BIRTHDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirm_delete)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        ))
        self.app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("edit_birthday", self.edit_birthday)],
            states={
                ASK_EDIT_BIRTHDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_edit_birthday)],
                ASK_EDIT_BIRTHDAY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_edit_birthday)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        ))
        self.app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("add_wish", self.add_wish)],
            states={
                ASK_WISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_wish)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        ))
        self.app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("delete_wish", self.delete_wish)],
            states={
                ASK_DELETE_WISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_delete_wish)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        ))
        self.app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("set_requisites", self.set_requisites)],
            states={
                SET_REQUISITES_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_requisites)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        ))

    async def set_requisites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Command for administrators to set the requisites."""
        if update.message.chat.type in ['group', 'supergroup']:
            user_id = update.message.from_user.id
            chat_id = update.message.chat.id
            admins = await context.bot.get_chat_administrators(chat_id)
            if any(admin.user.id == user_id for admin in admins):
                await update.message.reply_text("Введіть реквізити для групи:")
                return SET_REQUISITES_STATE  # State for the next step
            else:
                await update.message.reply_text("Ви не можете додати реквізити, адже не являєтесь адміністратором.")
        else:
            await update.message.reply_text("Ця команда працює тільки у групах.")

    async def save_requisites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save requisites to the database."""
        chat_id = update.message.chat.id
        requisites = update.message.text

        try:
            with self.db.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO requisites (chat_id, bank_details) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE bank_details = VALUES(bank_details)",
                    (chat_id, requisites)
                )
                self.db.commit()

            await update.message.reply_text("Реквізити успішно встановлені!")
        except Exception as e:
            await update.message.reply_text(f"Помилка у введені реквізитів: {e}")
        return ConversationHandler.END

    async def get_requisites(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Retrieve requisites from the database."""
        chat_id = update.message.chat.id

        try:
            with self.db.cursor() as cursor:
                cursor.execute("SELECT bank_details FROM requisites WHERE chat_id = %s", (chat_id,))
                result = cursor.fetchone()

            if result:
                await update.message.reply_text(f"Реквізити: {result[0]}")
            else:
                await update.message.reply_text("В цій групі ще не додані реквізити.")
        except Exception as e:
            await update.message.reply_text(f"Error retrieving requisites: {e}")

    async def capture_chat_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id

        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT IGNORE INTO birthdays (chat_id) VALUES (%s)",
                (chat_id,)
            )
        connection.commit()
        connection.close()
        print(f"Captured chat_id: {chat_id}")

    async def check_birthdays(self):
        """Function to check the database for today’s birthdays and send greetings."""

        connection = get_connection()
        today = datetime.now().strftime('%m-%d')

        # Fetch all chat_id values
        with connection.cursor() as cursor:
            cursor.execute("SELECT DISTINCT chat_id FROM birthdays")
            chat_ids = cursor.fetchall()

        if not chat_ids:
            print("No chat IDs found in the database.")
            return

        print(f"Chat IDs found: {chat_ids}")

        for chat_id_row in chat_ids:
            chat_id = chat_id_row[0]


            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT nickname FROM birthdays WHERE DATE_FORMAT(birthday, '%m-%d') = %s AND chat_id = %s",
                    (today, chat_id))
                birthdays = cursor.fetchall()

            if not birthdays:
                print(f"No birthdays found today for group with chat_id {chat_id}.")
                continue

            for birthday in birthdays:
                nickname = birthday[0]
                message = f"🎉 З Днем народження, {nickname}! 🎂 Щиро бажаємо всього найкращого!"
                print(f"Sending message to chat_id {chat_id}: {message}")
                try:
                    await self.app.bot.send_message(chat_id=chat_id, text=message)
                    print(f"Message successfully sent to {nickname}")
                except Exception as e:
                    print(f"Error sending message: {e}")

        connection.close()

    def schedule_daily_birthday_check(self):
        """Schedules the birthday check to run daily at a specified time."""
        self.scheduler.add_job(self.check_birthdays, CronTrigger(hour=16, minute=17))
        self.scheduler.start()



    async def delete_wish(self, update: Update, context: CallbackContext):
        nickname = f"@{update.effective_user.username}"
        query = "SELECT id FROM birthdays WHERE nickname = %s"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (nickname,))
        result = cursor.fetchone()

        if result is None:
            await update.message.reply_text(
                "Ваш день народження не зареєстрований, тому ви не можете переглянути свій вішліст."
            )
            cursor.close()
            conn.close()
            return ConversationHandler.END

        birthday_id = result[0]
        wishlist_query = "SELECT item_name FROM wishlists WHERE birthday_id = %s"
        cursor.execute(wishlist_query, (birthday_id,))
        results = cursor.fetchall()

        wish_map = {}
        i = 1
        if results:
            wishlist_text = "Ваш вішліст:\n"
            for item in results:
                wishlist_text += f"{i}. 🎁 {item[0]}\n"
                wish_map[i] = item[0]
                i += 1
            wishlist_text += "\nВведіть цифру бажання, яке ви хочете видалити."
        else:
            wishlist_text = "Ваш вішліст порожній."

        context.user_data['wish_map'] = wish_map
        await update.message.reply_text(wishlist_text)
        cursor.close()
        conn.close()
        return ASK_DELETE_WISH

    async def save_delete_wish(self, update: Update, context: CallbackContext):
        wish_map = context.user_data['wish_map']
        text_choose = update.message.text
        if text_choose.isdigit() and int(text_choose) in wish_map:
            text_value = wish_map.get(int(text_choose))
            delete_query = "DELETE FROM wishlists WHERE item_name = %s"
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(delete_query, (text_value,))
            conn.commit()

            await update.message.reply_text(f"Побажання '{text_value}' успішно видалене.")
        else:
            await update.message.reply_text("Неправильний вибір. Спробуйте ще раз.")

        return ConversationHandler.END

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Привіт, я BDayBuddy!Напишіть /help для списку команд.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Команди користувача:\n/view_birthdays - Переглянути всі дні народження\n/add_wish - Додати елемент до свого списку бажань\n/delete_wish - Видалити побажання з свого списку юажань\n/view_wishlist - Переглянути чийсь список бажань\n/my_wishlist - Переглянути свій список бажань\n/get_requisites - Переглянути реквізити\n\nКоманди адміністратора:\n/add_birthday - Додати новий день народження\n/edit_birthday - Редагувати існуючий день народження\n/delete_birthday - Видалити день народження\n/set_requisites - Додати реквізити\n")

    async def add_birthday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat = await context.bot.get_chat(update.message.chat_id)
        member = await chat.get_member(user.id)

        if not member.status in ["administrator", "creator"]:
            await update.message.reply_text("Вибачте, але ця команда доступна тільки адміністраторам.")
            return ConversationHandler.END

        await update.message.reply_text("Введіть нікнейм користувача, наприклад @nickname")
        return ASK_BIRTHDAY_NAME

    async def ask_birthday(self, update: Update, context: CallbackContext):
        while True:
            text = update.message.text
            # Перевірка на формат нікнейма
            if not text.startswith("@"):
                await update.message.reply_text("Нікнейм має починатися з '@'. Спробуйте ще раз:")
                return ASK_BIRTHDAY_NAME

            nicknames = await self.get_all_nicknames()

            if text in nicknames:
                await update.message.reply_text("Дата народження для користувача вже існує!")
                return ConversationHandler.END

            context.user_data['name'] = text
            entities = update.message.entities

            for entity in entities:
                if entity.type == MessageEntity.MENTION:
                    username = update.message.text[entity.offset:entity.offset + entity.length]
                    context.user_data['user_id'] = username

            await update.message.reply_text(
                f"Введіть дату народження для {context.user_data['name']} в форматі YYYY-MM-DD")
            return ASK_BIRTHDAY_DATE

    async def save_birthday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        birthday = update.message.text
        chat_id = update.effective_chat.id
        name = context.user_data['name']
        id = context.user_data['user_id']

        query = """
                    INSERT INTO birthdays (nickname, birthday, chat_id)
                    VALUES (%s, %s ,%s)
                    """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (name, birthday, chat_id))
        conn.commit()

        await update.message.reply_text(f"Дату народження для {context.user_data['name']} встановлено!")
        context.user_data.clear()




    async def view_birthdays(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показує дні народження для поточної групи."""
        chat_id = update.effective_chat.id  # Отримуємо chat_id групи

        # Запит із фільтрацією за chat_id
        query = "SELECT nickname, DATE_FORMAT(birthday, '%d-%m-%Y') FROM birthdays WHERE chat_id = %s"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (chat_id,))  # Передаємо chat_id як параметр запиту

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if results:
            birthdays_text = "📅 Список днів народжень:\n"
            for nickname, birthday in results:
                birthdays_text += f"👤 {nickname}: 🎂 {birthday}\n"
        else:
            birthdays_text = "📭 У цій групі немає записаних днів народжень."

        await update.message.reply_text(birthdays_text)


    async def delete_birthday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat = await context.bot.get_chat(update.message.chat_id)
        member = await chat.get_member(user.id)

        if not member.status in ["administrator", "creator"]:
            await update.message.reply_text("Вибачте, але ця команда доступна тільки адміністраторам.")
            return
        await update.message.reply_text("Введіть нікнейм користувача, якого потрібно видалити, наприклад @nickname")
        return ASK_BIRTHDAY_NAME

    async def confirm_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        nickname_to_delete = update.message.text
        nicknames = await self.get_all_nicknames()

        if nickname_to_delete not in nicknames:
            await update.message.reply_text("Цей нікнейм не знайдено в списку днів народження.")
            return ConversationHandler.END

        query = "SELECT id FROM birthdays WHERE nickname = %s"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (nickname_to_delete,))
        result = cursor.fetchone()

        if result:
            birthday_id = result[0]
            delete_wishlist_query = "DELETE FROM wishlists WHERE birthday_id = %s"
            cursor.execute(delete_wishlist_query, (birthday_id,))
            conn.commit()

        # Now, delete the birthday entry
        delete_birthday_query = "DELETE FROM birthdays WHERE nickname = %s"
        cursor.execute(delete_birthday_query, (nickname_to_delete,))
        conn.commit()

        await update.message.reply_text(f"День народження для {nickname_to_delete} успішно видалено!")
        cursor.close()
        conn.close()
        return ConversationHandler.END


        query = "DELETE FROM birthdays WHERE nickname = %s"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (nickname_to_delete,))
        conn.commit()

        await update.message.reply_text(f"День народження для {nickname_to_delete} успішно видалено!")
        cursor.close()
        conn.close()
        return ConversationHandler.END

    async def edit_birthday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Перевірка на адміністратора
        user = update.effective_user
        chat = await context.bot.get_chat(update.message.chat_id)
        member = await chat.get_member(user.id)

        if not member.status in ["administrator", "creator"]:
            await update.message.reply_text("Вибачте, але ця команда доступна тільки адміністраторам.")
            return ConversationHandler.END

        # Запит нікнейма для редагування
        await update.message.reply_text(
            "Введіть нікнейм користувача, чию дату народження потрібно змінити, наприклад @nickname")
        return ASK_EDIT_BIRTHDAY_NAME

    async def ask_edit_birthday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        nickname = update.message.text
        nicknames = await self.get_all_nicknames()

        if nickname not in nicknames:
            await update.message.reply_text("Цей нікнейм не знайдено в списку днів народження.")
            return ConversationHandler.END

        context.user_data['nickname'] = nickname
        await update.message.reply_text(f"Введіть нову дату народження для {nickname} у форматі YYYY-MM-DD")
        return ASK_EDIT_BIRTHDAY_DATE

    async def save_edit_birthday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        new_birthday = update.message.text
        nickname = context.user_data['nickname']

        query = "UPDATE birthdays SET birthday = %s WHERE nickname = %s"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (new_birthday, nickname))
        conn.commit()

        await update.message.reply_text(f"Дату народження для {nickname} оновлено на {new_birthday}.")
        cursor.close()
        conn.close()
        context.user_data.clear()
        return ConversationHandler.END

    async def view_wishlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Введіть нікнейм користувача, чий вішліст ви хочете переглянути, наприклад @nickname:")
        return ASK_BIRTHDAY_NAME

    async def ask_view_wishlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        nickname = update.message.text.strip()

        if not nickname.startswith('@'):
            await update.message.reply_text("Нікнейм має починатися з '@'.")
            return ConversationHandler.END

        nicknames = await self.get_all_nicknames()
        if nickname not in nicknames:
            await update.message.reply_text("Цей нікнейм не знайдено в списку днів народження.")
            return ConversationHandler.END

        query = "SELECT id FROM birthdays WHERE nickname = %s"
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (nickname,))
            result = cursor.fetchone()

            if result is None:
                await update.message.reply_text("Не вдалося знайти id для цього нікнейма.")
                return ConversationHandler.END

            birthday_id = result[0]

            # Додаємо chat_id в запит для перевірки
            wishlist_query = "SELECT item_name FROM wishlists WHERE birthday_id = %s AND chat_id = %s"
            cursor.execute(wishlist_query, (birthday_id, update.effective_chat.id))
            results = cursor.fetchall()

            if results:
                wishlist_text = f"Вішліст для {nickname}:\n"
                for item in results:
                    wishlist_text += f"🎁 {item[0]}\n"
            else:
                wishlist_text = f"Вішліст для {nickname} порожній."

            await update.message.reply_text(wishlist_text)
            return ConversationHandler.END


    async def my_wishlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        nickname = f"@{update.effective_user.username}"
        chat_id = update.effective_chat.id  # Отримуємо chat_id поточного чату
        query = "SELECT id FROM birthdays WHERE nickname = %s"

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (nickname,))
            result = cursor.fetchone()

            if result is None:
                await update.message.reply_text(
                    "Ваш день народження не зареєстрований, тому ви не можете переглянути свій вішліст.")
                return ConversationHandler.END

            birthday_id = result[0]

            # Фільтруємо побажання для цього користувача в конкретному чату
            wishlist_query = "SELECT item_name FROM wishlists WHERE birthday_id = %s AND chat_id = %s"
            cursor.execute(wishlist_query, (birthday_id, chat_id))
            results = cursor.fetchall()

            if results:
                wishlist_text = "Ваш вішліст:\n"
                for item in results:
                    wishlist_text += f"🎁 {item[0]}\n"
            else:
                wishlist_text = "Ваш вішліст порожній."

            await update.message.reply_text(wishlist_text)


    async def add_wish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Введіть ваше побажання:")
        return ASK_WISH

    async def save_wish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        wish = update.message.text
        nickname = f"@{update.effective_user.username}"
        chat_id = update.effective_chat.id  # Get chat_id of the current group

        # Перевіряємо, чи існує такий нікнейм в таблиці 'birthdays'
        query = "SELECT id FROM birthdays WHERE nickname = %s"

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (nickname,))
            result = cursor.fetchone()

            if result is None:
                await update.message.reply_text(
                    "Вибачте, але ви не можете додати побажання, оскільки ваш день народження не зареєстрований.")
                return ConversationHandler.END

            birthday_id = result[0]

            insert_query = "INSERT INTO wishlists (birthday_id, item_name, chat_id) VALUES (%s, %s, %s)"
            cursor.execute(insert_query, (birthday_id, wish, chat_id))
            conn.commit()

            await update.message.reply_text("Ваше побажання додано до вішлісту!")
            return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Введення дати дня народження скасовано")
        context.user_data.clear()
        return ConversationHandler.END

    async def get_all_nicknames(self):
        query = "SELECT nickname FROM birthdays"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        nicknames = [row[0] for row in results]
        cursor.close()
        conn.close()
        return nicknames