# -*- coding: utf-8 -*-
"""
@author: cleartonic
"""
import random
import json
import pandas as pd
import collections
import time
import socket
import re
import configparser
import os
import traceback
import asyncio
import gspreadmerger as gs

# SETTINGS
class Tw():
    infomessage = 'Trivia Bot loaded.'

    # SETTINGS FOR END USERS
    trivia_filename = 'triviaset'  # Specify the filename (default "triviaset")
    trivia_filetype = 'csv'  # Specify the file type. CSV (MUST be UTF-8), XLS, XLSX

    trivia_questions: int = 'INIT'  # Total questions to be answered for trivia round
    trivia_hinttime_1: int = 'INIT'  # Seconds to 1st hint after question is asked
    trivia_hinttime_2: int = 'INIT'  # Seconds to 2nd hint after question is asked
    trivia_skiptime: int = 'INIT'  # Seconds until the question is skipped automatically
    trivia_questiondelay: float = 'INIT'  # Seconds to wait after previous question is answered before asking next question
    trivia_bonusvalue: int = 'INIT'  # BONUS: How much points are worth in BONUS round
    admins = 'INIT'

    # CUSTOM
    trivia_answervalue = 'INIT'  # How much each question is worth (altered by DIFFICULTY)
    trivia_extra_points_per_avg_diff: int = 'INIT'
    trivia_extra_points_per_hard_diff: int = ' INIT'
    trivia_pre_questionasked_delay: float = 'INIT'
    trivia_creator_points_reward: int = 'INIT'

    userscores = {}  # Dictionary holding user scores, kept in '!' and loaded/created upon trivia. [1,2,3] 1: Session score 2: Total trivia points 3: Total wins
    COMMANDLIST = ["!triviastart", "!triviaend", "!top3", "!hint", "!score", "!next", "!stop", "!loadconfig", "!backuptrivia", "!loadtrivia", "!creator"]  # All commands
    SWITCH = True  # Switch to keep bot connection running
    trivia_active = False  # Switch for when trivia is being played
    trivia_questionasked = False  # Switch for when a question is actively being asked
    trivia_questionasked_time = 0  # Time when the last question was asked (used for relative time length for hints/skip)
    trivia_pre_questionasked_time = 0  # Same as above but for prequestion message
    trivia_hintasked = 0  # 0 = not asked, 1 = first hint asked, 2 = second hint asked
    session_questionno = 0  # Question # in current session
    session_bonusround = 0  # 0 - not bonus, 1 - bonus
    TIMER = 0  # Ongoing active timer

    tsrows = 0
    ts = None
    qs = None

    # CUSTOM
    column_position_id = 0
    column_position_category = 1
    column_position_question = 2
    column_position_answer = 3
    column_position_answer_second = 4
    column_position_creator = 5
    column_position_difficulty = 6
    trivia_pre_questionasked = False
    trivia_noname_creator = "Неизвестный"

    socket = None


class chatvar():  # Variables for IRC / Twitch chat function
    HOST = 'INIT'
    PORT = 'INIT'
    NICK = 'INIT'
    PASS = 'INIT'
    CHAN = 'INIT'
    RATE = 120  # messages per second
    CHAT_MSG = re.compile(r"^:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :")


# CODE

