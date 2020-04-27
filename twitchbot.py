from __future__ import annotations

import random
import json
import pandas as pd
import time
import socket
import re
import os
import jsonpickle
import asyncio
import gspreadmerger as gs
from typing import List


# SETTINGS
class Var:
    infomessage = 'Trivia Bot loaded.'
    guide = 'https://docs.google.com/document/d/1bzddGypBaQOqkfyok-mK2hzmskkldnF2yOU2mmy3wa8/edit?usp=sharing'

    # SETTINGS FOR END USERS
    trivia_hinttime_1: int = None  # Seconds to 1st hint after question is asked
    trivia_hinttime_2: int = None  # Seconds to 2nd hint after question is asked
    trivia_skiptime: int = None  # Seconds until the question is skipped automatically
    trivia_questiondelay: float = None  # Seconds to wait after previous question is answered before asking next question
    admins = None

    # CUSTOM
    trivia_answervalue = None  # How much each question is worth (altered by DIFFICULTY)
    trivia_extra_points_per_avg_diff: int = None
    trivia_extra_points_per_hard_diff: int = None
    trivia_pre_questionasked_delay: float = None
    trivia_creator_points_reward: int = None

    COMMANDLIST = ["!triviastart", "!triviaend", "!top3", "!hint", "!score", "!skip", "!trivia", "!ask", "!respond"]  # All commands
    SWITCH = True  # Switch to keep bot connection running
    trivia_active = False  # Switch for when trivia is being played
    trivia_questionasked = False  # Switch for when a question is actively being asked
    trivia_questionasked_time = 0  # Time when the last question was asked (used for relative time length for hints/skip)
    trivia_pre_questionasked_time = 0  # Same as above but for prequestion message
    trivia_hintasked = 0  # 0 = not asked, 1 = first hint asked, 2 = second hint asked
    session_questionno = 0  # Question # in current session
    TIMER = 0  # Ongoing active timer

    trivia_pre_questionasked = False
    trivia_min_questions_count = 0


class Trivia:
    active_trivia = None

    def __init__(self, data_frame):
        self.data_frame = data_frame
        self.question_idx = 0
        self.active_question = None
        self.question_start_time = 0

        self.trivia_pre_questionasked = False
        self.trivia_pre_questionasked_time = 0
        Question.build_questions(data_frame)

    def start(self):
        pass

    def end(self):
        pass

    def call_next_question(self):
        try:
            self.active_question = Question.questions.pop()
        except:
            print('INDEX ERROR?????')
            raise

        self.trivia_pre_questionasked = False
        self.trivia_pre_questionasked_time = 0
        self.question_start_time = round(time.time())
        msg = "Внимание, ВОПРОС: \"{}\"".format(self.active_question.question)
        sendmessage(msg)
        print("Next question called #{}: | ANSWER: {}, {}".format(self.question_idx + 1, self.active_question.answer,
                                                                  self.active_question.answer_second))



class Question:
    questions: List[Question] = list()

    # todo change to enums or smthng else
    col_id = 0
    col_category = 1
    col_question = 2
    col_answer = 3
    col_answer_second = 4
    col_author = 5
    col_difficulty = 6

    def __init__(self, q_id, category, question, answer, author, difficulty, answer_second=None):
        self.id = q_id
        self.category = category
        self.question = question
        self.answer = answer
        self.answer_second = answer_second if answer_second else answer
        self.author = author
        self.difficulty = difficulty

    @staticmethod
    def build_questions(data_frame):
        Question.questions = []
        for row in data_frame.head:
            print(row)
            for i in range(0, row):
                Question.questions.append(Question.question_from_row(row))
        random.shuffle(Question.questions)

    @staticmethod
    def question_from_row(row) -> Question:
        return Question(row[Question.col_id], row[Question.col_category], row[Question.col_question], row[Question.col_answer],
                 row[Question.col_author], row[Question.col_difficulty], answer_second=row[Question.col_answer_second])


class Channel:
    HOST = None
    PORT = None
    NICK = None
    PASS = None
    CHAN = None
    RATE = 120  # messages per second
    CHAT_MSG = re.compile(r"^:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :")
    socket = None


