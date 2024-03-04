import yaml
import binascii

from pypinyin import pinyin, Style
from asyncio import sleep as asleep

import sys, os
_current_dir = os.path.dirname(__file__)
if _current_dir not in sys.path:
    sys.path.insert(-1, _current_dir)

from .async_rcon import rcon
# from rcon.source import rcon
from rcon.exceptions import WrongPassword
from asyncio.exceptions import TimeoutError

import hoshino
from hoshino import Service,priv

from .RSA import RSAworker, PrivateKeyNotMatchError
from .util import *

sv = Service(
    name = 'PalServerRcon',  #功能名
    use_priv = priv.NORMAL, #使用权限   
    manage_priv = priv.ADMIN, #管理权限
    visible = True, #False隐藏
    enable_on_default = True, #是否默认启用
    )

help_msg = f'''=== 帕鲁Rcon帮助 ===
帕鲁rcon绑定
帕鲁服务器信息
谁在帕鲁
帕鲁关服
帕鲁广播 + 广播内容
帕鲁rcon指令 + 指令
'''.strip()
# showplayers和broadcast都是残废，遇到非英文就出问题，broadcast显示不会换行

bind_help1 = "请使用以下指令：\n帕鲁rcon绑定\n服务器ip\nrcon端口\n公钥加密的AdminPassword"

bind_help2 = '''
帕鲁rcon绑定
192.168.0.10
25575
DHR3peGBwROMsUhwykRoYhizuA375KhUngRRaIkBq8BXZcMEFawcklLZ4VMwiZbpFmDrT7cu273bq2YsaMsv+jmXsK1WBdYM3rQn4jwDcj7f80Q2+o6ek6lieWcKPkAVpXe8oFrcQFsk5yaP8DmzW+JoSyP/NJAIwAbg+JIq1PeO3IKORoTEvJDN6ogd2y1Q1uyW7dEiP0xT635soO5qnujXc62ZwYartBYGSccXntYuCptcWV+KnsV67ic8Z+FSF8P/jypngiIflV5pKvnK3dm1gBaImtfoLN1vpZJWHGE1NCprIFF4VS7kL6muym8aV3NhMfu0AdAoUv+N+H7JKA==
'''

_timeout_return = "连接超时，请依次排查\n ·IP是否配置正确\n ·rcon端口是否配置正确\n ·服务端是否启用rcon\n ·PalServer是否在运行中\n ·是否放行rcon端口（tcp）。"

rsa = RSAworker()  # 初始化一个RSAworker。首次调用自动生成RSA2048公私钥对

async def send_rcon_command(SERVER_ADDRESS, SERVER_PORT,RCON_PASSWORD, command, timeout=2):
    """异步发送rcon指令"""
    _success = False
    # 创建RCON连接
    try:
        response = await rcon(command,host=SERVER_ADDRESS, port=SERVER_PORT, passwd=RCON_PASSWORD, timeout=2, enforce_id=False)
    except WrongPassword:
        return [_success, "WrongPassword!"]
    except TimeoutError as e:
        return [_success, f"TimeoutError: {str(e)}\n{_timeout_return}"]
    # except Exception as e:
    #     return [_success, f"Unknow Error:{str(e)}"]
    else:
        _success = True
        return [_success, response.strip()]

