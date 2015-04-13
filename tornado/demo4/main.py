#!/usr/bin/env python
# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import tornado.websocket
import bcrypt
import concurrent.futures
import MySQLdb
import markdown
import os.path
import re
import subprocess
import torndb
import tornado.escape
from tornado import gen
import tornado.httpserver
import tornado.options 
import unicodedata

import logging
import os.path
import uuid

import tornado.auth

import json
import time

from tornado.options import define, options, parse_command_line

define("port", default=8888, help="run on the given port", type=int)
define("mysql_host", default="127.0.0.1:3306", help="chat database host")
define("mysql_database", default="CHAT", help="chat database name")
define("mysql_user", default="root", help="chat database user")
define("mysql_password", default="159654", help="chat database password")

# we gonna store clients in dictionary..
clients = dict()
class WebSocketHandler(tornado.websocket.WebSocketHandler):
	def load_message(self, json_data):
		messages = self.application.db.query("select \
								m.id as mail_id, \
								su.id as sender_id, \
								concat(su.first_name, ' ', su.last_name) as sender_full_name,  \
								ru.id as receive_id, \
								concat(ru.first_name, ' ', ru.last_name) as receive_full_name,  \
								m.body as body \
							from \
								Users su, \
								Users ru, \
								Messages m \
							where \
								m.receive_id = ru.id and \
								m.sender_id = su.id and \
								(sender_id = %s or sender_id = %s) and \
								(receive_id = %s or receive_id = %s)  \
								order by m.created_at desc limit %s",
								json_data["sender_id"], json_data["receive_id"],
								json_data["sender_id"], json_data["receive_id"], json_data["limit"])

		message = json.dumps({
					"type" : "load_message", 
					"sender_id" : json_data["sender_id"],
					"receive_id" : json_data["receive_id"],
					"messages" : messages
					})

		for key, client in clients.iteritems(): 
			if (client["id"] in [json_data["receive_id"], json_data["sender_id"]]):
				client["self"].write_message(message)

	def open(self, *args):
		self.id = self.get_argument("id")
		clients[self.id] = { "id" : self.id, "self" : self, "receive_id" : None }

		# yeni baglanti yapan cliente önceki user verilerini user_ids dictine yukle
		# yeni baglanti yapan cliente önceki user verilerini yolla dicten jsona cevir -> JSON
		user_ids = []
		for key, client in clients.iteritems():
			if client["id"] != self.id:
				user_ids.append(client["id"])
		self.write_message(json.dumps({
						"type" : "user_list" ,
						"user_ids" : user_ids
						}))

		# yeni baglanan clienti tum bagli clientlere gostermek icin dict'ten jsona cevir -> JSON
		# yeni baglanan clienti kendisi haric bagli olan clientlere gostermek yolla
		message = json.dumps({
					"type" : "new_user" ,
					"id" : self.id
					})
		for key, client in clients.iteritems():
			if client["id"] != self.id:
				client["self"].write_message(message)

	def on_message(self, data):
		# index.html'deki .send() fonksiyonundan gelen mesaji json mesaji dicte cevir -> DICT
		json_data = json.loads(data);
		if json_data["type"] == "new_message":
			date = time.strftime("%y-%m-%d %H:%M:%S")
			# anlık veriyi veritabanına basalım -> DB
			mail_id = self.application.db.execute("insert into Messages \
							          		(sender_id, receive_id, body, created_at, updated_at) \
							          values \
									(%s, %s, %s, %s, %s)",
									json_data["sender_id"], json_data["receive_id"], json_data["message_body"],
									date, date)

			
			
			# kendi user_id'sini ve mesaj metni gondermek icin dict'ten jsona cevir -> JSON
			# tüm istemcilere bu mesaji yolla
			message = json.dumps({
						"type" : "new_message",
						"mail_id" : mail_id,
						"sender_id" : json_data["sender_id"],
						"receive_id": json_data["receive_id"],
						"sender_full_name" : json_data["sender_full_name"],
						"receive_full_name": json_data["receive_full_name"],
						"message_body" : json_data["message_body"]
						})
			for key, client in clients.iteritems(): 
				if (client["id"] in [json_data["receive_id"], json_data["sender_id"]]):
					client["self"].write_message(message)

		elif json_data["type"] == "load_message":
			self.load_message(json_data)

		elif  json_data["type"] == "del_message":
			self.application.db.execute("delete from Messages where id = %s", json_data["mail_id"])
			self.load_message(json_data)

		elif  json_data["type"] == "info_message":
			for key, client in clients.iteritems(): 
				if (client["id"] in [json_data["receive_id"], json_data["sender_id"]]):
					client["self"].write_message(json_data)

	def on_close(self):
		# herhangi bir istemci oturumu kapattiginda onu client dictimizden silelim
		if self.id in clients:
			del clients[self.id]

		# silinen istemcinin idsini tum clientlerden silmek icin id'sini tüm istemcilere yolla
		for key, client in clients.iteritems():
			client["self"].write_message(json.dumps({ "type" : "user_logout",  "id" : str(self.id) }))

