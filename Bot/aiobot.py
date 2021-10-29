from config import *
from db import *
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters.builtin import Text


db = DB(DB_HOST, DB_USER, DB_PASS, DB_NAME)
bot = Bot(token=API_KEY)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)


def get_keyboard(ktype=1, data='num_'):
	if ktype == 1:
		buttons = [
			types.InlineKeyboardButton(text=SHORT_ANS[0], callback_data=data + "1"),
			types.InlineKeyboardButton(text=SHORT_ANS[1], callback_data=data + "2"),
			types.InlineKeyboardButton(text=SHORT_ANS[2], callback_data=data + "3"),
			types.InlineKeyboardButton(text=SHORT_ANS[3], callback_data=data + "4"),
		]
	elif ktype == 2:
		buttons = [
			types.InlineKeyboardButton(text=LONG_ANS[0], callback_data=data + "1"),
			types.InlineKeyboardButton(text=LONG_ANS[1], callback_data=data + "2"),
		]
	keyboard = types.InlineKeyboardMarkup(row_width=ktype)
	keyboard.add(*buttons)
	return keyboard


def get_department_keyboard(name: str, deps: list):
	buttons = []
	for i in deps:
		var = name + "_" + str(i[0])
		btn = types.InlineKeyboardButton(text=i[1], callback_data=var)
		buttons.append(btn)
	keyboard = types.InlineKeyboardMarkup(row_width=1)
	keyboard.add(*buttons)
	return keyboard


def translate(message):
	if type(message) == types.CallbackQuery:
		uid = message.message.chat.id
		message = message.message
	else:
		uid = message.chat.id
	return message, uid


async def free_deps(message):
	message, uid = translate(message)
	get_free_deps = db.get_free_deps(uid)
	mark = get_department_keyboard('ans', get_free_deps)
	await message.answer(CH_DEP_MSG, reply_markup=mark)


async def quest_type(message, cont=True):
	message, uid = translate(message)
	pid, text = db.boost_step(uid) if cont else db.get_question(uid)
	if not pid:
		await free_deps(message)
		return
	ktype = 1 if text[2] == b'True' else 2
	keyboard = get_keyboard(ktype)
	await message.answer(text[1], reply_markup=keyboard)


@dp.message_handler(commands="help")
async def cmd_help(message: types.Message):
	await message.answer(HELP_MSG, parse_mode='Markdown', disable_web_page_preview=True)


@dp.message_handler(commands="start")
async def cmd_start(message: types.Message):
	uid = message.from_user.id
	uname = message.from_user.username
	if db.set_new_user(uid, uname):
		await message.answer(START_MSG)
	else:
		await quest_type(message, cont=False)


@dp.message_handler(commands="setadmin")
async def cmd_set_admin(message: types.Message):
	message, uid = translate(message)
	if not db.is_admin(uid): return
	li = message.text.split()
	if len(li) != 2: return
	if db.set_admin(li[1]):
		await message.answer(f'Пользователь {li[1]} стал администратором!')


@dp.message_handler(commands="deladmin")
async def cmd_del_admin(message: types.Message):
	message, uid = translate(message)
	if not db.is_admin(uid): return
	li = message.text.split()
	if len(li) != 2: return
	if db.del_admin(li[1]):
		await message.answer(f'Администратор {li[1]} был удалён!')


@dp.message_handler(commands="getlist")
async def cmd_get_list(message: types.Message):
	message, uid = translate(message)
	if not db.is_admin(uid): return
	line = '\n'.join([f'{i})   @{j[0]}' for i, j in enumerate(db.get_admins())])
	await message.answer('Администраторы бота:\n\n' + line)


@dp.message_handler(commands="statistic")
async def cmd_statistic(message: types.Message):
	message, uid = translate(message)
	if not db.is_admin(uid): return
	await message.answer(PAUSE_MSG)
	wb1 = statistic(EXCEL_STAT, db.get_statistic())
	await message.answer_document(wb1)
	wb2 = statistic(EXCEL_TEXT, db.get_text_answers())
	await message.answer_document(wb2)


@dp.callback_query_handler(Text(startswith="dep_"))
async def callbacks_quest_dep(call: types.CallbackQuery):
	data = call.data.split("_")[1]
	message, uid = translate(call)
	db.set_depid(uid, data)
	dep_name = db.get_deps()[int(data) - 1][1]
	await message.edit_text(f"{DEP_MSG}\n{dep_name}")
	await free_deps(call)


@dp.callback_query_handler(Text(startswith="ans_"))
async def callbacks_quest_ans(call: types.CallbackQuery):
	data = int(call.data.split("_")[1])
	message, uid = translate(call)
	dep_name = db.get_deps()[data - 1][1]
	db.set_to_pid(uid, data)
	db.rmv_free_dep(uid, data)
	await message.edit_text(f"{CH_DEP_MSG}\n{dep_name}")
	await quest_type(call)


@dp.callback_query_handler(Text(startswith="num_"))
async def callbacks_quest_num(call: types.CallbackQuery):
	data = call.data.split("_")[1]
	message, uid = translate(call)
	dep, text = db.get_question(uid)
	if text[2] == b'False':
		if data == '1':
			await message.answer(RECOMS_MSG)
		elif data == '2':
			await quest_type(message)
		return
	if data == "1":
		var = '+2'
		ans = SHORT_ANS[0]
	elif data == "2":
		var = '+1'
		ans = SHORT_ANS[1]
	elif data == "3":
		var = '+0'
		ans = SHORT_ANS[2]
	elif data == "4":
		var = '-1'
		ans = SHORT_ANS[3]
	db.set_answer(uid, var)
	await message.edit_text(f"{text[1]}\n{ans}")
	await quest_type(message)


@dp.message_handler(content_types=[types.ContentType.TEXT])
async def cmd_text_answer(message: types.Message):
	message, uid = translate(message)
	ans = db.check_promo(uid, message.text)
	if ans == -1:
		await message.answer(PROMO_ERR_MSG)
		await message.answer(START_MSG)
	elif ans == 1:
		get_deps = db.get_deps()
		mark = get_department_keyboard('dep', get_deps)
		await message.answer(DEP_MSG, reply_markup=mark)
	elif ans == 0:
		pid, quest = db.get_question(uid)
		if not quest or quest[2] == b'False':
			try:
				db.set_answer(uid, message.text, ans_vars=False)
			except:
				pass
			await quest_type(message)
		else:
			await message.answer('Не понимаю(')


if __name__ == "__main__":
	executor.start_polling(dp, skip_updates=True)