class User:
    users: List[User] = list()

    def __init__(self, name, current_score=None, total_score=None, asked_count=None, answered_count=None, victories=None):
        self.name = name.lower()
        self.current_score = current_score if current_score else 0
        self.total_score = total_score if total_score else 0
        self.victories = victories if victories else 0
        self.asked_count = asked_count if asked_count else 0
        self.answered_count = answered_count if answered_count else 0

    def accept_answer(self, author: User) -> str:
        answer_points = Var.trivia_answervalue + difficulty_extra_user_points()
        creator_points = Var.trivia_creator_points_reward + difficulty_extra_creator_points()

        self.current_score += answer_points
        self.total_score += answer_points
        self.answered_count += 1
        author.current_score += creator_points
        author.total_score += creator_points
        author.asked_count += 1

        msg_creator = "Автор вопроса " + author.name + " получает " + str(creator_points) + " trivia points"
        msg = self.name + " правильно отвечает на вопрос #" + str(Var.session_questionno + 1) + "! Ответ \"" + str(
            Var.qs.iloc[Var.session_questionno, Var.column_position_answer]) + "\" оценивается в " + str(
            answer_points) + " trivia points. " + str(
            self.name) + " уже заработал(а) " + str(self.current_score) + " trivia points в сегодняшней игре."
        msg = msg + " " + msg_creator
        gs.answer(Var.qs.iloc[Var.session_questionno, Var.column_position_id], self.name)
        dumpscores()

        return msg

    def assign_winner(self):
        self.victories += 1
        for user in User.users:
            user.current_score = 0
        dumpscores()

    @staticmethod
    def userscore(username) -> str:
        usr = User.find_user(username)
        if usr:
            msg = "{} имеет {} trivia points в сегодняшней игре, {} за все время".format(usr.name, usr.current_score, usr.total_score)
        else:
            msg = "{} не найден в базе участников. Зарабатывайте trivia points правильно отвечая на вопросы других участников или задавайте " \
                  "свои вопросы!"
        return msg

    @staticmethod
    def top_current() -> List[User]:
        top = [user for user in User.users if user.current_score > 0]
        top.sort(key=lambda x: x.count)
        return top

    @staticmethod
    def user(name):
        usr = User.find_user(name)
        return usr if usr else User.add_user(name)

    @staticmethod
    def find_user(name):
        return next((user for user in User.users if user.name == name), None)

    @staticmethod
    def add_user(name):
        User.users.append(User(name))


def loadconfig():
    Var.trivia_hinttime_1 = int(os.environ['TRIVIA_HINTTIME_1'])
    Var.trivia_hinttime_2 = int(os.environ['TRIVIA_HINTTIME_2'])
    Var.trivia_skiptime = int(os.environ['TRIVIA_SKIPTIME'])
    Var.trivia_questiondelay = int(os.environ['TRIVIA_QUESTIONDELAY'])
    Var.trivia_pre_questionasked_delay = int(os.environ['TRIVIA_PRE_QUESTIONASKED_DELAY'])

    Var.trivia_answervalue = int(os.environ['TRIVIA_ANSWERVALUE'])
    Var.trivia_extra_points_per_avg_diff = int(os.environ['TRIVIA_EXTRA_POINTS_PER_AVG_DIFF'])
    Var.trivia_extra_points_per_hard_diff = int(os.environ['TRIVIA_EXTRA_POINTS_PER_HARD_DIFF'])
    Var.trivia_creator_points_reward = int(os.environ['TRIVIA_CREATOR_POINTS_REWARD'])
    Var.trivia_min_questions_count = int(os.environ['TRIVIA_MIN_QUESTION_COUNT'])

    Var.admins = os.environ['BOT_ADMINS'].strip().split(',')
    Channel.HOST = 'irc.twitch.tv'
    Channel.PORT = 6667
    Channel.NICK = os.environ['BOT_NICK']
    Channel.PASS = os.environ['BOT_PASS']
    Channel.CHAN = os.environ['BOT_CHANNEL']


def load_trivia_file(ext):
    data_frame = None
    if ext == 'csv':  # open trivia source based on type
        data_frame = pd.read_csv('triviaset' + '.' + ext)
    elif ext == 'xlsx':
        data_frame = pd.read_excel('triviaset' + '.' + ext)

    Trivia.active_trivia = Trivia(data_frame)


