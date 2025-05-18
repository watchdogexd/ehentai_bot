from pyrogram import Client, filters
from pyrogram.types import Message

import utiles.parse_count

@Client.on_message(filters.command("start"))
async def start(_, msg: Message):
    await msg.reply("请发送画廊链接\n例: `https://e-hentai.org/g/2936195/178b3c5fec`")


@Client.on_message(filters.command("help"))
async def help_(_, msg: Message):
    await msg.reply("请发送画廊链接\n例: `https://e-hentai.org/g/2936195/178b3c5fec`")

@Client.on_message(filters.command("getid"))
async def getid(_, msg: Message):
    await _.send_message(chat_id=msg.chat.id,text=("您的 TgID: `"+str(msg.from_user.id)+"`\n" if msg.from_user is not None else "")+"当前 ChatID: `"+str(msg.chat.id)+"`")

@Client.on_message(filters.command("summary"))
async def summary(_,msg: Message):
    await msg.reply(text=utiles.parse_count.parse_count.gen_summary())