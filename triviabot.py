import twitchbot as tw
import gspreadmerger as gs
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
        print('SETUP CONFIG')
        Config.config = configparser.ConfigParser()
        Config.config.read('config.txt')

    @staticmethod
    def set_env_vars():
        try:
            os.environ['DISCORD_BOT_TOKEN'] = Config.config['DISCORD']['DISCORD_BOT_TOKEN']
            os.environ['DISCORD_BOT_PREFIX'] = Config.config['DISCORD']['DISCORD_BOT_PREFIX']
            os.environ['DISCORD_BOT_PREFIX_SECOND'] = Config.config['DISCORD']['DISCORD_BOT_PREFIX_SECOND']
            os.environ['DISCORD_ADMIN_ROLE'] = Config.config['DISCORD']['DISCORD_ADMIN_ROLE']
        except KeyError:
            #heroku here later
            raise


Config.load()
gs.load()

import discordbot as dc

loop = asyncio.get_event_loop()
try:
    asyncio.ensure_future(tw.start_coro())
    asyncio.ensure_future(dc.start_coro())
    loop.run_forever()
except KeyboardInterrupt:
    dc.bot.logout()
    loop.stop()
finally:
    loop.close()


