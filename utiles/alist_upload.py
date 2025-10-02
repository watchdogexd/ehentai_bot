from config.config import e_cfg

import mimetypes
import httpx
from pathlib import Path
from loguru import logger

async def getToken():
    # 判断 url 结尾
    if e_cfg.alist_server.endswith("/"):
        url = e_cfg.alist_server + "api/auth/login"
    else:
        url = e_cfg.alist_server + "/api/auth/login"
    payload = {
        "username": e_cfg.alist_username,
        "password": e_cfg.alist_password
    }
    headers = {
        'Content-Type': 'application/json'
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url=url, json=payload, headers=headers)
            response.raise_for_status() # 400-599 抛出异常
        except Exception as e:
            logger.error(f"Alist 登录接口错误: {response.status_code}, body: {response.text}")
            raise e
        
        try:
            data = response.json()
            global alist_token
            alist_token = data.get('data', {}).get('token')
            if not alist_token:
                raise ValueError("Alist Token 未找到")
        except Exception as e:
            logger.error(f"获取 Alist Token 失败: {e}")
            raise e

        

async def uploader(save_path):
    await getToken()
    
    # 上传到 alist
    if e_cfg.alist_server != "":
        # 判断 url 结尾
        if e_cfg.alist_server.endswith("/"):
            url = e_cfg.alist_server + "api/fs/put"
        else:
            url = e_cfg.alist_server + "/api/fs/put"
        upload_path = e_cfg.alist_upload_path + Path(save_path).name
        mime_type, _ = mimetypes.guess_type(save_path) # 判断文件类型
        if not mime_type:
            mime_type = 'application/octet-stream'

        headers = {
        'Authorization': alist_token,
        'File-Path': upload_path,
        'Content-Type': mime_type
        }

        try:
            payload = Path(save_path).read_bytes()
        except Exception as e:
            logger.error(f"读取文件 {save_path} 失败: {e}")
            raise e
        async with httpx.AsyncClient() as client:
            response = await client.put(url, data=payload, headers=headers)

            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")