def loadconfig():
    config = configparser.ConfigParser()
    config.read('config.txt')
    Tw.trivia_filename = config['Trivia Settings']['trivia_filename']
    Tw.trivia_filetype = config['Trivia Settings']['trivia_filetype']
    Tw.trivia_questions = int(config['Trivia Settings']['trivia_questions'])
    Tw.trivia_hinttime_1 = int(config['Trivia Settings']['trivia_hinttime_1'])
    Tw.trivia_hinttime_2 = int(config['Trivia Settings']['trivia_hinttime_2'])
    Tw.trivia_skiptime = int(config['Trivia Settings']['trivia_skiptime'])
    Tw.trivia_questiondelay = int(config['Trivia Settings']['trivia_questiondelay'])
    Tw.trivia_bonusvalue = int(config['Trivia Settings']['trivia_bonusvalue'])

    Tw.trivia_answervalue = int(config['Custom Settings']['trivia_answervalue'])
    Tw.trivia_extra_points_per_avg_diff = int(config['Custom Settings']['trivia_extra_points_per_avg_diff'])
    Tw.trivia_extra_points_per_hard_diff = int(config['Custom Settings']['trivia_extra_points_per_hard_diff'])
    Tw.trivia_pre_questionasked_delay = int(config['Custom Settings']['trivia_pre_questionasked_delay'])
    Tw.trivia_creator_points_reward = int(config['Custom Settings']['trivia_creator_points_reward'])

    admin1 = config['Admin Settings']['admins']
    Tw.admins = admin1.split(',')

    chatvar.HOST = str(config['Bot Settings']['HOST'])
    chatvar.PORT = int(config['Bot Settings']['PORT'])
    chatvar.NICK = config['Bot Settings']['NICK']
    chatvar.PASS = config['Bot Settings']['PASS']
    chatvar.CHAN = config['Bot Settings']['CHAN']


##### Trivia start build. ts = "Trivia set" means original master trivia file. qs = "Quiz set" means what's going to be played with for the session
def load_trivia_file():
    # FUNCTION VARIABLES
    if Tw.trivia_filetype == 'csv':  # open trivia source based on type
        print('\ncsv\n')
        Tw.ts = pd.read_csv(Tw.trivia_filename + "." + Tw.trivia_filetype)
    Tw.tsrows = Tw.ts.shape[0]  # Dynamic # of rows based on triviaset
    Tw.qs = pd.DataFrame(columns=list(Tw.ts))  # Set columns in quizset to same as triviaset

    # Shows all column names
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    print(Tw.qs.head())


async def trivia_start():
    gs.build_trivia()
    load_trivia_file()

    sendmessage("Викторина запущена. Составление базы вопросов для сегодняшней игры...")
    qs_buildrows = 0  # starts at zero, must reach trivia_questions to be complete during while loop

    ### Loop through TS and build QS until qs_buildrows = trivia_numbers

    Tw.trivia_questions = int(Tw.tsrows)
    numberlist = []
    for i in range(Tw.tsrows):  # Create a list of all indices
        numberlist.append(i)
    while qs_buildrows < Tw.trivia_questions:
        temprando = random.choice(numberlist)
        numberlist.remove(temprando)
        try:
            Tw.qs = Tw.qs.append(Tw.ts.loc[temprando], verify_integrity=True)  # Check for duplicates with last argument, skip if so
            qs_buildrows += 1
        except:  # pass on duplicates and re-roll
            print("Duplicate index. This should not happen, dropping row from table. Please check config.txt's trivia_questions are <= total # of questions in trivia set.")
            Tw.ts.drop(Tw.ts.index[[temprando]])



    print("Quizset built.")
    Tw.trivia_active = True
    msg = "Викторина готова! Количество вопросов: " + str(Tw.trivia_questions) + ". Начало викторины через " + str(Tw.trivia_questiondelay) + " секунд."
    sendmessage(msg)
    await asyncio.sleep(Tw.trivia_questiondelay)
    trivia_call_prequestion()


def loadscores():
    # Load score list

    # TODO Cloudcube downlaod

    try:
        with open('userscores.txt', 'r') as fp:
            print("Score list loaded.")
            Tw.userscores = json.load(fp)
    except (FileNotFoundError, IOError, json.decoder.JSONDecodeError):
        with open('userscores.txt', "w") as fp:
            Tw.userscores = {'trivia_dummy': [0, 0, 0]}
            json.dump(Tw.userscores, fp)


def dumpscores():
    with open('userscores.txt', 'w') as fp:
        json.dump(Tw.userscores, fp)

    # TODO Cloudcube upload


