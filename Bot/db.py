import pymysql
from openpyxl import Workbook


class DB:
	def __init__(self, host, user, pswrd, name):
		self.db = pymysql.connect(host=host, user=user, password=pswrd, database=name)

	def get_user(self, uid):
		cursor = self.db.cursor()
		cursor.execute('SELECT * FROM user WHERE tid = %s;', uid)
		ans = cursor.fetchone()
		return ans

	def set_new_user(self, uid, uname):
		cursor = self.db.cursor()
		try:
			cursor.execute('INSERT INTO user VALUES(%s, %s, %s, %s, %s, %s, %s);', (None, uid, uname, None, None, None, None))
			self.db.commit()
			cursor.execute('SELECT id FROM user WHERE tid = %s;', (uid,))
			user_id = cursor.fetchone()[0]
			ans = self.get_user(uid)
		except:
			ans = None
		return ans

	def check_promo(self, uid, promo):
		cursor = self.db.cursor()
		cursor.execute('SELECT pid FROM user WHERE tid = %s;', (uid,))
		pid = cursor.fetchone()[0]
		if pid:
			#	Если пользователь уже активировал промокод
			return 0
		cursor.execute('SELECT id FROM promo WHERE name = %s;', (promo,))
		promo_id = cursor.fetchone()
		if not promo_id:
			#	Если промокода нет в базе
			return -1
		cursor.execute('UPDATE user SET pid=%s WHERE tid=%s;', (promo_id[0], uid))
		self.db.commit()
		#	Добавляем id промокода пользователю
		return 1

	def get_step(self, uid):
		cursor = self.db.cursor()
		cursor.execute('SELECT to_pid, step FROM user WHERE tid = %s;', uid)
		step = cursor.fetchone()
		return step

	def boost_step(self, uid):
		cursor = self.db.cursor()
		pid = self.get_step(uid)
		if not pid:
			#	Ни один тест не назначен
			return None, None
		pid, step = pid
		que_list = self.get_questions()
		step += 1
		if step <= len(que_list):
			cursor.execute('UPDATE user SET step = %s WHERE tid = %s;', (step, uid))
			#	Возвращаем новый вопрос
			ans = pid, que_list[step - 1]
		else:
			cursor.execute('UPDATE user SET to_pid = %s, step = %s WHERE tid=%s;', (None, 0, uid))
			#	Ни один тест не назначен
			ans = None, None
		self.db.commit()
		return ans

	def set_to_pid(self, uid, pid):
		cursor = self.db.cursor()
		cursor.execute('UPDATE user SET to_pid = %s, step = 0 WHERE tid = %s;', (pid, uid,))
		self.db.commit()

	def get_deps(self):
		cursor = self.db.cursor()
		cursor.execute('SELECT * FROM department;')
		deps = cursor.fetchall()
		return deps

	def get_question(self, uid):
		pid, step = self.get_step(uid)
		if not pid:
			return None, None
		que_list = self.get_questions()
		return pid, que_list[step - 1]

	def get_questions(self):
		cursor = self.db.cursor()
		cursor.execute('SELECT * FROM question;')
		quests = cursor.fetchall()
		return quests

	def set_free_deps(self, uid, depid):
		cursor = self.db.cursor()
		deps = [(uid, i[0],) for i in self.get_deps() if i[0] != depid]
		cursor.executemany('INSERT INTO free_deps VALUES (%s, %s);', deps)
		self.db.commit()

	def get_free_deps(self, uid):
		cursor = self.db.cursor()
		user = self.get_user(uid)
		user_id = (user[0],)
		lop = []
		cursor.execute('SELECT depid FROM free_deps WHERE uid = %s;', user_id)
		deps = cursor.fetchall()
		for dep in deps:
			cursor.execute('SELECT * FROM department WHERE id = %s;', dep)
			lop.append(cursor.fetchall()[0])
		return lop

	def rmv_free_dep(self, uid, pid):
		cursor = self.db.cursor()
		user_id = self.get_user(uid)[0]
		cursor.execute('DELETE FROM free_deps WHERE uid = %s AND depid = %s;', (user_id, pid,))
		self.db.commit()

	def set_depid(self, uid, depid):
		cursor = self.db.cursor()
		try:
			cursor.execute('UPDATE user SET depid = %s WHERE tid = %s;', (depid, uid,))
			self.db.commit()
			user = self.get_user(uid)
			self.set_free_deps(user[0], user[4])
			return 1
		except:
			return 0

	def set_answer(self, uid, ans, ans_vars=True):
		usr = self.get_user(uid)
		cursor = self.db.cursor()
		tab_name = 'answer_vars' if ans_vars else 'answer_text'
		sql = f'INSERT INTO {tab_name} VALUES (%s, %s, %s, %s, %s, %s);'
		params = (None, usr[0], usr[4], usr[5], usr[6], ans,)
		cursor.execute(sql, params)
		self.db.commit()

	def is_admin(self, uid):
		promo_id = self.get_user(uid)[3]
		cursor = self.db.cursor()
		cursor.execute('SELECT admin FROM promo WHERE id = %s;', promo_id)
		ans = cursor.fetchone()[0]
		return 1 if ans == b'True' else 0

	def set_admin(self, uname):
		cursor = self.db.cursor()
		cursor.execute('SELECT * FROM user WHERE name = %s;', uname)
		ans = cursor.fetchone()
		if not ans: return
		cursor.execute('SELECT id FROM promo WHERE admin = %s;', b'True')
		ans = cursor.fetchone()[0]
		cursor.execute('UPDATE user SET pid = %s WHERE name = %s;', (ans, uname,))
		self.db.commit()
		return 1

	def del_admin(self, uname):
		cursor = self.db.cursor()
		cursor.execute('SELECT * FROM user WHERE name = %s;', uname)
		ans = cursor.fetchone()
		if not ans: return
		cursor.execute('SELECT id FROM promo WHERE admin = %s;', b'False')
		ans = cursor.fetchone()[0]
		cursor.execute('UPDATE user SET pid = %s WHERE name = %s;', (ans, uname,))
		self.db.commit()
		return 1

	def get_admins(self):
		cursor = self.db.cursor()
		cursor.execute('SELECT id FROM promo WHERE admin = %s;', b'True')
		ans = cursor.fetchone()[0]
		cursor.execute('SELECT name FROM user WHERE pid = %s;', ans)
		return cursor.fetchall()

	def get_statistic(self):
		cursor = self.db.cursor()
		depart = list(self.get_deps())
		depart.sort(key=lambda x: x[0])
		inds = [i[0] for i in depart]
		rating = [[''] + [i[1] for i in depart]]
		for i in inds:
			tmp = [depart[i - 1][1]]
			for j in inds:
				if i == j:
					tmp.append(0)
					continue
				cursor.execute('SELECT ans FROM answer_vars WHERE dep_id = %s AND to_dep_id = %s;', (i, j,))
				ans = cursor.fetchall()
				if ans == ():
					tmp.append(0)
					continue
				result = eval(''.join([k[0] for k in ans]))
				tmp.append(result)
			rating.append(tmp)
		return rating

	def get_text_answers(self):
		cursor = self.db.cursor()
		cursor.execute('SELECT * FROM answer_text')
		return list(cursor.fetchall())


def statistic(path, rating):
	wb = Workbook()
	ws = wb.active
	for i in rating:
		ws.append(i)
	wb.save(path)
	f = open(path, 'rb')
	return f
