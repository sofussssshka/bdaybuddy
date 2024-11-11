from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, filters, ConversationHandler, MessageHandler, \
    CallbackContext

from src.database import get_connection

ASK_BIRTHDAY_NAME: int
ASK_BIRTHDAY_NAME, ASK_BIRTHDAY_DATE, ASK_DELETE_BIRTHDAY, ASK_EDIT_BIRTHDAY_NAME, ASK_EDIT_BIRTHDAY_DATE,ASK_WISH,ASK_DELETE_WISH = range(7)


class Commandshendler:
    def __init__(self, app):
        self.app = app
        self.setup()
        self.wishlist = {}

    def setup(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
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



    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Привіт, я BDayBuddy!Напишіть /help для списку команд.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Команди користувача:\n/view_birthdays - Переглянути всі дні народження\n/add_wish - Додати елемент до свого списку бажань\n/view_wishlist - Переглянути чийсь список бажань\n/my_wishlist - Переглянути свій список бажань\n\nКоманди адміністратора:\n/add_birthday - Додати новий день народження\n/edit_birthday - Редагувати існуючий день народження\n/delete_birthday - Видалити день народження")

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
        name = context.user_data['name']
        id = context.user_data['user_id']

        query = """
                    INSERT INTO birthdays (nickname, birthday)
                    VALUES (%s, %s)
                    """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (name, birthday))
        conn.commit()

        await update.message.reply_text(f"Дату народження для {context.user_data['name']} встановлено!")
        context.user_data.clear()


    async def save_birthday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        birthday = update.message.text
        name = context.user_data['name']
        id = context.user_data['user_id']

        query = """
                    INSERT INTO birthdays (nickname, birthday)
                    VALUES (%s, %s)
                    """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (name, birthday))
        conn.commit()

        await update.message.reply_text(f"Дату народження для {context.user_data['name']} встановлено!")
        context.user_data.clear()
        return ConversationHandler.END

    async def view_birthdays(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = "SELECT nickname, birthday FROM birthdays"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query)

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if results:
            birthdays_text = "Список днів народжень:\n"
            for nickname, birthday in results:
                birthdays_text += f"👤 {nickname}: 🎂 {birthday}\n"
        else:
            birthdays_text = "Список днів народжень порожній."
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
        nickname = update.message.text


        nicknames = await self.get_all_nicknames()
        if nickname not in nicknames:
            await update.message.reply_text("Цей нікнейм не знайдено в списку днів народження.")
            return ConversationHandler.END


        query = "SELECT id FROM birthdays WHERE nickname = %s"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (nickname,))
        result = cursor.fetchone()

        if result is None:
            await update.message.reply_text("Не вдалося знайти id для цього нікнейма.")
            cursor.close()
            conn.close()
            return ConversationHandler.END

        birthday_id = result[0]


        wishlist_query = "SELECT item_name FROM wishlists WHERE birthday_id = %s"
        cursor.execute(wishlist_query, (birthday_id,))
        results = cursor.fetchall()

        if results:
            wishlist_text = f"Вішліст для {nickname}:\n"
            for item in results:
                wishlist_text += f"🎁 {item[0]}\n"
        else:
            wishlist_text = f"Вішліст для {nickname} порожній."

        await update.message.reply_text(wishlist_text)
        cursor.close()
        conn.close()
        return ConversationHandler.END

    async def my_wishlist(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        nickname = f"@{update.effective_user.username}"


        query = "SELECT id FROM birthdays WHERE nickname = %s"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (nickname,))
        result = cursor.fetchone()

        if result is None:
            await update.message.reply_text(
                "Ваш день народження не зареєстрований, тому ви не можете переглянути свій вішліст.")
            cursor.close()
            conn.close()
            return ConversationHandler.END

        birthday_id = result[0]


        wishlist_query = "SELECT item_name FROM wishlists WHERE birthday_id = %s"
        cursor.execute(wishlist_query, (birthday_id,))
        results = cursor.fetchall()

        if results:
            wishlist_text = "Ваш вішліст:\n"
            for item in results:
                wishlist_text += f"🎁 {item[0]}\n"
        else:
            wishlist_text = "Ваш вішліст порожній."

        await update.message.reply_text(wishlist_text)
        cursor.close()
        conn.close()

    async def add_wish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Введіть ваше побажання:")
        return ASK_WISH

    async def save_wish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        wish = update.message.text
        nickname = f"@{update.effective_user.username}"

        # Перевіряємо, чи існує такий нікнейм в таблиці 'birthdays'
        query = "SELECT id FROM birthdays WHERE nickname = %s"
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (nickname,))
        result = cursor.fetchone()

        if result is None:
            await update.message.reply_text(
                "Вибачте, але ви не можете додати побажання, оскільки ваш день народження не зареєстрований.")
            cursor.close()
            conn.close()
            return ConversationHandler.END

        birthday_id = result[0]


        insert_query = "INSERT INTO wishlists (birthday_id, item_name) VALUES (%s, %s)"
        cursor.execute(insert_query, (birthday_id, wish))
        conn.commit()

        await update.message.reply_text("Ваше побажання додано до вішлісту!")
        cursor.close()
        conn.close()
        return ConversationHandler.END



    async def delete_wish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Введіть ваше побажання, яке потрібно видалити:")
        return ASK_DELETE_WISH

    async def confirm_delete_wish(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        wish = update.message.text
        user_id = update.effective_user


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