### Trivia command switcher
async def trivia_commandswitch(cleanmessage, username):
    # ADMIN ONLY COMMANDS
    if username in Tw.admins:
        if cleanmessage == "!triviastart":
            if Tw.trivia_active:
                print("Trivia already active.")
            else:
                await trivia_start()
        if cleanmessage == "!triviaend":
            if Tw.trivia_active:
                await trivia_end()
        if cleanmessage == "!stop":
            stopbot()
        if cleanmessage == "!loadconfig":
            loadconfig()
            sendmessage("Config reloaded.")
        if cleanmessage == "!backuptrivia":
            trivia_savebackup()
            sendmessage("Backup created.")
        if cleanmessage == "!loadtrivia":
            await trivia_loadbackup()
        if cleanmessage == "!next":
            await trivia_skipquestion()

    # ACTIVE TRIVIA COMMANDS
    if Tw.trivia_active:
        if cleanmessage == "!top3":
            topscore = trivia_top3score()
            print("topscore", topscore)
            print("Len", len(topscore))
            if (len(topscore) >= 3):
                msg = "In 1st: " + str(topscore[0][0]) + " " + str(topscore[0][1]) + " points. 2nd place: " + str(topscore[1][0]) + " " + str(
                    topscore[1][1]) + " points. 3rd place: " + str(topscore[2][0]) + " " + str(topscore[2][1]) + " points."
                sendmessage(msg)
            if (len(topscore) == 2):
                msg = "In 1st: " + str(topscore[0][0]) + " " + str(topscore[0][1]) + " points. 2nd place: " + str(topscore[1][0]) + " " + str(topscore[1][1]) + " points."
                sendmessage(msg)
            if (len(topscore) == 1):
                msg = "In 1st: " + str(topscore[0][0]) + " " + str(topscore[0][1]) + " points."
                sendmessage(msg)

        if cleanmessage == "!hint":
            if Tw.trivia_hintasked == 0:
                trivia_askhint(0)
            if Tw.trivia_hintasked == 1:
                trivia_askhint(0)
            if Tw.trivia_hintasked == 2:
                trivia_askhint(1)

        if cleanmessage == "!bonus":
            if Tw.session_bonusround == 0:
                trivia_startbonus()
                Tw.session_bonusround = 1
            if Tw.session_bonusround == 1:
                trivia_endbonus()
                Tw.session_bonusround = 0

    # GLOBAL COMMANDS
    if cleanmessage == "!score":
        trivia_userscore(username)


### Custom convenience
def show_stack():
    for line in traceback.format_stack():
        print(line.strip())


def category_str():
    category = "Без категории"
    # category = str(Tw.qs.iloc[Tw.session_questionno, Tw.column_position_category])
    return category


def difficulty_str():
    difficulty = "средняя"
    if Tw.qs.iloc[Tw.session_questionno, Tw.column_position_difficulty] == 0:
        difficulty = "легкая"
    if Tw.qs.iloc[Tw.session_questionno, Tw.column_position_difficulty] == 2:
        difficulty = "тяжелая"
    return difficulty


def creator_str():
    creator = Tw.trivia_noname_creator
    if len(Tw.qs.iloc[Tw.session_questionno, Tw.column_position_creator]) >= 1:
        creator = Tw.qs.iloc[Tw.session_questionno, Tw.column_position_creator]
    return creator


def difficulty_extra_user_points():
    difficulty = Tw.qs.iloc[Tw.session_questionno, Tw.column_position_difficulty]
    extra_points = Tw.trivia_extra_points_per_avg_diff
    if difficulty == 0:
        extra_points = 0
    if difficulty == 2:
        extra_points = Tw.trivia_extra_points_per_hard_diff
    return extra_points


def difficulty_extra_creator_points():
    difficulty = Tw.qs.iloc[Tw.session_questionno, Tw.column_position_difficulty]
    extra_points = 1
    if difficulty == 0:
        extra_points = 0
    if difficulty == 2:
        extra_points = 2
    return extra_points


