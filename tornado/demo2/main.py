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
import tornado.ioloop
import tornado.options
import tornado.web
import unicodedata

import logging
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import os.path
import uuid


import json

from tornado.options import define, options, parse_command_line

define("port", default=8888, help="run on the given port", type=int)
define("mysql_host", default="127.0.0.1:3306", help="chat database host")
define("mysql_database", default="CHAT", help="chat database name")
define("mysql_user", default="root", help="chat database user")
define("mysql_password", default="159654", help="chat database password")

# we gonna store clients in dictionary..
clients = dict()

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self, *args):
        self.id = self.get_argument("id")
        self.receive_id = self.get_argument("receive_id")
        clients[self.id] = { "id" : self.id, "self" : self, "receive_id" : self.receive_id }

		# yeni baglanti yapan cliente önceki user verilerini usersIds dictine yükle
        usersIds = []
        for key, client in clients.iteritems():
            usersIds.append(client["id"])

		# yeni baglanti yapan cliente önceki user verilerini yolla dicten jsona cevir -> JSON
        sendMessage = json.dumps({ "type" : "user_list" , "users_ids" : usersIds })
        self.write_message(sendMessage)

	    # yeni baglanan clienti tüm bagli clientlere göstermek icin dict'ten jsona cevir -> JSON
        sendMessage = json.dumps({ "type" : "new_user" , "user_id" : self.id })

        # yeni baglanan clienti kendisi haric bagli olan clientlere göstermek yolla
        for key, client in clients.iteritems():
            if client["id"] != self.id:
                client["self"].write_message(sendMessage)

    def on_message(self, receivedData):
		#  index.html'deki .send() fonksiyonundan gelen mesaji json mesaji dicte cevir -> DICT
        jsonData = json.loads(receivedData);
        if jsonData["type"] == "new_message":
			# kendi user_id'sini ve mesaj metni göndermek icin dict'ten jsona cevir -> JSON
		sendMessage = json.dumps({ "type" : "new_message", "message_body" : jsonData["message_body"], "user_id" : str(self.id) }) 

		# tüm istemcilere bu mesajı yolla #TODO sadece bazılarına basılacak
		for key, client in clients.iteritems(): 
			if (client["receive_id"] == jsonData["receive_id"]) or (client["id"] == self.id):
				client["self"].write_message(sendMessage)

	elif jsonData["type"] == "select_user":
		sendMessage = json.dumps({ "type" : "select_user", "message_body" : jsonData["message_body"], "user_id" : str(self.id) }) 
		for key, client in clients.iteritems(): 
			if client["id"] == jsonData["message_body"]:
				client["self"].write_message(sendMessage)
				

    def on_close(self):

		# herhangi bir istemci oturumu kapattiginda onu client dictimizden silelim
        if self.id in clients:
            del clients[self.id]
		
		# silinen istemcinin idsini tüm clientlerden silmek icin id'sini tüm istemcilere yolla
        sendMessage = json.dumps({ "type" : "user_logout",  "user_id" : str(self.id) })
        for key, client in clients.iteritems():
            client["self"].write_message(sendMessage)

class LoginHandler(tornado.websocket.WebSocketHandler):
    def get(self):
		self.render("login.html", error=None)

    def post(self):
		user = self.application.db.get("select * from Users where username = %s and password = %s", self.get_argument("username"), self.get_argument("password"))

		if not user:
			self.render("login.html", error="Basarisiz")
			self.application.db.execute("update Users set state_id = 1 where username = %s and password = %s", self.get_argument("username"), self.get_argument("password"))
			users = self.application.db.query("select * from Users")
			self.set_secure_cookie("user_id", str(user["id"]))
			self.set_secure_cookie("receive_id", None)
	
		user_id = user["username"]
		receive_id = user["username"]
		data = {"user_id" : user_id, "receive_id" : receive_id }
		self.render("index.html", data=data)

class IndexHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
        #self.write("This is your response")
        self.render("index.html")
        #we don't need self.finish() because self.render() is fallowed by self.finish() inside tornado
        #self.finish()

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/",            IndexHandler),
            (r"/login",       LoginHandler),
            (r'/websocket',   WebSocketHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/",
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
