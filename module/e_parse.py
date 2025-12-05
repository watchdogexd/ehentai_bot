import os
from dataclasses import dataclass
from limits import user_limiters, global_limiter, user_locks

from loguru import logger
from pyrogram import Client, filters, enums, types
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup as Ikm,
    InlineKeyboardButton as Ikb,
    CallbackQuery,
    MessageEntity
)

from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant

from config.config import e_cfg, DP, bot_cfg
from utiles.download_file import download_file
from utiles.ehArchiveD import EHentai, GMetaData
from utiles.filter import is_admin
from utiles.parse_count import parse_count
from utiles.utile import is_admin_, rate_limit, is_whitelist_
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.start()


@Client.on_message(
    filters.regex(r"https://(?:e-|ex)hentai.org/g/(\d+)/([a-f0-9]+)") & filters.private
)
@rate_limit(
    request_limit=e_cfg.request_limit,
    time_limit=e_cfg.time_limit,
    total_request_limit=e_cfg.total_request_limit,
)
@logger.catch
async def ep(_: Client, msg: Message):
    user_id = msg.from_user.id

    # 检查功能禁用状态
    if e_cfg.disable and not is_admin_(user_id):
        return await msg.reply("解析功能暂未开放")

    user_limiter = user_limiters[user_id]

    if (not is_whitelist_(user_id=user_id)) and (not is_admin_(user_id=user_id)):
        if e_cfg.member_group is not None:
            try:
                user_status = await _.get_chat_member(e_cfg.member_group,msg.from_user.id)
                logger.info(f"用户 {msg.from_user.id} 在群 {e_cfg.member_group} 的状态为 {str(user_status.status)}") # debug
            except UserNotParticipant as e:
                return await msg.reply(f"您没有权限使用本 Bot。({type(e).__name__})")
            except Exception as e:
                await msg.reply(f"解析失败：{type(e).__name__}, 错误信息：{e}")
                raise e
            if user_status.status not in [enums.ChatMemberStatus.RESTRICTED,enums.ChatMemberStatus.MEMBER,enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return await msg.reply(f"您没有权限使用本 Bot。({str(user_status.status)})")
            if user_status.status == enums.ChatMemberStatus.RESTRICTED:
                perms: types.ChatPermissions = user_status.permissions
                if perms is not None and perms.can_send_messages is False:
                    return await msg.reply("您在群组中被禁止发送消息，无法使用本 Bot。")
                if not user_status.is_member:
                    return await msg.reply("您不是群组的成员，无法使用本 Bot。")

    # 全局与用户限流检查
    if not global_limiter.has_capacity():
        return await msg.reply("当前请求人数过多，请稍后再试。")

    if not user_limiter.has_capacity():
        return await msg.reply(f"你已达到每分钟请求上限，请稍后再试。")

    async with global_limiter, user_limiter:
        lock = user_locks[user_id]

        if lock.locked():
            return await msg.reply("你有一个任务正在处理中，请完成后再试。")

        async with lock:
            m = await msg.reply("解析中...")

            if e_cfg.estimate_usage:
                #TODO: 加入 GP 预计算逻辑
                try:
                    if e_cfg.confirm_estimate_download:
                        estimation = await ehentai_estimate(msg.text,True)
                    else:
                        estimation = await ehentai_estimate(msg.text,True)
                except Exception as e:
                    await m.edit(f"预估损耗失败：{type(e).__name__}, 错误信息：{e}")
                    raise e
                
                # await msg.reply("您尚处测试，没有实际解析。")
                # return 
                
                # try:
                #     erp = await ehentai_parse_fastforward(estimation, True)
                # except Exception as e:
                #     await m.edit(f"解析直链失败：{type(e).__name__}, 错误信息：{e}")
                #     raise e
                
                if e_cfg.telegram_logger is not None:
                    entities = [
                        MessageEntity(type=enums.MessageEntityType.CODE,offset=len(str("用户 ")),length=len(str(msg.from_user.id))),
                        MessageEntity(type=enums.MessageEntityType.TEXT_MENTION,offset=len(str("用户 " + str(msg.from_user.id) + "(")),length=len(str(msg.from_user.full_name)),user=msg.from_user),
                        MessageEntity(type=enums.MessageEntityType.TEXT_LINK,offset=len("用户 " + str(msg.from_user.id) + "("+str(msg.from_user.full_name) + ")" +" 解析了 "),length=len(str(estimation.archiver_info.title)),url=str(msg.text))]
                    log_message = "用户 " + str(msg.from_user.id) + "("+str(msg.from_user.full_name) + ")" \
                                +" 解析了 "+str(estimation.archiver_info.title) + "\n预计"\
                                + ((("损耗 "+str(round(estimation.gp_usage/1000,ndigits=2)) +"kGP.") if estimation.gp_usage >= 1000 else \
                                     "损耗 "+str(estimation.gp_usage) +"GP." ) if estimation.using_gp else \
                                  ("损耗 "+str(round(estimation.quota_usage/1024/1024,ndigits=2)) +"MB Quota."))
                    try:
                        await _.send_message(chat_id=e_cfg.telegram_logger,parse_mode=enums.ParseMode.MARKDOWN,text=log_message,entities=entities)
                    except Exception as e:
                        logger.error(f"[{type(e).__name__}]无法在 Telegram 频道中发送解析日志。请检查 config/config.yaml->experimental.tg_logger 是否正确配置为记录目标群/频道/聊天。{e}")
                if e_cfg.single_gp_limit is not None and e_cfg.single_gp_limit > 0:
                    if estimation.gp_usage > e_cfg.single_gp_limit:
                        if (not is_whitelist_(user_id=user_id)) and (not is_admin_(user_id=user_id)):
                            btn = Ikm(
                                [
                                    [
                                        Ikb("GP 损耗超过下载限额"+str(round(e_cfg.single_gp_limit/1000,2))+"kGP","lorem"),
                                    ]
                                ]
                            )
                            caption = "预计消耗" + \
                                (((str(round(estimation.gp_usage/1000,ndigits=2)) +"kGP.") if estimation.gp_usage >= 1000 else \
                                str(estimation.gp_usage) +"GP." ) if estimation.using_gp else \
                                (str(round(estimation.quota_usage/1024/1024,ndigits=2)) +"MB Quota.")) + "\n" +\
                                "**超出 Bot 限额。**"
                            await msg.reply_document(estimation.json_path, quote=True, reply_markup=btn,caption=caption)
                            await m.delete()
                            os.remove(estimation.json_path)
                            return
                if e_cfg.single_quota_limit is not None and e_cfg.single_quota_limit > 0:
                    if estimation.quota_usage > e_cfg.single_quota_limit:
                        if (not is_whitelist_(user_id=user_id)) and (not is_admin_(user_id=user_id)):
                            btn = Ikm(
                                [
                                    [
                                        Ikb("Quota 损耗超过下载限额"+str(round(e_cfg.single_quota_limit/1024/1024,2))+"MB","lorem"),
                                    ]
                                ]
                            )
                            caption = "预计消耗" + \
                                (((str(round(estimation.gp_usage/1000,ndigits=2)) +"kGP.") if estimation.gp_usage >= 1000 else \
                                str(estimation.gp_usage) +"GP." ) if estimation.using_gp else \
                                (str(round(estimation.quota_usage/1024/1024,ndigits=2)) +"MB Quota.")) + "\n" +\
                                "**超出 Bot 限额。**"
                            await msg.reply_document(estimation.json_path, quote=True, reply_markup=btn,caption=caption)
                            await m.delete()
                            os.remove(estimation.json_path)
                            return
                if e_cfg.confirm_estimate_download:
                    d = f"{estimation.archiver_info.gid}/{estimation.archiver_info.token};"
                    btn = Ikm(
                        [
                            [
                                Ikb("确认解析", f"confirm_{d}"),
                            ]
                        ]
                    )
                    caption = "预计消耗" + \
                        (((str(round(estimation.gp_usage/1000,ndigits=2)) +"kGP.") if estimation.gp_usage >= 1000 else \
                           str(estimation.gp_usage) +"GP." ) if estimation.using_gp else \
                          (str(round(estimation.quota_usage/1024/1024,ndigits=2)) +"MB Quota."))
                    await msg.reply_document(estimation.json_path, quote=True, reply_markup=btn,caption=caption)
                    await m.delete()
                    os.remove(estimation.json_path)
                    return
                else:
                    try:
                        erp = await ehentai_parse_fastforward(estimation, True)
                    except Exception as e:
                        await m.edit(f"解析直链失败：{type(e).__name__}, 错误信息：{e}")
                        raise e
            else:
                try:
                    erp = await ehentai_parse(msg.text, True)
                except Exception as e:
                    await m.edit(f"解析失败：{type(e).__name__}, 错误信息：{e}")
                    raise e
                

            d = f"{erp.archiver_info.gid}/{erp.archiver_info.token}"
            btn = Ikm(
                [
                    [
                        Ikb("下载", f"download_{d}")
                        if e_cfg.download
                        else Ikb("下载", url=erp.d_url),
                        Ikb("销毁下载", callback_data=f"cancel_{d}"),
                    ]
                ]
            )

            if not e_cfg.download and e_cfg.destroy_regularly:
                await destroy_regularly(msg.text)

            await msg.reply_document(erp.json_path, quote=True, reply_markup=btn)
            await m.delete()

            uc = parse_count.get_counter(user_id)
            uc.add_count(erp.require_gp,erp.archiver_info.filesize)
            logger.info(
                f"{msg.from_user.full_name} 归档 {msg.text} "
                f"(今日 {uc.day_count} 个) "
                f"(消耗 {f'{erp.require_gp} GP' if erp.require_gp else '免费'})"
            )
            os.remove(erp.json_path)


@dataclass
class EPR:
    archiver_info: GMetaData
    d_url: str
    require_gp: int
    json_path: str = None

@dataclass
class Usage_Estimation:
    archiver_info: "GMetaData"
    e_hentai: EHentai
    using_quota: bool
    using_gp: bool
    quota_usage: int
    gp_usage: int
    json_path: str = None

async def ehentai_parse(url: str, o_json: bool = False) -> EPR:
    """解析e-hentai画廊链接"""
    ehentai = EHentai(e_cfg.cookies, proxy=bot_cfg.proxy)
    archiver_info = await ehentai.get_archiver_info(url)
    require_gp = await ehentai.get_required_gp(archiver_info)
    d_url = await ehentai.get_download_url(archiver_info)

    if o_json:
        json_path = ehentai.save_gallery_info(archiver_info, DP)
        return EPR(archiver_info, d_url, require_gp, json_path)
    return EPR(archiver_info, d_url, require_gp)

async def ehentai_estimate(url: str, o_json: bool = False) -> Usage_Estimation:
    ehentai = EHentai(e_cfg.cookies, proxy=bot_cfg.proxy)
    archiver_info = await ehentai.get_archiver_info(url)
    require_gp = await ehentai.get_required_gp(archiver_info)

    if o_json:
        json_path = ehentai.save_gallery_info(archiver_info, DP)
        return Usage_Estimation(archiver_info,ehentai,require_gp==0,require_gp!=0,archiver_info.filesize,require_gp,json_path)
    return Usage_Estimation(archiver_info,ehentai,require_gp==0,require_gp!=0,archiver_info.filesize,require_gp)

async def ehentai_parse_fastforward(estimation: Usage_Estimation, o_json: bool = False) -> EPR:
    d_url = await estimation.e_hentai.get_download_url(estimation.archiver_info)

    if o_json:
        json_path = estimation.e_hentai.save_gallery_info(estimation.archiver_info, DP)
        return EPR(estimation.archiver_info, d_url, estimation.gp_usage, json_path)
    return EPR(estimation.archiver_info, d_url, estimation.gp_usage)

async def cancel_download(url: str) -> bool:
    """销毁下载"""
    ehentai = EHentai(e_cfg.cookies, proxy=bot_cfg.proxy)
    archiver_info = await ehentai.get_archiver_info(url)
    return await ehentai.remove_download_url(archiver_info)


@Client.on_callback_query(filters.regex(r"^download_"))
async def download_archiver(_, cq: CallbackQuery):
    await cq.message.edit_reply_markup(Ikm([[Ikb("下载中...", "downloading")]]))
    gurl = cq.data.split("_")[1]
    try:
        epr = await ehentai_parse(gurl)
        file = f"{epr.archiver_info.gid}.zip"
        # 判断文件大小是否超过 2GB
        if round(epr.archiver_info.filesize/1024/1024,ndigits=2) > 2048:
            return await cq.message.reply("文件超过 2048MB，无法下载")
        if not os.path.exists(file):
            """已存在则不再下载"""
            file = await download_file(epr.d_url, file, proxy=bot_cfg.proxy)
    except Exception as e:
        await cq.message.reply(f"下载失败: {e}")
        raise e
    await cq.message.edit_reply_markup()
    await cq.message.reply_chat_action(enums.ChatAction.UPLOAD_DOCUMENT)

    await cq.message.reply_document(file, quote=True)
    await cancel_download(gurl)

@Client.on_callback_query(filters.regex(r"^confirm_"))
async def confirm_download(_ : Client, cq:CallbackQuery):
    user_id = cq.from_user.id
    await cq.message.edit_reply_markup(Ikm([[Ikb("解析中...", "resolving")]]))
    gurl = cq.data.split("_")[1]
    try:
        erp = await ehentai_parse(gurl)
    except Exception as e:
        await _.send_message(chat_id=cq.from_user.id,text=f"解析失败：{type(e).__name__}, 错误信息：{e}")
        raise e
    d = f"{erp.archiver_info.gid}/{erp.archiver_info.token}"

    is_allowed = e_cfg.download or (e_cfg.download_admin_only and is_admin_(user_id))
    file_btn = Ikb("文件下载", f"download_{d}") if is_allowed else None
    link_btn = Ikb("直链解析", url=erp.d_url) if is_allowed else Ikb("下载", url=erp.d_url)
    cancel_btn = Ikb("销毁下载", callback_data=f"cancel_{d}")

    btn = Ikm([[b for b in [file_btn, link_btn, cancel_btn] if b is not None]])

    await cq.message.edit_reply_markup(btn)
    if e_cfg.telegram_logger is not None:
        entities = [
            MessageEntity(type=enums.MessageEntityType.CODE,offset=len(str("用户 ")),length=len(str(cq.from_user.id))),
            MessageEntity(type=enums.MessageEntityType.TEXT_MENTION,offset=len(str("用户 " + str(cq.from_user.id) + "(")),length=len(str(cq.from_user.full_name)),user=cq.from_user),
            ]
        log_message = "用户 " + str(cq.from_user.id) + "("+str(cq.from_user.full_name) + ")" \
                    + ((("损耗 "+str(round(erp.require_gp,ndigits=2)) +"kGP.") if erp.require_gp >= 1000 else \
                        "损耗 "+str(erp.require_gp) +"GP." ) if erp.require_gp > 0 else \
                    ("损耗 "+str(round(erp.archiver_info.filesize/1024/1024,ndigits=2)) +"MB Quota."))
        try:
            await _.send_message(chat_id=e_cfg.telegram_logger,parse_mode=enums.ParseMode.MARKDOWN,text=log_message,entities=entities)
        except Exception as e:
            logger.error(f"[{type(e).__name__}]无法在 Telegram 频道中发送解析日志。请检查 config/config.yaml->experimental.tg_logger 是否正确配置为记录目标群/频道/聊天。{e}")
    uc = parse_count.get_counter(user_id)
    uc.add_count(erp.require_gp,erp.archiver_info.filesize)
    logger.info(
        f"{cq.from_user.full_name} 归档 {gurl} "
        f"(今日 {uc.day_count} 个) "
        f"(消耗 {f'{erp.require_gp} GP' if erp.require_gp else '免费'})"
    )

@Client.on_callback_query(filters.regex(r"^lorem"))
async def idle(_,cq: CallbackQuery):
    return await cq.answer("请联系 Bot 管理员修改限额")

@Client.on_callback_query(filters.regex(r"^cancel_"))
async def cancel_dl(_, cq: CallbackQuery):
    gurl = cq.data.split("_")[1]
    logger.info(f"{cq.from_user.full_name} 销毁 {gurl}")
    if not (await cancel_download(gurl)):
        await cq.answer("销毁下载失败")
        s = "失败"
    else:
        await cq.message.edit_reply_markup()
        await cq.answer("已销毁下载")
        s = "成功"
    logger.info(f"{cq.from_user.full_name} 创建的 {gurl} 销毁{s}")


@Client.on_message(filters.command("count") & is_admin)
async def count(_, msg: Message):
    await msg.reply(
        f"今日解析次数: __{parse_count.get_all_count()}__\n今日消耗 GP: __{parse_count.get_all_gp()}__"
    )


async def destroy_regularly(url: str):
    """定时销毁下载"""
    scheduler.add_job(
        cancel_download, "interval", args=[url], seconds=e_cfg.destroy_regularly
    )