async def trivia_start():
    authors = gs.build_trivia()
    load_trivia_file('csv')

    if Var.trivia_questions < Var.trivia_min_questions_count:
        sendmessage("Недостаточно вопросов для старта викторины, минимум: {}, доступно: {}".format(Var.trivia_min_questions_count,
                                                                                                   Var.trivia_questions))
    else:
        sendmessage("Викторина запущена. Составление базы вопросов для сегодняшней игры...")
        build()
        print("Quizset built.")
        Var.trivia_active = True
        msg = "Викторина готова! Количество вопросов: " + str(Var.trivia_questions) + ", авторы: " + ", ".join(
            authors.keys()) + ". Начало викторины через " + str(Var.trivia_questiondelay) + " секунд."
        sendmessage(msg)
        await asyncio.sleep(Var.trivia_questiondelay)
        trivia_call_prequestion()


def loadscores():
    # Load score list
    try:
        with open('userscores.txt', 'r') as fp:
            User.users = jsonpickle.decode(json.load(fp))
            print("Users loaded ({})".format(len(User.users)))
    except (FileNotFoundError, IOError, json.decoder.JSONDecodeError):
        with open('userscores.txt', 'w') as fp:
            json.dump(jsonpickle.encode([User('enikkk')]), fp)


def dumpscores():
    with open('userscores.txt', 'w') as fp:
        json.dump(jsonpickle.encode(User.users), fp)
    gs.save_scores()


### Trivia command switcher
async def trivia_commandswitch(cleanmessage, username, message):
    print("Command recognized: {} by {}".format(cleanmessage, username))

    # ADMIN ONLY COMMANDS
    if username in Var.admins:
        if cleanmessage == "!triviastart" and not Var.trivia_active:
            await trivia_start()
        if cleanmessage == "!triviaend" and Var.trivia_active:
            await trivia_end()
        if cleanmessage == "!skip":
            await trivia_skipquestion()

    # ACTIVE TRIVIA COMMANDS
    if Var.trivia_active:
        if cleanmessage == "!top3":
            trivia_top3score()

        if cleanmessage == "!hint":
            if Var.trivia_hintasked == 0:
                trivia_askhint(0)
            if Var.trivia_hintasked == 1:
                trivia_askhint(0)
            if Var.trivia_hintasked == 2:
                trivia_askhint(1)

    # GLOBAL COMMANDS
    if cleanmessage == "!score":
        sendmessage(User.userscore(username))

    elif cleanmessage == "!trivia":
        sendmessage("Присоединяйтесь к нашей викторине: {}".format(Var.guide))

    # elif cleanmessage == "!ask":
    #     ask_user_question(username, message)

    elif cleanmessage == "!respond":
        sendmessage("max ThunBeast geroy ThunBeast")

    await asyncio.sleep(1)


def difficulty_extra_user_points():
    difficulty = Var.qs.iloc[Var.session_questionno, Var.column_position_difficulty]
    if difficulty == 0:
        extra_points = -3
    elif difficulty == 2:
        extra_points = 3
    else:
        extra_points = 0
    return extra_points


def difficulty_extra_creator_points():
    difficulty = Var.qs.iloc[Var.session_questionno, Var.column_position_difficulty]
    return 3 if difficulty == 2 else 2


def reset_question_timings():
    Var.trivia_hintasked = 0
    Var.trivia_questionasked = False
    Var.trivia_questionasked_time = 0


def reset_prequestion_timings():
    Var.trivia_pre_questionasked = False
    Var.trivia_pre_questionasked_time = 0


### Call trivia question
def trivia_call_prequestion():
    Var.trivia_pre_questionasked = True
    Var.trivia_pre_questionasked_time = round(time.time())

    premsg = "Вопрос #" + str(
        Var.session_questionno + 1) + " в категории [" + str(
        Var.qs.iloc[Var.session_questionno, Var.column_position_category]) + "], сложность [" + \
             Var.qs.iloc[Var.session_questionno, Var.column_position_difficulty] + "], от пользователя [" + Var.qs.iloc[
                 Var.session_questionno, Var.column_position_creator] + "] ..."
    sendmessage(premsg)


def trivia_callquestion():
    reset_prequestion_timings()
    Var.trivia_questionasked = True
    Var.trivia_questionasked_time = round(time.time())

    msg = "Внимание, ВОПРОС: \"" + Var.qs.iloc[Var.session_questionno, Var.column_position_question] + "\""
    sendmessage(msg)
    print("Next question called #" + str(Var.session_questionno + 1) + ": | ANSWER: \"" + Var.qs.iloc[
        Var.session_questionno, Var.column_position_answer] + "\" or \"" + Var.qs.iloc[
              Var.session_questionno, Var.column_position_answer] + "\"")


