import flask, telebot, json, re
from functools import wraps
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

from bot.config import botcfg
from bot import util

LOG_CATEGORY = 'VSLBOT.MAIN'
TELEBOT_WH_PATH = '/%s' % botcfg['TELEBOT_WH_PATH']

logger = util.get_logger(LOG_CATEGORY)
sessions = util.get_session_storage()
pat = re.compile('^\/?(hi|hello|start|ciao|help|hola|ola|all?o)$')

bot = util.get_bot()
app = flask.Flask(__name__)


@app.route("/")
def index():
    return ''


@app.route(TELEBOT_WH_PATH, methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)


@bot.message_handler(commands=['stop', 'clean'])
def handle_stop(message):
    '''Stop any pending queries and clear any inline keyboards'''
    chat_id = message.chat.id
    if chat_id in sessions:
        del sessions[chat_id]
    keyboard = ReplyKeyboardRemove()
    bot.send_message(message.chat.id, 'Talk to you soon!', reply_markup=keyboard)


def return_on_stop(f):
    @wraps(f)
    def wrapper(message, *args, **kwds):
        if message.text.strip().lower() in ['/stop', '/clean']:
            return False
        return f(message, *args, **kwds)
    return wrapper


@bot.message_handler(commands=['member'])
def handle_registration(message):
    chat_id = message.chat.id
    if chat_id in sessions:
        return False
    sessions[chat_id] = util.User(message.chat.first_name, message.chat.last_name)
    fname = 'there'
    if message.chat.first_name:
        fname = message.chat.first_name
    msg = bot.reply_to(message, """Howdy %s, what's your full name?
""" % fname)
    bot.register_next_step_handler(msg, process_name_step)


@return_on_stop
def process_name_step(message):
    chat_id = message.chat.id
    try:
        user = sessions[chat_id]
        user.first_name, user.last_name = message.text.strip().split(' ')
        # Commit the change
        sessions[chat_id] = user
        msg = bot.reply_to(message, 'Your email address, please:')
        bot.register_next_step_handler(msg, process_email_step)
    except Exception as e:
        logger.error('process_name_step: [chat:%d] Could not get first and last names - %s' % (chat_id, e))
        msg = bot.reply_to(message, 'Please enter first & last names:')
        bot.register_next_step_handler(msg, process_name_step)


@return_on_stop
def process_email_step(message):
    chat_id = message.chat.id
    try:
        if chat_id not in sessions:
            return False
        email = message.text.strip().lower()
        if not util.check_email(email):
            raise Exception('Invalid email %s' % email)
        user = sessions[chat_id]
        user.email = email
        # Commit the change
        sessions[chat_id] = user
        # Do processing
        bot.send_message(chat_id, 'Nice to meet you, %s. We have recorded your email %s.' % (user.first_name, user.email))
        # Session is done, clean up
        del sessions[chat_id]
    except Exception as e:
        logger.error('process_email_step: [chat:%d] Could not obtain email - %s' % (chat_id, e))
        msg = bot.reply_to(message, "Ok, please enter your email:")
        bot.register_next_step_handler(msg, process_email_step)


@bot.message_handler(func=lambda message: True)
def handle_undefined(message):
    chat_id = message.chat.id
    logger.info('sessions = %s' % sessions)
    if chat_id in sessions:
        return False
    if message.chat.first_name:
        fname = message.chat.first_name
    else:
        fname = "there"
    bot.reply_to(message, """Hi %s, I'm a bot from VietStartupLondon.
Here are the commands:
    /events: Query upcoming and past events
    /member: Register memebership
    /stop: Bot will stop asking you questions
""" % fname)
