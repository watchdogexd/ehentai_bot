from time import time

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from bot import app
from config.config import e_cfg

class Counter:
    def __init__(self):
        self.now_count = 0
        self.day_count = 0
        self.request_time = 0
        self.day_require_gp = 0 # per GP
        self.day_quota_usage = 0 # per Byte

    def add_count(self, gp=0, quota=0):
        self.now_count += 1
        self.day_count += 1
        self.day_require_gp += gp
        self.day_quota_usage += quota
        self.request_time = time()

    def reset_now_count(self):
        self.now_count = 0
        self.request_time = 0

    def reset_day_count(self):
        self.day_count = 0
        self.day_require_gp = 0
        self.day_quota_usage = 0


from config.chat_data import chat_data


class UserCount:
    def __init__(self):
        if not chat_data.get("UserCount"):
            chat_data["UserCount"] = {}
        self.data: dict[int, Counter] = chat_data["UserCount"]

    def get_counter(self, uid: int):
        return self.init(uid)

    def reset_all_day_count(self):
        [i.reset_day_count() for i in self.data.values()]
        logger.info("已重置今日解析次数")

    def gen_summary(self):
        today_quota = self.get_all_quota()
        today_gp = self.get_all_gp()
        summary = "24h 内总结 \n" + \
                "共消耗 Quota " + \
                (str(round(today_quota/1024/1024/1024,2))+"GB \n" if today_quota >= 1024 * 1024 * 1024 else (\
                str(round(today_quota/1024/1024,2))+"MB \n" if today_quota >= 1024 * 1024 else (\
                str(round(today_quota/1024,2))+"KB \n"))) + \
                "共消耗 " + \
                (str(round(today_gp/1000/1000,2))+"mGP" if today_gp >= 1000*1000 else ( \
                (str(round(today_gp/1000,2))+"kGP" if today_gp >= 1000 else ( \
                str(today_gp) + "GP"))))
        return summary

    def day_cleanup(self):
        if e_cfg.day_cleanup:
            if e_cfg.telegram_logger is not None:
                app.send_message(chat_id=e_cfg.telegram_logger,text=self.gen_summary())
        self.reset_all_day_count()

    def get_all_count(self):
        return sum(i.day_count for i in self.data.values())

    def get_all_gp(self):
        return sum(i.day_require_gp for i in self.data.values())
    
    def get_all_quota(self):
        return sum(i.day_quota_usage for i in self.data.values())

    def init(self, uid: int):
        if not self.data.get(uid):
            self.data[uid] = Counter()
        return self.data[uid]


parse_count = UserCount()


def clear_regularly():
    scheduler = BackgroundScheduler()
    scheduler.add_job(parse_count.day_cleanup, "cron", hour=0, minute=0)
    scheduler.start()


clear_regularly()