async def trivia_answer(username, cleanmessage):
    print("Answer recognized: {} by {}".format(cleanmessage, username))
    # TODO IF USER QUESTION
    Var.trivia_questionasked = False

    msg = User.user(username).accept_answer(User(Var.qs.iloc[Var.session_questionno, Var.column_position_creator]))
    sendmessage(msg)

    await asyncio.sleep(2)
    Var.session_questionno += 1
    reset_question_timings()
    reset_prequestion_timings()
    if Var.trivia_questions == Var.session_questionno:  # End game check
        await trivia_end()
    else:
        await asyncio.sleep(Var.trivia_questiondelay)
        trivia_call_prequestion()


### Finishes trivia by getting top 3 list, then adjusting final message based on how many participants. Then dumpscore()
async def trivia_end():
    top = User.top_current()
    msg = "Нет завершенных вопросов. Результаты пусты."

    if len(top) > 0:
        msg = "***{}*** победитель сегодняшней викторины с {} trivia points!".format(top[0].name, top[0].current_score)
    if len(top) > 1:
        msg += ", **{}** на 2-ом месте с {} trivia points".format(top[1].name, top[1].current_score)
    if len(top) > 2:
        msg += ", *{}* занимает почетное 3-е с {} trivia points".format(top[2].name, top[2].current_score)

    sendmessage(msg)
    top[0].assign_winner()
    await asyncio.sleep(3)
    sendmessage("Благодарим за участие! Увидимся на последующих викторинах!")

    Var.session_questionno = 0  # reset variables for trivia
    Var.trivia_active = False
    reset_question_timings()
    reset_prequestion_timings()
    Var.qs = pd.DataFrame(columns=list(Var.ts))


async def trivia_routinechecks():  # after every time loop, routine checking of various vars/procs
    Var.TIMER = round(time.time())

    if Var.trivia_questions == Var.session_questionno:  # End game check
        await trivia_end()

    if ((
            Var.TIMER - Var.trivia_questionasked_time) > Var.trivia_hinttime_2 and Var.trivia_active and Var.trivia_hintasked
            == 1 and Var.trivia_questionasked):
        Var.trivia_hintasked = 2
        trivia_askhint(1)  # Ask second hint

    if ((
            Var.TIMER - Var.trivia_questionasked_time) > Var.trivia_hinttime_1 and Var.trivia_active and Var.trivia_hintasked
            == 0 and Var.trivia_questionasked):
        Var.trivia_hintasked = 1
        trivia_askhint(0)  # Ask first hint

    if ((Var.TIMER - Var.trivia_questionasked_time) > Var.trivia_skiptime and Var.trivia_active and Var.trivia_questionasked):
        await trivia_skipquestion()  # Skip question after time is up

    if ((
            Var.TIMER - Var.trivia_pre_questionasked_time) > Var.trivia_pre_questionasked_delay and Var.trivia_active and
            Var.trivia_pre_questionasked
            and not Var.trivia_questionasked):
        trivia_callquestion()  # Ask question after prequestion delay


def trivia_askhint(hinttype=0):  # hinttype: 0 = 1st hint, 1 = 2nd hint
    if (hinttype == 0 and Var.trivia_questionasked == True):
        prehint = str(Var.qs.iloc[Var.session_questionno, Var.column_position_answer])
        hint = ''

        for word in prehint.split(" "):
            for letter in word:
                word = word.replace(letter, " _ ")
            hint = "{} {}".format(hint, word)
        sendmessage("Подсказка #1:" + hint)

    elif (hinttype == 1 and Var.trivia_questionasked == True):  # type 0, replace 2 out of 3 chars with _
        prehint = str(Var.qs.iloc[Var.session_questionno, Var.column_position_answer])
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
        sendmessage("Подсказка #2: " + hint)


async def trivia_skipquestion():
    if Var.trivia_active:
        Var.session_questionno += 1
        reset_question_timings()
        reset_prequestion_timings()

        sendmessage("Время на ответ истекло или вопрос был пропущен. Правильный ответ: \"" + str(
            Var.qs.iloc[Var.session_questionno - 1, Var.column_position_answer]) + "\". Переход к следующему вопросу")

        gs.answer(Var.qs.iloc[Var.session_questionno - 1, Var.column_position_id], "skip/timeout")

        await asyncio.sleep(2)
        if Var.trivia_questions == Var.session_questionno:  # End game check
            await trivia_end()
        else:
            await asyncio.sleep(Var.trivia_questiondelay)
            trivia_call_prequestion()


