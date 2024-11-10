from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from handller import Commandshendler

def main():

    application = ApplicationBuilder().token("7782910038:AAHdMjaPLSvNRDGReYQ2eOXvIvl6TTniwf8").build()

    Commandshendler(application)
    application.run_polling()




if __name__ == "__main__":
    main()