def reset_question_timings():
    Tw.trivia_hintasked = 0
    Tw.trivia_questionasked = False
    Tw.trivia_questionasked_time = 0


def reset_prequestion_timings():
    Tw.trivia_pre_questionasked = False
    Tw.trivia_pre_questionasked_time = 0


### Call trivia question
def trivia_call_prequestion():
    Tw.trivia_pre_questionasked = True
    Tw.trivia_pre_questionasked_time = round(time.time())

    premsg = "Вопрос #" + str(
        Tw.session_questionno + 1) + " в категории [" + category_str().capitalize() + "], сложность [" + difficulty_str().capitalize() + "], от пользователя [" + creator_str() + "] ..."
    sendmessage(premsg)
    print(premsg)


def trivia_callquestion():
    reset_prequestion_timings()
    Tw.trivia_questionasked = True
    Tw.trivia_questionasked_time = round(time.time())

    msg = "Внимание, ВОПРОС: \"" + Tw.qs.iloc[Tw.session_questionno, Tw.column_position_question] + "\""

    sendmessage(msg)
    print("Question #" + str(Tw.session_questionno + 1) + ": | ANSWER: " + Tw.qs.iloc[Tw.session_questionno, Tw.column_position_answer])


async def trivia_answer(username, cleanmessage):
    Tw.trivia_questionasked = False

    # Answered user awarded points
    answer_points = Tw.trivia_answervalue + difficulty_extra_user_points()
    key = next((x for x in Tw.userscores.keys() if x == username), None)
    if key:
        Tw.userscores[username][0] += answer_points
        Tw.userscores[username][1] += answer_points
    else:
        print("Failed to find user! Adding new")
        Tw.userscores[username] = [answer_points, answer_points, 0]  # sets up new user

    # Creator awarded points
    msg_creator = ''
    if creator_str() != Tw.trivia_noname_creator:
        creator_points = Tw.trivia_creator_points_reward + difficulty_extra_creator_points()
        msg_creator = "Автор вопроса " + creator_str() + " получает " + str(creator_points) + " trivia points"

        key = next((x for x in Tw.userscores.keys() if x == creator_str()), None)
        if key:
            Tw.userscores[creator_str()][0] += creator_points
            Tw.userscores[creator_str()][1] += creator_points
        else:
            print("Failed to find creator! Adding new")
            Tw.userscores[creator_str()] = [creator_points, creator_points, 0]  # sets up new user

    dumpscores()  # Save all current scores
    msg = str(username) + " правильно отвечает на вопрос #" + str(Tw.session_questionno + 1) + "! Ответ ** " + str(
        Tw.qs.iloc[Tw.session_questionno, Tw.column_position_answer]) + " ** оценивается в " + str(answer_points) + " trivia points. " + str(
        username) + " уже заработал(а) " + str(Tw.userscores[username][0]) + " trivia points в сегодняшней игре."
    msg = msg + " " + msg_creator

    print(msg)
    sendmessage(msg)
    await asyncio.sleep(Tw.trivia_questiondelay)
    Tw.session_questionno += 1
    reset_question_timings()
    reset_prequestion_timings()
    trivia_savebackup()
    if Tw.trivia_questions == Tw.session_questionno:  # End game check
        await trivia_end()
    else:
        print("Next question called...")
        trivia_call_prequestion()


