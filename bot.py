# -*- coding: UTF-8 -*-

from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import BotCommand, BotCommandScopeChat

from config.config import bot_cfg, e_cfg


def info_filter(record):
    return record["level"].name == "INFO"


logger.add("logs/bot.log", rotation="1 MB", filter=info_filter)
logger.add("logs/error.log", rotation="5 MB", level="ERROR")

proxy = {
    "scheme": bot_cfg.scheme,  # 支持“socks4”、“socks5”和“http”
    "hostname": bot_cfg.hostname,
    "port": bot_cfg.port,
}

plugins = dict(root="module")

app = Client(
    "my_bot",
    proxy=proxy if all(proxy.values()) else None,
    bot_token=bot_cfg.bot_token,
    api_id=bot_cfg.api_id,
    api_hash=bot_cfg.api_hash,
    plugins=plugins,
    lang_code="zh",
)


# 设置菜单
@app.on_message(filters.command("menu") & filters.private & filters.user(e_cfg.admins))
async def menu(_, message):
    a_cmd = {
        "sw": "开关解析功能",
        "count": "今日解析次数",
        "d": "开关下载",
        "summary":"今日总结",
    }
    u_cmd = {
        "start": "开始",
        "help": "帮助",
    }
    if e_cfg.credit:
        u_cmd["credit"] = "鸣谢"

    await app.delete_bot_commands()

    for i in e_cfg.admins:
        await app.set_bot_commands(r_c(a_cmd), scope=BotCommandScopeChat(i))
    await app.set_bot_commands(r_c(u_cmd))
    await app.send_message(chat_id=message.chat.id, text="菜单设置成功，请退出聊天界面重新进入来刷新菜单")


def r_c(cmd: dict):
    return [BotCommand(command=k, description=v) for k, v in cmd.items()]


if __name__ == "__main__":
    from utiles.parse_count import clear_regularly
    logger.info("bot开始运行...")
    app.run(clear_regularly())
