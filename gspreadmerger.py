import gspread
import json
import uuid
import time
import asyncio
from oauth2client.service_account import ServiceAccountCredentials
import csv
import boto3
from botocore.exceptions import ClientError
from collections import deque
import os


class S3FileManager:
    client = None
    bucket = 'cloud-cube-eu'
    key = 'b34hz576f9il/public/'

    users_file = 'userscores.txt'
    categories_file = 'categories.txt'
    merge_requests_file = 'mergerequests.txt'

    @staticmethod
    def load():
        S3FileManager.setup_client()
        S3FileManager.download()

    @staticmethod
    def setup_client():
        S3FileManager.client = boto3.client(
            's3',
            aws_access_key_id=os.environ['CLOUDCUBE_ACCESS_KEY_ID'],
            aws_secret_access_key=os.environ['CLOUDCUBE_SECRET_ACCESS_KEY'],
            region_name='eu-west-1')

    @staticmethod
    def download():
        S3FileManager.download_users()
        S3FileManager.download_categories()
        S3FileManager.download_requests()

    @staticmethod
    def upload():
        S3FileManager.upload_users()
        S3FileManager.upload_categories()
        S3FileManager.upload_requests()

    @staticmethod
    def download_file(file_name):
        print("S3 download: {}".format(file_name))
        S3FileManager.client.download_file(S3FileManager.bucket,
                                           S3FileManager.key + file_name,
                                           file_name)
    @staticmethod
    def upload_file(file_name):
        print("S3 upload: {}".format(file_name))
        S3FileManager.client.upload_file(file_name, S3FileManager.bucket,
                                         S3FileManager.key + file_name)

    @staticmethod
    def download_users():
        S3FileManager.download_file(S3FileManager.users_file)

    @staticmethod
    def download_categories():
        S3FileManager.download_file(S3FileManager.categories_file)

    @staticmethod
    def download_requests():
        S3FileManager.download_file(S3FileManager.merge_requests_file)

    @staticmethod
    def upload_users():
        S3FileManager.upload_file(S3FileManager.users_file)

    @staticmethod
    def upload_categories():
        S3FileManager.upload_file(S3FileManager.categories_file)

    @staticmethod
    def upload_requests():
        S3FileManager.upload_file(S3FileManager.merge_requests_file)


class Gspread:
    categories = {}
    mergeRequests = []

    newCategories = []
    mergedQuestionCount = 0
    isMerging = False
    isResourceExhausted = False
    resourceExhaustionProtectedId = ''
    gc = None

    # Google sheets
    colNames = ['id', 'category', 'question', 'answer', 'answer2', 'author', 'difficulty', 'dateMerged', 'dateAnswered',
                'usersAnswered']
    colId, colCategory, colQuestion, colAnswer, colAnswer2, colAuthor, colDifficulty, colDateMerged, colDateAnswered, colUsersAnswered = colNames
    userColNames = [colId, colCategory, colQuestion, colAnswer, colAnswer2, colAuthor, colDifficulty]
    requiredFieldsIndex = [colNames.index(colQuestion) + 1, colNames.index(colAnswer) + 1, colNames.index(colAuthor) + 1]
    difficulties = ['0', '1', '2']
    easyDiff, avgDiff, hardDiff = difficulties
    defaultCategoryCode = '0001'

    # Config
    apiMail = ''
    adminsMail = []
    baseSheetUrl = ''
    mainDataBaseSheetId = ''
    categoriesSheetId = ''


def answer(question_id, user_name):
    sheet = Gspread.gc.open_by_key(Gspread.mainDataBaseSheetId).sheet1
    question_cell = sheet.find(question_id)
    question = sheet.row_values(question_cell.row)

    try:
        users_answered = ",{}".format(question[col_index(Gspread.colUsersAnswered)], user_name)
    except IndexError:
        users_answered = user_name

    sheet.update_cell(question_cell.row, col_index(Gspread.colDateAnswered) + 1, round(time.time()))
    sheet.update_cell(question_cell.row, col_index(Gspread.colUsersAnswered) + 1, users_answered)


def save_scores():
    S3FileManager.upload_users()


