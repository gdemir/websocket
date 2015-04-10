# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import tornado.websocket

import json

from tornado.options import define, options, parse_command_line

define("port", default=8888, help="run on the given port", type=int)

# we gonna store clients in dictionary..
clients = dict()

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self, *args):
        self.id = self.get_argument("id")
        clients[self.id] = { "id" : self.id, "self" : self }

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
        
		# kendi user_id'sini ve mesaj metni göndermek icin dict'ten jsona cevir -> JSON
        sendMessage = json.dumps({ "type" : "new_message", "message_body" : jsonData["message_body"], "user_id" : str(self.id) }) 

		# tüm istemcilere bu mesajı yolla #TODO sadece bazılarına basılacak
        for key, client in clients.iteritems(): 
            client["self"].write_message(sendMessage)

    def on_close(self):

        if self.id in clients:
            del clients[self.id]

        sendMessage = json.dumps({ "type" : "user_logout",  "user_id" : str(self.id) })
        for key, client in clients.iteritems():
            client["self"].write_message(sendMessage)

class IndexHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def get(self):
        #self.write("This is your response")
        self.render("index.html")
        #we don't need self.finish() because self.render() is fallowed by self.finish() inside tornado
        #self.finish()

app = tornado.web.Application([
    (r'/', IndexHandler),
    (r'/websocket', WebSocketHandler),
])

if __name__ == '__main__':
    parse_command_line()
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
