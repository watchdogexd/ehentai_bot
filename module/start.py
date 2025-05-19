from pyrogram import Client, filters
from pyrogram.types import Message

import utiles.parse_count
from config.config import e_cfg

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
    if msg.from_user.id not in e_cfg.admins:
        if e_cfg.member_group is not None:
            try:
                user_status = await _.get_chat_member(e_cfg.member_group,msg.from_user.id)
            except UserNotParticipant as e:
                return await msg.reply(f"您没有权限使用本命令。({type(e).__name__})")
                pass
            except Exception as e:
                await msg.reply(f"请求失败：{type(e).__name__}, 错误信息：{e}")
                raise e
            if user_status.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return await msg.reply(f"您没有权限使用本命令。({str(user_status.status)})")
        else:
            return await msg.reply(f"您没有权限使用本命令。")
    await msg.reply(text=utiles.parse_count.parse_count.gen_summary())

@Client.on_message(filters.command("credit"))
async def credit(_,msg: Message):
    if e_cfg.credit:
        return await msg.reply(text=("" if e_cfg.credit is None else (e_cfg.credit)))
    else:
        return

# @Client.on_message(filters.command("config") & filters.private)
# async def config(_,msg: Message):
#     if msg.from_user.id not in e_cfg.admins:
#         if e_cfg.member_group is not None:
#             try:
#                 user_status = await _.get_chat_member(e_cfg.member_group,msg.from_user.id)
#             except UserNotParticipant as e:
#                 return
#                 pass
#             except Exception as e:
#                 return
#             if user_status.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
#                 return
#         else:
#             return
#     await msg.reply(text=str("\n".join([f"e_cfg.config['{i}']={e_cfg.config[i]}" for i in e_cfg.config])))
