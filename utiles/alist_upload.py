from config.config import e_cfg

import mimetypes
import httpx
import json

async def getToken():
    # 判断 url 结尾
    if e_cfg.alist_server.endswith("/"):
        url = e_cfg.alist_server + "api/auth/login"
    else:
        url = e_cfg.alist_server + "/api/auth/login"
    payload = json.dumps({
        "username": e_cfg.alist_username,
        "password": e_cfg.alist_password
    })
    headers = {
        'Content-Type': 'application/json'
    }
    async with httpx.AsyncClient() as client:
        response = client.post(url=url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            global alist_token
            alist_token = data.get('data', {}).get('token', None)

        

async def uploader(save_path):
    await getToken()

    if alist_token is None:
        print("未获取到 Alist Token")
        return
    
    # 上传到 alist
    if e_cfg.alist_server != "":
        # 判断 url 结尾
        if e_cfg.alist_server.endswith("/"):
            url = e_cfg.alist_server + "api/fs/put"
        else:
            url = e_cfg.alist_server + "/api/fs/put"
        upload_path = e_cfg.alist_upload_path
        mime_type, _ = mimetypes.guess_type(save_path)

        payload = '' # file contents
        headers = {
        'Authorization': alist_token,
        # 'Content-Length': str(os.path.getsize(save_path)),
        'File-Path': upload_path,
        'Content-Type': mime_type
        }
        async with httpx.AsyncClient() as client:
            with open (save_path, "rb") as f:
                file_data = f.read()
                payload = file_data
                response = await client.put(url, json=payload, headers=headers)

                print(f"Status Code: {response.status_code}")
                print(f"Response Body: {response.text}")