### Finishes trivia by getting top 3 list, then adjusting final message based on how many participants. Then dumpscore()
async def trivia_end():
    topscore = trivia_top3score()  # Argument "1" will return the first in the list (0th position) for list of top 3
    trivia_clearscores()
    if (len(topscore) == 0):
        msg = "Нет завершенных вопросов. Результаты пусты."
        sendmessage(msg)

    else:
        msg = "Викторина окончена! Подсчет результатов..."
        sendmessage(msg)
        await asyncio.sleep(2)
        trivia_assignwinner(topscore[0][0])
        if len(topscore) >= 3:
            msg = " *** " + str(topscore[0][0]) + " *** победитель сегодняшней викторины с " + str(topscore[0][1]) + " trivia points! 2-ое место: " + str(
                topscore[1][0]) + " " + str(topscore[1][1]) + " trivia points. 3-е место: " + str(topscore[2][0]) + " " + str(topscore[2][1]) + " trivia points."
            sendmessage(msg)
        if len(topscore) == 2:
            msg = " *** " + str(topscore[0][0]) + " *** победитель сегодняшней викторины с " + str(topscore[0][1]) + " trivia points! 2-ое место: " + str(
                topscore[1][0]) + " " + str(topscore[1][1]) + " trivia points."
            sendmessage(msg)
        if len(topscore) == 1:
            msg = " *** " + str(topscore[0][0]) + " *** победитель сегодняшней викторины с " + str(topscore[0][1]) + " trivia points!"
            sendmessage(msg)

    dumpscores()
    await asyncio.sleep(3)
    msg2 = "Благодарим за участие! Увидимся на последующих викторинах!"
    sendmessage(msg2)

    Tw.session_questionno = 0  # reset variables for trivia
    Tw.trivia_active = False
    reset_question_timings()
    reset_prequestion_timings()
    Tw.qs = pd.DataFrame(columns=list(Tw.ts))

    # Clear backup files upon finishing trivia
    os.remove('backup/backupquizset.csv')
    os.remove('backup/backupscores.txt')
    os.remove('backup/backupsession.txt')


async def trivia_routinechecks():  # after every time loop, routine checking of various vars/procs
    Tw.TIMER = round(time.time())

    if Tw.trivia_questions == Tw.session_questionno:  # End game check
        await trivia_end()

    if ((Tw.TIMER - Tw.trivia_questionasked_time) > Tw.trivia_hinttime_2 and Tw.trivia_active and Tw.trivia_hintasked == 1 and Tw.trivia_questionasked):
        Tw.trivia_hintasked = 2
        trivia_askhint(1)  # Ask second hint

    if ((Tw.TIMER - Tw.trivia_questionasked_time) > Tw.trivia_hinttime_1 and Tw.trivia_active and Tw.trivia_hintasked == 0 and Tw.trivia_questionasked):
        Tw.trivia_hintasked = 1
        trivia_askhint(0)  # Ask first hint

    if ((Tw.TIMER - Tw.trivia_questionasked_time) > Tw.trivia_skiptime and Tw.trivia_active and Tw.trivia_questionasked):
        await trivia_skipquestion()  # Skip question after time is up

    if ((
            Tw.TIMER - Tw.trivia_pre_questionasked_time) > Tw.trivia_pre_questionasked_delay and Tw.trivia_active and Tw.trivia_pre_questionasked and not Tw.trivia_questionasked):
        trivia_callquestion()  # Ask question after prequestion delay


def trivia_askhint(hinttype=0):  # hinttype: 0 = 1st hint, 1 = 2nd hint
    if (hinttype == 0 and Tw.trivia_questionasked == True):  # type 0, replace 2 out of 3 chars with _
        print(str(Tw.session_questionno));
        prehint = str(Tw.qs.iloc[Tw.session_questionno, Tw.column_position_answer])
        listo = []
        hint = ''
        counter = 0
        for i in prehint:
            if counter % 3 >= 0.7:
                listo += " _ "
            else:
                listo += i
            counter += 1
        for i in range(len(listo)):
            hint += hint.join(listo[i])
        sendmessage("Hint #1: " + hint)

    if (hinttype == 1 and Tw.trivia_questionasked == True):  # type 1, replace vowels with _
        prehint = str(Tw.qs.iloc[Tw.session_questionno, Tw.column_position_answer])
        hint = re.sub('[aeiou]', ' _ ', prehint, flags=re.I)
        sendmessage("Hint #2: " + hint)


