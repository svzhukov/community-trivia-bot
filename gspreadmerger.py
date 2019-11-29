import gspread
import json
import uuid
import time
import asyncio
from oauth2client.service_account import ServiceAccountCredentials
import csv


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
    apiMail = 'twitch-community-trivia-bot@twitch-community-trivia-bot.iam.gserviceaccount.com'
    adminsMail = ['en1k89055807894@gmail.com', 'allrape1@gmail.com']
    baseSheetUrl = 'https://docs.google.com/spreadsheets/d/'
    mainDataBaseSheetId = '105HTMseRZ4YaND_TfPYG--g9DazB0wPrIlbMRzALXVA'
    categoriesSheetId = '1ysb4LL6IASqSeX1xLAee0hscHykP1peHAM3Ofrnnd1k'


def build_trivia():
    main_sheet = Gspread.gc.open_by_key(Gspread.mainDataBaseSheetId).sheet1

    allRows = main_sheet.get_all_values()[1:]
    print(allRows)
    print('Building building...')

    unanswered = [row for row in allRows if not len(row[col_index(Gspread.colDateAnswered)])]
    print('\n')
    print('\n')
    print('\n')
    print(unanswered)
    # for rowIdx, row in enumerate(allRows):
    #     if len(row[col_index(Gspread.colDateAnswered)]) == 0:
    #         pass

    with open('triviaset.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(unanswered)


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
            elif row[i] not in Gspread.categories:
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
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
    Gspread.gc = gspread.authorize(creds)
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


def load_categories_list():
    try:
        with open('categories.txt', 'r') as filehandler:
            Gspread.categories = json.load(filehandler)
    except (FileNotFoundError, IOError, json.decoder.JSONDecodeError):
        with open('categories.txt', 'w'):
            pass


def save_categories_list():
    with open('categories.txt', 'w') as filehandler:
        json.dump(Gspread.categories, filehandler)


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
