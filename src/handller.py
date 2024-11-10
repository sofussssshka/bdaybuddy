from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, filters, ConversationHandler, MessageHandler, \
    CallbackContext

from src.database import get_connection

ASK_BIRTHDAY_NAME, ASK_BIRTHDAY_DATE = range(2)


class Commandshendler:
    def __init__(self, app):
        self.app = app
        self.setup()

    def setup(self):
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(ConversationHandler(
            entry_points=[CommandHandler("add_birthday", self.add_birthday)],
            states={
                ASK_BIRTHDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_birthday)],
                ASK_BIRTHDAY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_birthday)]

            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        ))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Привіт, я BDayBuddy!Напишіть /help для списку команд.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Команди користувача:\n/view_birthdays - Переглянути всі дні народження\n/add_wish - Додати елемент до свого списку бажань\n/view_wishlist - Переглянути чийсь список бажань\n/my_wishlist - Переглянути свій список бажань\n\nКоманди адміністратора:\n/add_birthday - Додати новий день народження\n/edit_birthday - Редагувати існуючий день народження\n/delete_birthday - Видалити день народження")

    async def add_birthday(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Введіть нікнейм користувача, наприклад @nickname")
        return ASK_BIRTHDAY_NAME

    async def ask_birthday(self, update: Update, context: CallbackContext):
        text=update.message.text
        nicknames= await self.get_all_nicknames()

        if text in nicknames:
            await update.message.reply_text("Дата народження для користувача вже існує!")
            return ConversationHandler.END

        context.user_data['name'] = update.message.text
        entities = update.message.entities
        # for entity,username in entities.items():
        #     if username.startswith('@'):
        #         context.user_data['user_id'] = context.bot.get_chat(username).id
        for entity in entities:
            if entity.type == MessageEntity.MENTION:
                username=update.message.text[entity.offset:entity.offset + entity.length]
                #TODO:замінити на айдішники
                context.user_data['user_id'] = username
        await update.message.reply_text(f"Введіть дату народження для {context.user_data['name']} в форматі YYYY-MM-DD")
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
