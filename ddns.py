from os import path
from sys import exc_info
from traceback import format_exception
from re import search as re_search
from time import strftime
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
try:
    from requests import post, get
    from requests.exceptions import ConnectionError
except ModuleNotFoundError:
    print("Required module not installed")
    exit(1)

# https://www.namesilo.com/account_api.php
NAMESILO_KEY = ""
TTL = 3600

# https://ifttt.com/maker_webhooks
IFTTT_EVENT = "YOUR_IFTTT_EVENT_NAME"
IFTTT_KEY = ""

BASE_URL = "https://www.namesilo.com/api/"
log_message = []

dnsListRecords = {
    "name": "dnsListRecords",
    "params": {
        "version": "1",
        "type": "xml",
        "key": NAMESILO_KEY,
        "domain": None
    }
}

dnsUpdateRecord = {
    "name": "dnsUpdateRecord",
    "params": {
        "version": "1",
        "type": "xml",
        "key": NAMESILO_KEY,
        "domain": None,
        "rrhost": None,
        "rrttl": TTL,
        "rrid": None,
        "rrvalue": None
    }
}

dnsAddRecord = {
    "name": "dnsAddRecord",
    "params": {
        "version": "1",
        "type": "xml",
        "key": NAMESILO_KEY,
        "domain": None,
        "rrtype": "A",
        "rrhost": None,
        "rrttl": TTL,
        "rrvalue": None
    }
}


def objectify(root):
    class Node(dict):
        __getattr__, __setattr__ = dict.get, dict.__setitem__
    ret = Node()
    for child in root:
        if len(child) == 0:
            ret[child.tag] = child.text.strip()
        else:
            if child.tag in ret:
                if type(ret[child.tag]) != list:
                    tmp = ret[child.tag]
                    ret[child.tag] = [tmp]
                ret[child.tag].append(objectify(child))
            else:
                ret[child.tag] = objectify(child)
    return ret


class FailedPostException(Exception):
    def __init__(self, rsp):
        super(FailedPostException, self).__init__()
        self.response = rsp

    @property
    def request(self):
        return self.response.request

    @property
    def reply(self):
        return self.response.reply

    @property
    def detail(self):
        return self.reply.detail


def webhooks():
    if not IFTTT_KEY:
        return
    try:
        r = post(
            "https://maker.ifttt.com/trigger/{0}/with/key/{1}".format(IFTTT_EVENT, IFTTT_KEY),
            json={"value1": "<br>".join(log_message)}
        )
        if r.status_code != 200:
            raise ValueError("Failed to connect to IFTTT with status code: {0}".format(r.status_code))
    except Exception as err:
        log(err)


def log(text, with_time=True):
    log_text = text.strip()
    if with_time:
        log_text = "{0} - {1}".format(strftime("%Y/%m/%d %H:%M:%S"), log_text)
    print(log_text)
    log_message.append(log_text)


def failed(message):
    if type(message) == list:
        log("Long message")
        for line in message:
            log(line, with_time=False)
    else:
        log(message)
    webhooks()
    exit(1)


def do_request(operation):
    r = get(BASE_URL + operation["name"], params=operation["params"])
    obj = objectify(ET.fromstring(r.text))
    if obj.reply.code != "300":
        raise FailedPostException(obj)
    return obj


def get_current_ip():
    error = None
    server_list = [
        "https://myip.ipip.net",
        "https://api.ipify.org",
        "https://checkip.amazonaws.com",
        "http://checkip.dyndns.com"
    ]
    for server in server_list:
        try:
            text = get(server).text.strip()
            ret = re_search(r'\d+\.\d+\.\d+\.\d+', text)
            if ret is None or not all([0 <= int(i) <= 255 for i in ret.group(0).split(".")]):
                raise ValueError(text)
            return ret.group(0)
        except (ConnectionError, ValueError) as err:
            error = err
    if error:
        raise ValueError(error)


def query_and_update(hosts, domain):
    current_ip = get_current_ip()
    log("Current IP={0}".format(current_ip))
    operation = dnsListRecords.copy()
    operation["params"]["domain"] = domain
    obj = do_request(operation)
    for host in hosts:
        a_record = None
        operation = None
        full_host = "{0}.{1}".format(host, domain) if host != "" else domain
        for rec in obj["reply"].resource_record:
            if rec.type == "A" and full_host == rec.host:
                a_record = rec
                break
        if a_record is None:
            log("No A record found for host: '{0}', creating a new A record.".format(full_host))
            operation = dnsAddRecord.copy()
            log("NEW: type={0}, host={1}, value={2}".format("A", full_host, current_ip))
        else:
            if current_ip != a_record.value:
                log("DDNS need to be updated.")
                operation = dnsUpdateRecord.copy()
                operation["params"]["rrid"] = a_record.record_id
                log("UPDATE: type={0}, host={1}, value={2}, old={3}".format(a_record.type, a_record.host, current_ip, a_record.value))
            else:
                log("DDNS is up to date.")
                log("CUR: type={0}, host={1}, value={2}".format(a_record.type, a_record.host, a_record.value))
        if operation != None:
            operation["params"]["rrvalue"] = current_ip
            operation["params"]["rrhost"] = host
            operation["params"]["domain"] = domain
            do_request(operation)


def main():
    log_message.append("-" * 40)
    # log("Init DDNS for host: '{0}'".format("{0}.{1}".format(HOST, DOMAIN) if HOST != "" else DOMAIN))
    try:
        hs = ["", "www"]
        dom = "domain.com"
        query_and_update(hs, dom)
    except FailedPostException as request_failed:
        failed("Failed to do a request with message: '{0}'".format(request_failed.detail))
    except ValueError as get_ip_failed:
        failed("Failed to get current IP with response: '{0}'".format(get_ip_failed))
    except Exception:
        etype, value, tb = exc_info()
        failed(format_exception(etype, value, tb))
    finally:
        with open(path.join(path.dirname(path.abspath(__file__)), "ddns.log"), "a+") as log_file:
            log_file.write("\n".join(log_message) + "\n")


if __name__ == "__main__":
    main()