class LoginHandler(tornado.websocket.WebSocketHandler):
	def get(self):
		self.render("login.html", notice=None)

	def post(self):
		if self.get_argument("username") and self.get_argument("password"):
			user = self.application.db.get("select \
								id as id, \
								concat(first_name, ' ', last_name) as full_name \
							from Users \
							where \
								username = %s and password = %s",
								self.get_argument("username"), self.get_argument("password"))
			if user:
				# kullanıcı oturuma girdi diye güncelle
				self.application.db.execute("update Users set state_id = 1 where username = %s and password = %s", self.get_argument("username"), self.get_argument("password"))
				# kendisi hariç userları al
				users = self.application.db.query("select \
									id as id, \
									concat(first_name, ' ', last_name) as full_name \
								from Users \
								where not id = %s", user["id"])
				# self.set_secure_cookie("user_id", str(user["id"]))
				self.set_secure_cookie("user", "1")
				login = {
					"id" : user["id"],
					"full_name" : user['full_name'],
					"users" : users
					}
				self.render("user.html", login=login)
			else:
				notice = {"danger" : "Oops! İsminiz veya sifreniz hatali, belkide bunlardan sadece biri hatalidir?"}
				self.render("login.html", notice=notice)
		else:
				notice = {"warning" : "Kullanici adi ve parola bos birakilmamalidir"}
				self.render("login.html", notice=notice)

class NewHandler(tornado.web.RequestHandler):
	
	def get(self):
		self.redirect("new.html")

	def post(self):
		user = self.application.db.get("select * from Users where username = %s", self.get_argument("username"))
		if not user:
			self.application.db.execute("insert into Users \
							(first_name, last_name, username, password) \
						  values \
							(%s, %s, %s, %s)",
							self.get_argument("first_name"), self.get_argument("last_name"),
							self.get_argument("username"), self.get_argument("password"))
			notice = {
					"warning" : "Lutfen hesabiniza giris yapin!",
					"success" : self.get_argument("username") + " adinda yeni kayit olusturuldu",
				}
			self.render("login.html", notice=notice)
		else:
			notice = {"danger" : self.get_argument("username") + " kullanicisini zaten kullaniliyor!"}
			self.render("new.html", notice=notice)

class UserHandler(tornado.web.RequestHandler):
	
	def get(self):
		self.redirect("user.html")

class HomeHandler(tornado.web.RequestHandler):
	@tornado.web.asynchronous
	def get(self):
		self.render("home.html")


class Application(tornado.web.Application):
	def __init__(self):
		handlers = [
			(r"/",                    HomeHandler),
			(r"/login",           LoginHandler),
			(r"/user",            UserHandler),
			(r"/new",            NewHandler),
			(r'/websocket',  WebSocketHandler),
		]
		settings = dict(
			template_path=os.path.join(os.path.dirname(__file__), "templates"),
			static_path=os.path.join(os.path.dirname(__file__), "static"),
			xsrf_cookies=True,
			cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
			login_url="/login",
			debug=True,
		)
		super(Application, self).__init__(handlers, **settings)
		# Have one global connection to the blog DB across all handlers
		self.db = torndb.Connection(
			host=options.mysql_host, database=options.mysql_database,
			user=options.mysql_user, password=options.mysql_password)

if __name__ == '__main__':
	tornado.options.parse_command_line()
	http_server = tornado.httpserver.HTTPServer(Application())
	http_server.listen(options.port)
	tornado.ioloop.IOLoop.current().start()