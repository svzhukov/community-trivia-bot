import os
import traceback
import discord
from discord.ext import commands
import gspreadmerger as gs


class Permissions:
    class AdminRoleCheckError(commands.CommandError):
        def __init__(self, message: str = None):
            self.message = message if message else "Comand is restricted to bot admin role"

        def __repr__(self):
            return self.message

    class RoleManagementCheckError(commands.CommandError):
        def __init__(self, message: str = None):
            self.message = message if message else "Command requires discord role management permissions"

        def __repr__(self):
            return self.message

    @staticmethod
    def has_bot_admin_role(ctx) -> bool:
        role = os.environ['DISCORD_ADMIN_ROLE']
        try:
            if int(role) in [dc_role.id for dc_role in ctx.message.author.roles]:
                return True
            else:
                raise Permissions.AdminRoleCheckError
        except ValueError:
            if role in [dc_role.name for dc_role in ctx.message.author.roles]:
                return True
            else:
                raise Permissions.AdminRoleCheckError

    @staticmethod
    def has_role_management_permissions(ctx) -> bool:
        if True in [dc_role.permissions.manage_roles for dc_role in ctx.message.author.roles] or ctx.message.author.id == ctx.guild.owner.id:
            return True
        else:
            raise Permissions.RoleManagementCheckError


#######################################################################
bot = commands.Bot(command_prefix=(os.environ['DISCORD_BOT_PREFIX'], os.environ['DISCORD_BOT_PREFIX_SECOND']))
@bot.command(name='list')
async def com_merge_list(ctx):
    await gs.merge_list(ctx)


@bot.command(name='req')
async def com_merge_req(ctx, sheet_id):
    await gs.merge_req(ctx, sheet_id)


@bot.command(name='merge')
@commands.check(Permissions.has_bot_admin_role)
async def merge_com(ctx, sheet_id):
    await gs.merge_com(ctx, sheet_id)


@bot.command(name='adminrole')
@commands.check(Permissions.has_role_management_permissions)
async def com_admin_role(ctx, *args):
    if len(args):
        os.environ['DISCORD_ADMIN_ROLE'] = ' '.join(args)
        await ctx.send("New bot admin role has been set to **" + ' '.join(args) + "**")
    else:
        await ctx.send("Current bot admin role is **{}**, to set a new one specify either role id or role name"
                       .format(os.environ['DISCORD_ADMIN_ROLE']))


@bot.command(name='respond')
async def com_respond(ctx):
    await ctx.send("Hello, I'm alive and responding!")


@bot.command(name='test')
@commands.check(Permissions.has_bot_admin_role)
async def com_test(ctx):
    await ctx.send('This is a TEST, admin test yes')


# Discord bot events
@bot.event
async def on_ready():
    print('Trivia discord bot is ready')
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("regaet kvinoy"))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, Permissions.AdminRoleCheckError) or isinstance(error, Permissions.RoleManagementCheckError):
        await ctx.send(error.message)
    elif isinstance(error, discord.ext.commands.errors.CommandOnCooldown):
        await ctx.send("**{}**, {}".format(ctx.message.author.name, error))
    elif isinstance(error, discord.ext.commands.errors.CommandNotFound):
        # Disable the spam from other bots with the same prefixes
        pass
    elif isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
        print(error)
    else:
        traceback.print_exception(type(error), error, error.__traceback__)


async def start_coro():
    await bot.start(os.environ['DISCORD_BOT_TOKEN'])