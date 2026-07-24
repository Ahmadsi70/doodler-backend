import requests
with open("runpod_backend/server.py", "r", encoding="utf-8") as f:
    code = f.read()
url = "https://p7q35voyphx937-8000.proxy.runpod.net/update_code"
r = requests.post(url, json={"code": code})
print(r.text)
