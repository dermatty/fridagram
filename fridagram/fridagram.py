from threading import Thread
import configparser
import logging
import logging.handlers
from os.path import expanduser
from dataclasses import dataclass
import inspect
from setproctitle import setproctitle
import json
import os
import requests
import time
import sys

__version__ = "0.1.5"
motd = "fridagram " + __version__ + " started!\nExit with /exit"


def whoami():
    outer_func_name = str(inspect.getouterframes(inspect.currentframe())[1].function)
    outer_func_linenr = str(inspect.currentframe().f_back.f_lineno)
    return outer_func_name + " / #" + outer_func_linenr + ": "


class EchoThread(Thread):
    def __init__(self, token, logger):
        Thread.__init__(self)
        self.token = token
        self.running = False
        self.logger = logger
        self.stopped = False

    def stop(self):
        self.running = False
        while not self.stopped:
            time.sleep(0.05)

    def run(self):
        self.logger.info("Sending first getme - heartbeat to bot ...")
        heartbeat_answer = get_me(self.token)
        if not heartbeat_answer:
            self.logger.error("Received no answer on first getme, exiting ...")
            self.running = False
        else:
            self.logger.info("Received answer on first getme: " + str(heartbeat_answer))
            self.running = True
            lastt0 = time.time()
            while self.running:
                ok, rlist = receive_message(self.token)
                if ok and rlist:
                    for chat_id, text in rlist:
                        if text == "/exit":
                            self.running = False
                            answer = "You write 'exit', therefore exiting ..."
                        else:
                            answer = "You wrote : " + text
                        send_message(self.token, [chat_id], answer)
                elif time.time() - lastt0 > 15:
                    self.logger.info("Sending getme - heartbeat to bot ...")
                    heartbeat_answer = get_me(self.token)
                    if not heartbeat_answer:
                        self.logger.error("Received no answer on getme, exiting ...")
                        self.running = False
                    else:
                        self.logger.info(
                            "Received answer on getme: " + str(heartbeat_answer)
                        )
                        lastt0 = time.time()  #
                time.sleep(0.1)
        self.stopped = True


@dataclass
class Cfg:
    token: str
    chatids: list[str]


def read_config(cfg_file, logger):
    try:
        cfg = configparser.ConfigParser()
        cfg.read(cfg_file)
        token = cfg["TELEGRAM"]["token"]
        chatids_values = cfg["TELEGRAM"]["chatids"]
        chatids = json.loads(chatids_values)
        return True, Cfg(token, chatids)
    except Exception as e:
        return False, whoami() + str(e)


def get_updates(token, offset=0):
    try:
        if int(offset) != 0:
            urlstr = (
                f"https://api.telegram.org/bot{token}/getUpdates?offset={str(offset)}"
            )
            answer = requests.get(urlstr)
            print(answer)
        else:
            urlstr = f"https://api.telegram.org/bot{token}/getUpdates"
            answer = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
    except Exception as e:
        return {"ok": False, "result": []}
    return json.loads(answer.content)


def get_me(token):
    try:
        answer = requests.get(f"https://api.telegram.org/bot{token}/getme")
        return answer
    except Exception:
        return None


def receive_message(token, timeout=45):
    try:
        answer = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates?timeout={timeout}"
        )
        r = json.loads(answer.content)
        if r["ok"] and r["result"]:
            rlist = [
                (r0["message"]["chat"]["id"], r0["message"]["text"])
                for r0 in r["result"]
            ]
            offset = int(r["result"][-1]["update_id"] + 1)
            urlstr = (
                f"https://api.telegram.org/bot{token}/getUpdates?offset={str(offset)}"
            )
            _ = requests.get(urlstr)
            return True, rlist, ""
        elif r["ok"] and not r["result"]:
            return True, [], ""
        else:
            return False, [], ""
    except Exception as e:
        return False, [], str(e)


def send_filepath_as_photo(token, chatids, photo_path, photo_caption):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    resultlist = []
    for c in chatids:
        params = {"chat_id": c, "caption": photo_caption}
        try:
            file_opened = open(photo_path, "rb")
            file0 = {"photo": file_opened}
            message = requests.post(url, params, files=file0)
            file_opened.close()
            resultlist.append((True, json.loads(message.content)))
        except Exception as e:
            resultlist.append((False, {"ok": False, "result": str(e)}))
    return resultlist

def send_url_as_photo(token, chatids, photo_url, photo_caption):
    """r = send_url_as_photo(self.token, [chat_id],
    "https://url/file.jpg",
    "test")"""
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    resultlist = []
    for c in chatids:
        payload = {"chat_id": c, "photo": photo_url, "caption": photo_caption}
        try:
            message = requests.post(url, json=payload)
        except Exception:
            return False, {"ok": False, "result": []}
        resultlist.append(json.loads(message.content))
    return True, resultlist


def send_message(token, chatids, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resultlist = []
    for c in chatids:
        params = {"chat_id": str(c), "text": text}
        try:
            message = requests.post(url, params=params)
        except Exception:
            return False, {"ok": False, "result": []}
        resultlist.append(json.loads(message.content))
    return True, resultlist


def clear_bot(token):
    r = get_updates(token, offset=-1)
    if not r["ok"]:
        return False
    if not r["result"]:
        # if results empty but ok, return True / cleared!
        return True
    try:
        rlast = int(r["result"][-1]["update_id"] + 1)
        r = get_updates(token, offset=int(rlast))
        return r
    except Exception:
        return False



def start():
    setproctitle("drifg." + os.path.basename(__file__))

    userhome = expanduser("~")
    maindir = userhome + "/.fridagram/"

    # Init Logger
    logger = logging.getLogger("dh")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(maindir + "fridagram.log", mode="w")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info(whoami() + motd)

    try:
        cfg_file = maindir + "config"
        ret, cfg0 = read_config(cfg_file, logger)
        if not ret:
            raise Exception(cfg0)
    except Exception as e:
        logger.error(whoami() + str(e))
        sys.exit()

    r, ok = send_message(cfg0.token, cfg0.chatids, motd)

    echobot = EchoThread(cfg0.token, logger)
    echobot.start()

    while echobot.running:
        time.sleep(0.05)

    echobot.join()