def ask_user_question(username, message):
    if Var.trivia_active:
        sendmessage("Дождитесь окончания викторины, чтобы задать свой вопрос")
    else:
        q = gs.get_question(message)
        if not q or q[Var.column_position_creator] != username:
            sendmessage("Вопрос не найден или вы не являетесь его автором")
        else:
            # todo ask question
            sendmessage("в разработке 4Head")


### Top 3 trivia
def trivia_top3score():
    top = User.top_current()
    msg = "Нет рекордов"
    if len(top) > 0:
        msg = "1-ое место: {} {} очков".format(top[0].name, top[0].current_score)
    if len(top) > 1:
        msg += ", 2-ое место: {} {} очков".format(top[1].name, top[1].current_score)
    if len(top) > 2:
        msg += ", 3-е место: {} {} очков".format(top[2].name, top[2].current_score)

    sendmessage(msg)


### Chat message sender func
def sendmessage(msg):
    answermsg = ":" + Channel.NICK + "!" + Channel.NICK + "@" + Channel.NICK + ".tmi.twitch.tv PRIVMSG " + Channel.CHAN + " : " + msg + "\r\n"
    answermsg2 = answermsg.encode("utf-8")
    Channel.socket.send(answermsg2)


############### CHAT & BOT CONNECT ###############
async def scanloop():
    response = get_response()
    if response == "PING :tmi.twitch.tv\r\n":
        pong()
    elif response:
        await check_response(response)


def get_response() -> str:
    response = None
    try:
        response = Channel.socket.recv(1024).decode("utf-8")
    except socket.error as e:
        # Ignore "[Errno 35] Resource temporarily unavailable" exception
        import errno
        if e.errno == errno.EAGAIN: pass
        else: raise
    except UnicodeDecodeError:
        pass
    return response


def pong():
    Channel.socket.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))


async def check_response(response):
    username = re.search(r"\w+", response).group(0).lower()
    # Ignore this bot's messages
    if username == Channel.NICK.lower():
        return

    message = Channel.CHAT_MSG.sub("", response)
    cleanmessage = re.sub(r"\s+", "", message, flags=re.UNICODE)

    if cleanmessage in Var.COMMANDLIST:
        await trivia_commandswitch(cleanmessage, username, message)
    elif answer_recognized(message, username):
        await trivia_answer(username, cleanmessage)


def answer_recognized(message, username) -> bool:
    if Var.trivia_active:
        return (bool(
            re.match("\\b" + str(Var.qs.iloc[Var.session_questionno, Var.column_position_answer]) + "\\b", message,
                     re.IGNORECASE)) or bool(
            re.match("\\b" + str(Var.qs.iloc[Var.session_questionno, Var.column_position_answer_second]) + "\\b", message,
                     re.IGNORECASE))) and (
                       username != Var.qs.iloc[Var.session_questionno, Var.column_position_creator])
    elif Var.user_question:
        return bool(re.match("\\b" + str(Var.user_question[Var.column_position_answer]) + "\\b", message, re.IGNORECASE)) or bool(
            re.match("\\b" + str(Var.user_question[Var.column_position_answer_second]) + "\\b", message, re.IGNORECASE))
    else:
        return False


## STARTING PROCEDURES
def load_files():
    print("Loading config and scores...")
    loadconfig()
    loadscores()


async def connect_socket():
    if Var.SWITCH:
        s = socket.socket()
        s.connect((Channel.HOST, Channel.PORT))
        s.send("PASS {}\r\n".format(Channel.PASS).encode("utf-8"))
        s.send("NICK {}\r\n".format(Channel.NICK).encode("utf-8"))
        s.send("JOIN {}\r\n".format(Channel.CHAN).encode("utf-8"))
        s.setblocking(False)
        Channel.socket = s
        await asyncio.sleep(1)
        sendmessage(Var.infomessage)


# Infinite loop while bot is active to scan messages & perform routines
async def trivia_loop():
    print(Var.SWITCH)
    while Var.SWITCH:
        if Var.trivia_active:
            await trivia_routinechecks()
        await scanloop()
        await asyncio.sleep(1 / Channel.RATE)


async def start_coro():
    load_trivia_file('csv')
    load_files()
    await connect_socket()
    await trivia_loop()