async def trivia_skipquestion():
    if Tw.trivia_active:
        Tw.session_questionno += 1
        reset_question_timings()
        reset_prequestion_timings()

        sendmessage("Время на ответ истекло или вопрос был пропущен. Правильный ответ: " + str(Tw.qs.iloc[Tw.session_questionno - 1, Tw.column_position_answer]) + ". Переход к следующему вопросу")
        await asyncio.sleep(Tw.trivia_questiondelay)
        if Tw.trivia_questions == Tw.session_questionno:  # End game check
            await trivia_end()
        else:
            trivia_call_prequestion()


### B O N U S (disabled for now by @enikkk)
def trivia_startbonus():
    msg = "B O N U S Round begins! Questions are now worth " + str(Tw.trivia_bonusvalue) + " points!"
    sendmessage(msg)
    Tw.trivia_answervalue = Tw.trivia_bonusvalue


def trivia_endbonus():
    msg = "Bonus round is over! Questions are now worth 1 point."
    sendmessage(msg)
    Tw.trivia_answervalue = 1


### Top 3 trivia
def trivia_top3score():
    data2 = {}  # temp dictionary just for keys & sessionscore
    for i in Tw.userscores.keys():
        if Tw.userscores[i][0] > 0:
            data2[i] = Tw.userscores[i][0]

    data3 = collections.Counter(data2)  # top 3 counter
    data3.most_common()
    top3 = []  # top 3 list
    for k, v in data3.most_common(3):
        top3 += [[k, v]]
    return top3


### clears scores and assigns a win to winner
def trivia_clearscores():
    for i in Tw.userscores.keys():
        Tw.userscores[i][0] = 0


### Add +1 to winner's win in userscores
def trivia_assignwinner(winner):
    Tw.userscores[winner][2] += 1


### temp function to give 100 score to each
def trivia_givescores():
    for i in Tw.userscores.keys():
        Tw.userscores[i][0] = random.randrange(0, 1000)


def trivia_userscore(username):
    key = next((x for x in Tw.userscores.keys() if x == username), None)
    if key:
        msg = str(username) + " имеет " + str(Tw.userscores[username][0]) + " trivia points в сегодняшней игре, " + str(
            Tw.userscores[username][1]) + " за все время и " + str(Tw.userscores[username][2]) + " побед за первое место в ежедневных играх."
        sendmessage(msg)
    else:
        msg = str(username) + " не найден в базе участников. Зарабатывайте trivia points правильно отвечая на вопросы других участников или задавайте свои вопросы!"
        sendmessage(msg)


### Chat message sender func
def sendmessage(msg):
    answermsg = ":" + chatvar.NICK + "!" + chatvar.NICK + "@" + chatvar.NICK + ".tmi.twitch.tv PRIVMSG " + chatvar.CHAN + " : " + msg + "\r\n"
    answermsg2 = answermsg.encode("utf-8")
    Tw.socket.send(answermsg2)


### STOP BOT (sets loop to false)
def stopbot():
    Tw.SWITCH = False


### CALL TIMER
def calltimer():
    print("Timer: " + str(Tw.TIMER))


### BACKUP SAVING/LOADING
def trivia_savebackup():  # backup session saver
    # Save session position/variables
    if not os.path.exists('backup/'):
        os.mkdir('backup/')
    config2 = configparser.ConfigParser()
    config2['DEFAULT'] = {'session_questionno': Tw.session_questionno, 'trivia_answervalue': Tw.trivia_answervalue, 'session_bonusround': Tw.session_bonusround}
    with open('backup/backupsession.txt', 'w') as c:
        config2.write(c)

        # Save CSV of quizset
    Tw.qs.to_csv('backup/backupquizset.csv', index=False, encoding='utf-8')
    # Save session scores
    with open('backup/backupscores.txt', 'w') as fp:
        json.dump(Tw.userscores, fp)