def catgory_repr(code):
    return "{} / {}".format(Gspread.categories[code]['folder'].capitalize(), Gspread.categories[code]['name'].capitalize())

def diff_repr(code: str):
    difficulty = "Средняя"
    if code == Gspread.easyDiff:
        difficulty = "Легкая"
    elif code == Gspread.hardDiff:
        difficulty = "Тяжелая"
    return difficulty


def build_trivia() -> dict:
    print("Building trivia")
    main_sheet = Gspread.gc.open_by_key(Gspread.mainDataBaseSheetId).sheet1
    allRows = main_sheet.get_all_values()

    unanswered = [row for row in allRows if not len(row[col_index(Gspread.colDateAnswered)])]

    authors = {}
    for question in unanswered:
        author_name = question[col_index(Gspread.colAuthor)]
        if author_name in authors.keys():
            authors[author_name].append(question)
        else:
            authors[author_name] = [question]

    q_max = 0
    if len(authors.keys()) > 2:
        q_max = 24
    elif len(authors.keys()) == 2:
        q_max = 18
    elif len(authors.keys()) == 1:
        q_max = 12

    q_max = len(unanswered) if len(unanswered) < q_max else q_max
    print(q_max)

    trivia = [allRows[0]]
    d = deque(authors.keys())
    print(d)
    for i in range(0, q_max):
        q = authors[d[0]].pop()
        q[col_index(Gspread.colCategory)] = catgory_repr(q[col_index(Gspread.colCategory)])
        q[col_index(Gspread.colDifficulty)] = diff_repr(q[col_index(Gspread.colDifficulty)])

        trivia.append(q)
        if not len(authors[d[0]]):
            d.remove(d[0])
        d.rotate(-1)


    with open('triviaset.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(trivia)

    return authors

async def merge_list(ctx):
    msg = ""
    if len(Gspread.mergeRequests) > 0:
        for merge in Gspread.mergeRequests:
            msg += (Gspread.baseSheetUrl + merge) + "\n"
        msg += "Всего в списке реквестов, ожидающих добавления: **" + str(len(Gspread.mergeRequests)) + "**"
    else:
        msg = "Список на добавление пуст"
    await ctx.send(msg)


async def resource_exhausted(ctx, sheet_id):
    Gspread.isResourceExhausted = True
    print('Resource exhausted')
    msg = "```diff\n- [" + sheet_id + "] - Привышен лимит доступных запросов к sheets.googleapis.com, бот продолжит работу " \
          "автоматически сразу после восставновления сервиса, ожидайте\n... \n```"
    await ctx.send(msg)
    await asyncio.sleep(30)
    Gspread.isResourceExhausted = False


async def merge_com(ctx, sheet_id):
    if sheet_id.lower() == 'all' and len(Gspread.mergeRequests) == 0:
        msg = "Список на добавление пуст"
        await ctx.send(msg)
        return

    # Merge
    for merge_id in (Gspread.mergeRequests.copy() if sheet_id.lower() == 'all' else [sheet_id]):
        errorsFound = await check_for_errors(ctx, merge_id)
        if not errorsFound:
            await merge(ctx, merge_id)


async def merge(ctx, sheet_id):
    Gspread.isMerging = True
    print("Is merging = " + str(Gspread.isMerging) + " - " + sheet_id)
    msg = "```ini\n> [" + sheet_id + "] - Начало процесса добавления таблицы. Пожалуйста, дождитесь окончания, " \
                                     "прежде чем давать новые команды\n...\n``` "
    await ctx.send(msg)

    try:
        sheet = Gspread.gc.open_by_key(sheet_id).sheet1
        main_sheet = Gspread.gc.open_by_key(Gspread.mainDataBaseSheetId).sheet1

        allRows = sheet.get_all_values()[1:]
        for rowIdx, row in enumerate(allRows):
            # Skip questions with non empty id field, except resource exhaustion protected id
            if len(row[col_index(Gspread.colId)]) != 0 and row[col_index(Gspread.colId)] != Gspread.resourceExhaustionProtectedId:
                continue

            # Filled row with all values
            newRow = merged_row_from(row)

            # Assign and update id in user sheet
            sheet.update_cell(rowIdx + 2, col_index(Gspread.colId) + 1, newRow[col_index(Gspread.colId)])

            # Protects question from being skipped in the next merge if resource gets exhausted on append_row()
            Gspread.resourceExhaustionProtectedId = newRow[col_index(Gspread.colId)]
            main_sheet.append_row(newRow, value_input_option='RAW')
            Gspread.resourceExhaustionProtectedId = ''
            Gspread.mergedQuestionCount += 1

        # Done
        await complete_merge(ctx, sheet_id)

    except gspread.exceptions.APIError as e:
        # Recursion until service is available again
        if json.loads(e.args[0])['error']['code'] == 429:
            await resource_exhausted(ctx, sheet_id)
            await merge(ctx, sheet_id)
        else:
            raise

    finally:
        Gspread.isMerging = False
        print("Is merging = " + str(Gspread.isMerging))

async def merge_req(ctx, sheet_id):
    if sheet_id in Gspread.mergeRequests:
        msg = "Таблица с этим ID уже есть в списке"
        return msg

    # Check for errors
    errorsFound = await check_for_errors(ctx, sheet_id)
    if errorsFound: return

    # Give admins permissions
    for admin in Gspread.adminsMail:
        Gspread.gc.insert_permission(sheet_id, admin, perm_type='user', role='writer', notify=False)

    # Saving merge request
    Gspread.mergeRequests.append(sheet_id)
    save_merge_requests()

    # Ready to merge
    msg = Gspread.baseSheetUrl + sheet_id + " таблица прошла проверку и готова к добавлению. Всего реквестов, ожидающих " \
                                            "добавления: " + "**" + str(len(Gspread.mergeRequests)) + "** "
    return msg

def remove_merge_request(sheetId):
    if sheetId in Gspread.mergeRequests:
        Gspread.mergeRequests.remove(sheetId)
        save_merge_requests()


def col_index(colName):
    if colName in Gspread.colNames:
        return Gspread.colNames.index(colName)


def merged_row_from(row):
    newRow = [None] * len(Gspread.colNames)
    for i, col in enumerate(newRow):
        # id
        if i == Gspread.colNames.index(Gspread.colId):
            newRow[i] = uuid.uuid4().hex

        # category
        elif i == Gspread.colNames.index(Gspread.colCategory):
            if len(row[i]) != 4:
                newRow[i] = Gspread.defaultCategoryCode
            elif row[i] not in Gspread.categories.keys():
                add_new_category(row[i])
                newRow[i] = row[i]
            else:
                newRow[i] = row[i]

        # difficulty
        elif i == Gspread.colNames.index(Gspread.colDifficulty) and row[i] not in Gspread.difficulties:
            newRow[i] = Gspread.avgDiff

        # dateMerge
        elif i == Gspread.colNames.index(Gspread.colDateMerged):
            newRow[i] = round(time.time())

        # other values
        elif i < len(Gspread.userColNames):
            newRow[i] = row[i]

    return newRow


async def complete_merge(ctx, sheetId):
    newCategoryStr = ", новые категории: " + ', '.join(Gspread.newCategories) if len(Gspread.newCategories) else ''
    msg = "```diff\n+ [" + sheetId + "] - Успешно добавлена! Новых вопросов: " + str(Gspread.mergedQuestionCount) + newCategoryStr + "\n```"
    Gspread.newCategories = []
    Gspread.mergedQuestionCount = 0
    remove_merge_request(sheetId)
    await ctx.send(msg)


# Returns True if any error found
async def check_for_errors(ctx, sheet_id):
    errStart = "```autohotkey\n% [" + sheet_id + "] - Проверка не пройдена, причина: "
    errEnd = "\n```"
    err = generate_error_message(sheet_id)
    if err:
        await ctx.send(errStart + err.lower() + errEnd)
        return True
    return False


def generate_error_message(sheetId):
    try:
        sheet = Gspread.gc.open_by_key(sheetId).sheet1
        permList = Gspread.gc.list_permissions(sheetId)

        # Check for public permissions before other
        for perm in permList:
            if perm.get('type') == 'anyone':
                return "Таблица доступна для просмотра ВСЕМ. Пожалуйста, удалите предыдущее сообщение и поменяйтся " \
                      "права доступа "

        # No writer permission for api
        apiPerm = ''
        apiNameFound = False
        for perm in permList:
            if perm.get('name') == Gspread.apiMail:
                apiNameFound = True
                apiPerm = perm.get('role')
        if not apiNameFound or (apiNameFound and apiPerm != 'writer'):
            return "У бота есть права на просмотр таблицы, но нет прав на редактирование"

        # Wrong column count
        if sheet.col_count != len(Gspread.userColNames):
            return "Неправильное количество столбцов"

        # Wrong column name or order
        for i, col in enumerate(sheet.row_values(1)):
            print("{} - {}".format(col, Gspread.userColNames[i]))
            if col != Gspread.userColNames[i]:
                return "Неправильное имя или порядок столбцов"

        # No questions
        if sheet.row_count < 2:
            return "Нет вопросов"

        # Check required fields
        for reqIdx in Gspread.requiredFieldsIndex:
            reqVals = sheet.col_values(reqIdx)[1:]
            if len(reqVals) + 1 < sheet.row_count:
                return "Имеются пустые строки"
            if '' in reqVals:
                return "Не заполнены обязательные поля"

    # Api exceptions
    except gspread.exceptions.APIError as e:
        argsJson = json.loads(e.args[0])
        if argsJson['error']['code'] == 404 or argsJson['error']['code'] == 403:
            return "Таблица с указанным ID не существует, либо неправильно выставлены права доступа боту"
        elif argsJson['error']['code'] == 429:
            return "Привышен лимит доступных запросов к сервису sheets.googleapis.com, подождите пару минут и " \
                  "повторите команду "
        else:
            raise
    else:
        return None


def load():
    Gspread.apiMail = os.environ['GSPREAD_API_MAIL']
    Gspread.adminsMail = os.environ['GSPREAD_ADMIN_MAILS'].strip().split(',')
    Gspread.mainDataBaseSheetId = os.environ['GSPREAD_MAIN_DB_SHEET_ID']
    Gspread.categoriesSheetId = os.environ['GSPREAD_CATEGORIES_SHEET_ID']

    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
    Gspread.gc = gspread.authorize(creds)

    S3FileManager.load()
    load_merge_requests()
    load_categories_list()

# Save & Load files
def load_merge_requests():
    try:
        print('load_merge_requests')
        with open('mergerequests.txt', 'r') as fileHandler:
            Gspread.mergeRequests = json.load(fileHandler)
    except (FileNotFoundError, IOError):
        with open('mergerequests.txt', 'w'):
            pass


def save_merge_requests():
    with open('mergerequests.txt', 'w') as fileHandler:
        print('Saving: {}'.format(Gspread.mergeRequests))
        json.dump(Gspread.mergeRequests, fileHandler)
    S3FileManager.upload_requests()


def load_categories_list():
    with open('categories.txt', 'r') as filehandler:
        Gspread.categories = json.load(filehandler)

    if not len(Gspread.categories):
        print("Categories not found, loading from gspread")
        sheet = Gspread.gc.open_by_key(Gspread.categoriesSheetId).sheet1
        allRows = sheet.get_all_values()[1:]

        Gspread.categories = {}
        for row in allRows:
            if len(row[2]):
                Gspread.categories[row[2]] = {"folder": row[0], "name": row[1], "code": row[2]}
        print(Gspread.categories)
        save_categories_list()


def save_categories_list():
    with open('categories.txt', 'w') as filehandler:
        json.dump(Gspread.categories, filehandler)
    S3FileManager.upload_categories()


def add_new_category(category_code):
    try:
        sheet = Gspread.gc.open_by_key(Gspread.categoriesSheetId).sheet1
        row = sheet.row_values(sheet.find(category_code).row)
        Gspread.categories[row[2]] = {"folder": row[0], "name": row[1], "code": row[2]}
    except gspread.exceptions.CellNotFound:
        Gspread.categories[category_code] = {"folder": "Не указана", "name": "Общая", "code": category_code}
    finally:
        Gspread.newCategories.append(category_code)
        save_categories_list()
        # TODO: proccess exception properly
