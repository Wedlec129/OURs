import asyncio
import json
from asyncio import gather, Semaphore
from getmac import get_mac_address
from ipaddress import ip_network
from icmplib import async_ping
from base64 import b32encode
from json import loads
from socket import gethostbyaddr
from lib.config_reader import threads_count, ouifile_path
from lib.progress_bar import ScanState

# -----------vendors_list
filename_path = ouifile_path
vendors_json = loads(open(filename_path, 'r', encoding="utf-8", errors="replace").read())
# -----------

SEMAPHORE_LIMIT = threads_count
semaphore = Semaphore(SEMAPHORE_LIMIT)
   
scan_state_scan = ScanState()

# Путь к JSON-файлу для хранения результатов
DB_FILE = "scan_results.json"

# Функция для загрузки текущей базы
def load_db():
	try:
		with open(DB_FILE, 'r', encoding='utf-8') as f:
			return json.load(f)
	except FileNotFoundError:
		return {"hosts": {}}
	except json.JSONDecodeError:
		return {"hosts": {}}

# Функция для сохранения базы
def save_db(data):
	with open(DB_FILE, 'w', encoding='utf-8') as f:
		json.dump(data, f, indent=2, ensure_ascii=False)

async def scan_ip(ip: str):
	async with semaphore:
		try:
			result = await async_ping(str(ip), count=2, interval=0.5, timeout=0.1)
			if result.is_alive:
				try:
					mac = get_mac_address(ip=str(ip), network_request=True)
					vendor = find_vendor(mac)
					scan_state_scan.next()
					return ip, result.is_alive, mac, vendor
				except Exception as e:
					scan_state_scan.next()
					return ip, result.is_alive, None, None
			else:
				scan_state_scan.next()
				return ip, False, None, None
		except Exception as e:
			scan_state_scan.next()
			return ip, False, None, None

async def start_scan(range_ip: str):
	scan_state_scan.total = addr_count(range_ip.split('/')[1])
	scan_state_scan.is_scanning = True
	scan_state_scan.progress = 0   
	ip_list = network_list(range_ip)
	tasks = [scan_ip(str(ip)) for ip in ip_list]  
	results = []
	for i in range(0, len(tasks), SEMAPHORE_LIMIT):
		batch = tasks[i:i + SEMAPHORE_LIMIT]
		results.extend(await gather(*batch))
	scan_state_scan.is_scanning = False
	scan_state_scan.procent = None

	# Обновляем JSON-базу
	db_data = load_db()
	for address, status, mac, vendor in results:
		address = str(address)
		if status:
			host_data = {
				"id": b32encode(address.encode()).decode(),
				"ip": address,
				"mac": mac,
				"hostname": get_hostname(address),
				"vendor": vendor,
				"ports": []  # Пустой список для данных Nmap
			}
			db_data["hosts"][address] = host_data
	save_db(db_data)
	
	return results

def get_hostname(ip):
	try:
		hostname = gethostbyaddr(ip)[0]
	except:
		hostname = None
	return hostname

def addr_count(mask_cidr: str):
	return 2**(32-int(mask_cidr))-2

def network_list(ip_range: str):
	network = ip_network(ip_range, strict=False)
	return network.hosts()

def create_json(array):
	data_list = []
	for address, status, mac, vendor in array:
		address = str(address)
		if status:
			data = {
				"id": b32encode(address.encode()).decode(),
				"ip": address,
				"mac": mac,
				"hostname": get_hostname(address),
				"vendor": vendor
			}
			data_list.append(data)
	return data_list

def find_vendor(mac):
	if mac is not None:
		mac = ("".join(mac.split(":")[:3])).upper()
		try:
			return vendors_json[mac]
		except Exception:
			return None
	return None