async def trivia_loadbackup():  # backup session loader
    if Tw.trivia_active:
        sendmessage("Викторина уже запущена. Предыдущая сессия не была загружена.")
    else:
        # Load session position/variables
        config2 = configparser.ConfigParser()
        config2.read('backup/backupsession.txt')

        Tw.session_questionno = int(config2['DEFAULT']['session_questionno'])

        # Load quizset
        Tw.qs = pd.read_csv('backup/backupquizset.csv', encoding='utf-8')

        # Load session scores

        try:
            with open('backup/backupscores.txt', 'r') as fp:
                print("Score list loaded.")
                Tw.userscores = json.load(fp)
        except (FileNotFoundError, IOError, json.decoder.JSONDecodeError):
            with open('backup/backupscores.txt', "w") as fp:
                print("No score list, creating...")
                Tw.userscores = {'trivia_dummy': [0, 0, 0]}
                json.dump(Tw.userscores, fp)

        print("Loaded backup.")
        Tw.trivia_active = True
        sendmessage("Предыдущая сессия успешна загружена. Викторина начнется через " + str(Tw.trivia_questiondelay) + " секунд.")
        await asyncio.sleep(Tw.trivia_questiondelay)
        trivia_call_prequestion()


############### CHAT & BOT CONNECT ###############
async def scanloop():
    try:
        response = Tw.socket.recv(1024).decode("utf-8")
        if response == "PING :tmi.twitch.tv\r\n":  # Ping
            Tw.socket.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
            print("Pong sent")
        else:  # Checking correct answers (move to new function)
            print(response)
            username = re.search(r"\w+", response).group(0)
            if username == chatvar.NICK:  # Ignore this bot's messages
                pass

            else:
                message = chatvar.CHAT_MSG.sub("", response)
                cleanmessage = re.sub(r"\s+", "", message, flags=re.UNICODE)
                print("USER RESPONSE: " + username + " : " + message)
                if cleanmessage in Tw.COMMANDLIST:
                    print("Command recognized.")
                    await trivia_commandswitch(cleanmessage, username)
                    await asyncio.sleep(1)

                if bool(re.match("\\b" + Tw.qs.iloc[Tw.session_questionno, Tw.column_position_answer] + "\\b", message, re.IGNORECASE)) and (
                        username.lower() != creator_str().lower()):  # strict new matching
                    print("Answer recognized.")
                    await trivia_answer(username, cleanmessage)
                if bool(re.match("\\b" + str(Tw.qs.iloc[Tw.session_questionno, Tw.column_position_answer_second]) + "\\b", message, re.IGNORECASE)) and (
                        username.lower() != creator_str().lower()):  # strict new matching
                    print("Answer recognized.")
                    await trivia_answer(username, cleanmessage)
    except socket.error as e:
        import errno
        if e.errno == errno.EAGAIN: pass # Ignore "[Errno 35] Resource temporarily unavailable" exception
        else: raise
    except (AttributeError, IndexError) as e:
        print("{}: {}".format(type(e), e))
        await asyncio.sleep(2)


## STARTING PROCEDURES
def load_files():
    print("Loading config and scores...")
    loadconfig()
    loadscores()


async def connect_socket():
    print(Tw.SWITCH)
    if Tw.SWITCH:
        s = socket.socket()
        s.connect((chatvar.HOST, chatvar.PORT))
        s.send("PASS {}\r\n".format(chatvar.PASS).encode("utf-8"))
        s.send("NICK {}\r\n".format(chatvar.NICK).encode("utf-8"))
        s.send("JOIN {}\r\n".format(chatvar.CHAN).encode("utf-8"))
        await asyncio.sleep(1)
        Tw.socket = s
        sendmessage(Tw.infomessage)
        s.setblocking(False)


# Infinite loop while bot is active to scan messages & perform routines
async def trivia_loop():
    print(Tw.SWITCH)
    while Tw.SWITCH:
        if Tw.trivia_active:
            await trivia_routinechecks()
        await scanloop()
        await asyncio.sleep(1 / chatvar.RATE)


async def start_coro():
    load_files()
    await connect_socket()
    await trivia_loop()