async def read_config():
    '''读配置文件'''
    with open(os.path.join(_current_dir, "config.yaml"), "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data

async def write_config(data):
    '''写配置文件'''
    with open(os.path.join(_current_dir, "config.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)

async def decrypt_admin_password(cipher):
    '''解密服务器私钥'''
    try:
        RCON_PASSWORD = rsa.decrypt(cipher)
        return [True, "", RCON_PASSWORD]
    except PrivateKeyNotMatchError:
        msg = "AdminPassword解密失败，可能是由于服务端密钥重置导致的。请重新绑定。"
        return [False, msg, ""]
    except binascii.Error:
        msg = "AdminPassword解密失败，可能是错误地修改配置文件中的密文导致的，请重新绑定"
        return [False, msg, ""]
    except Exception as e:
        return [False, "Unkonwn Error: \ne", ""]

@sv.on_prefix("帕鲁rcon绑定")
async def pal_rcon_register(bot, ev):
    is_admin = hoshino.priv.check_priv(ev, hoshino.priv.ADMIN)
    if not is_admin:
        await bot.send("权限不足")
        return 
    messages = str(ev.message).split("\n")
    if len(messages) != 3:
        help_img = "[CQ:image,file=file://{os.path.join(os.getcwd(),'encrypted_example.jpg')}]"
        help_img = "[CQ:image,file=https://s2.loli.net/2024/03/02/NWfxYkHFSndiUap.jpg]"
        bind_help_forward = render_forward_msg(msg_list = [bind_help1, "为保证AdminPassword不被泄漏，请使用服务端公钥加密后，发送密文", "加密公钥如下：", rsa.get_pub_key(), "请使用RSA加密工具加密AdminPassword，如https://www.toolhelper.cn/AsymmetricEncryption/RSA/", help_img, "例如\n"+bind_help2])
        await bot.send_group_forward_msg(group_id=ev.group_id, messages=bind_help_forward)
        return
    if not is_valid_ip(messages[0].strip()):
        await bot.send(ev, f"{messages[0]}不是一个有效的IP地址，请检查")
        return
    if not is_valid_port(int(messages[1].strip())):
        await bot.send(ev, f"{messages[1]}不是一个有效的端口号，请检查")
        return
    try:
        plain_AdminPassword = rsa.decrypt(messages[2].strip())
    except:
        await bot.send(ev, f"密文解密失败！请仔细阅读说明后再试。")
        return 
    server_address = messages[0].strip()
    rcon_port = messages[1].strip()
    admin_password = messages[2].strip()
    data = await read_config()
    _ori = data['groups'].get(ev.group_id)  # 可能存在的原配置
    data['groups'][ev.group_id] = {"server_address":str(server_address), "rcon_port":rcon_port, "admin_password":str(admin_password)}
    await write_config(data)
    if _ori is not None:
        msg = f"群帕鲁rcon连接信息已经更新！\n原IP: {_ori['server_address']}\n原RCON端口: {_ori['rcon_port']}"
        msg += f"\n\n新IP: {server_address}\n新RCON端口: {rcon_port}"
    else:
        msg = f"群帕鲁rcon连接信息配置成功！\nIP: {server_address}\nRCON端口: {rcon_port}"
    await bot.send(ev, msg)

@sv.on_fullmatch("帕鲁服务器信息")
async def pal_server_info(bot, ev):
    gid = ev.group_id
    data = await read_config()
    group_server_data = data['groups'].get(gid)
    if group_server_data is None:
        msg = "群聊还未绑定帕鲁服务器，请发送“帕鲁rcon绑定”进一步了解。"
    else:
        SERVER_ADDRESS = group_server_data.get("server_address")
        SERVER_PORT = group_server_data.get("rcon_port")
        decrypted = await decrypt_admin_password(group_server_data.get("admin_password"))
        if decrypted[0]:
            RCON_PASSWORD = decrypted[2]
            res = await send_rcon_command(SERVER_ADDRESS, SERVER_PORT, RCON_PASSWORD, "Info")
            msg = res[1] if res[0] else "error: " + res[1]
        else:
            msg = decrypted[1]
    await bot.send(ev,msg)

@sv.on_fullmatch("谁在帕鲁")
async def pal_server_info(bot, ev):
    gid = ev.group_id
    data = await read_config()
    group_server_data = data['groups'].get(gid)
    if group_server_data is None:
        msg = "群聊还未绑定帕鲁服务器，请发送“帕鲁rcon绑定”进一步了解。"
    else:
        SERVER_ADDRESS = group_server_data.get("server_address")
        SERVER_PORT = group_server_data.get("rcon_port")
        decrypted = await decrypt_admin_password(group_server_data.get("admin_password"))
        if decrypted[0]:
            RCON_PASSWORD = decrypted[2]
            await bot.send(ev, "正在查询，如果服内有ID非英文的玩家，可能需要等待数十秒")
            res = await send_rcon_command(SERVER_ADDRESS, SERVER_PORT, RCON_PASSWORD, "ShowPlayers", timeout=60)
            res[1] = res[1].replace("\x00\x00","")
            # 'name,playeruid,steamid\nスターズオンアース,604703510,\x00\x00'
            msg = res[1] if res[0] else "error: " + res[1]
        else:
            msg = decrypted[1]
    await bot.send(ev,msg)

@sv.on_fullmatch("帕鲁关服")
async def pal_server_shutdown(bot, ev):
    is_admin = hoshino.priv.check_priv(ev, hoshino.priv.ADMIN)
    if not is_admin:
        await bot.send("权限不足")
        return 
    gid = ev.group_id
    data = await read_config()
    group_server_data = data['groups'].get(gid)
    if group_server_data is None:
        msg = "群聊还未绑定帕鲁服务器，请发送“帕鲁rcon绑定”进一步了解。"
    else:
        SERVER_ADDRESS = group_server_data.get("server_address")
        SERVER_PORT = group_server_data.get("rcon_port")
        decrypted = await decrypt_admin_password(group_server_data.get("admin_password"))
        if decrypted[0]:
            RCON_PASSWORD = decrypted[2]
            res = await send_rcon_command(SERVER_ADDRESS, SERVER_PORT, RCON_PASSWORD, "Shutdown 10 Server_will_shutdown_in_10s.")
            msg = res[1] if res[0] else "error: " + res[1]
        else:
            msg = decrypted[1]
    await bot.send(ev,msg)

@sv.on_prefix("帕鲁广播")
async def pal_server_broadcast(bot, ev):
    # is_admin = hoshino.priv.check_priv(ev, hoshino.priv.DEFAULT)
    # if not is_admin:
    #     await bot.send("权限不足")
    #     return
    # 姑且允许所有人广播
    bc_message = str(ev.message).strip()
    uid = ev.user_id
    gid = ev.group_id
    data = await read_config()
    group_server_data = data['groups'].get(gid)
    if group_server_data is None:
        msg = "群聊还未绑定帕鲁服务器，请发送“帕鲁rcon绑定”进一步了解。"
    else:
        SERVER_ADDRESS = group_server_data.get("server_address")
        SERVER_PORT = group_server_data.get("rcon_port")
        decrypted = await decrypt_admin_password(group_server_data.get("admin_password"))
        if decrypted[0]:
            RCON_PASSWORD = decrypted[2]
            if any(ord(c) > 127 for c in bc_message):
                # 包含非ascii字符
                bc_message = ' '.join(word_list[0] for word_list in pinyin(bc_message, style=Style.TONE3, heteronym=False))
                await bot.send(ev, "广播内容包含游戏内无法显示的字符，已尝试将其中的汉字转换成拼音，其余文字无法处理，游戏内也无法正常显示。")
            # 空格等全部换成下划线
            trans_table = str.maketrans({' ': '_', '\t': '_', '\n': '_', '\r': '_', '\f': '_','，':',','。':'.','？':'?','！':'!'})
            bc_message_replaced = bc_message.translate(trans_table)
            # 游戏内广播不会自动换行，所以手动处理，每48个字符换一行
            bc_message_replaced = "-"*48 + f"broadcast_from_QQ:{uid}__"+bc_message_replaced
            msg = ""
            bc_msg_list = [bc_message_replaced[i:i+48] for i in range(0, len(bc_message_replaced), 48)]
            bc_msg_list.append("-"*48)
            for bc_msg in bc_msg_list:
                res = await send_rcon_command(SERVER_ADDRESS, SERVER_PORT, RCON_PASSWORD, f"Broadcast {bc_msg}")
                msg += res[1] if res[0] else "error: " + res[1] + "\n"
                await asleep(0.5)# 确保分段消息顺序
            msg = msg.strip()
        else:
            msg = decrypted[1]
    await bot.send(ev,msg)

@sv.on_prefix("帕鲁rcon")
async def pal_server_rcon(bot, ev):
    is_admin = hoshino.priv.check_priv(ev, hoshino.priv.DEFAULT)
    if not is_admin:
        await bot.send("权限不足")
        return
    cmd = str(ev.message).strip()
    gid = ev.group_id
    data = await read_config()
    group_server_data = data['groups'].get(gid)
    if group_server_data is None:
        msg = "群聊还未绑定帕鲁服务器，请发送“帕鲁rcon绑定”进一步了解。"
    else:
        SERVER_ADDRESS = group_server_data.get("server_address")
        SERVER_PORT = group_server_data.get("rcon_port")
        decrypted = await decrypt_admin_password(group_server_data.get("admin_password"))
        if decrypted[0]:
            RCON_PASSWORD = decrypted[2]
            res = await send_rcon_command(SERVER_ADDRESS, SERVER_PORT, RCON_PASSWORD, cmd)
            msg = res[1] if res[0] else "error: " + res[1]
        else:
            msg = decrypted[1]
    await bot.send(ev,msg)