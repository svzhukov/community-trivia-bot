import asyncio
import os
import configparser


class Config:
    config = None

    @staticmethod
    def load():
        Config.setup_config()
        Config.set_env_vars()

    @staticmethod
    def setup_config():
        Config.config = configparser.ConfigParser()
        Config.config.read('config.txt')

    @staticmethod
    def set_env_vars():
        try:
            os.environ['DISCORD_BOT_TOKEN'] = Config.config['DISCORD']['DISCORD_BOT_TOKEN']
            os.environ['DISCORD_BOT_PREFIX'] = Config.config['DISCORD']['DISCORD_BOT_PREFIX']

            os.environ['CLOUDCUBE_ACCESS_KEY_ID'] = Config.config['AWS']['CLOUDCUBE_ACCESS_KEY_ID']
            os.environ['CLOUDCUBE_SECRET_ACCESS_KEY'] = Config.config['AWS']['CLOUDCUBE_SECRET_ACCESS_KEY']

            os.environ['GSPREAD_API_MAIL'] = Config.config['GSPREAD']['GSPREAD_API_MAIL']
            os.environ['GSPREAD_ADMIN_MAILS'] = Config.config['GSPREAD']['GSPREAD_ADMIN_MAILS']
            os.environ['GSPREAD_MAIN_DB_SHEET_ID'] = Config.config['GSPREAD']['GSPREAD_MAIN_DB_SHEET_ID']
            os.environ['GSPREAD_CATEGORIES_SHEET_ID'] = Config.config['GSPREAD']['GSPREAD_CATEGORIES_SHEET_ID']

            os.environ['TRIVIA_HINTTIME_1'] = Config.config['Trivia Settings']['TRIVIA_HINTTIME_1']
            os.environ['TRIVIA_HINTTIME_2'] = Config.config['Trivia Settings']['TRIVIA_HINTTIME_2']
            os.environ['TRIVIA_SKIPTIME'] = Config.config['Trivia Settings']['TRIVIA_SKIPTIME']
            os.environ['TRIVIA_QUESTIONDELAY'] = Config.config['Trivia Settings']['TRIVIA_QUESTIONDELAY']
            os.environ['TRIVIA_PRE_QUESTIONASKED_DELAY'] = Config.config['Trivia Settings']['TRIVIA_PRE_QUESTIONASKED_DELAY']

            os.environ['TRIVIA_ANSWERVALUE'] = Config.config['Custom Settings']['TRIVIA_ANSWERVALUE']
            os.environ['TRIVIA_EXTRA_POINTS_PER_AVG_DIFF'] = Config.config['Custom Settings']['TRIVIA_EXTRA_POINTS_PER_AVG_DIFF']
            os.environ['TRIVIA_EXTRA_POINTS_PER_HARD_DIFF'] = Config.config['Custom Settings']['TRIVIA_EXTRA_POINTS_PER_HARD_DIFF']
            os.environ['TRIVIA_CREATOR_POINTS_REWARD'] = Config.config['Custom Settings']['TRIVIA_CREATOR_POINTS_REWARD']

            os.environ['BOT_ADMINS'] = Config.config['Bot Settings']['BOT_ADMINS']
            os.environ['BOT_CHANNEL'] = Config.config['Bot Settings']['BOT_CHANNEL']
            os.environ['BOT_NICK'] = Config.config['Bot Settings']['BOT_NICK']
            os.environ['BOT_PASS'] = Config.config['Bot Settings']['BOT_PASS']
            print('All env vars successfully set from config')

        except KeyError:
            print('Failed to load from config, using already set env vars')


Config.load()
import discordbot as dc
import gspreadmerger as gs
import twitchbot as tw

loop = asyncio.get_event_loop()
try:
    gs.load()
    asyncio.ensure_future(tw.start_coro())
    asyncio.ensure_future(dc.start_coro())
    loop.run_forever()
except KeyboardInterrupt:
    dc.bot.logout()
    loop.stop()
finally:
    loop.close()


