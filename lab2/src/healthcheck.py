"""Здоров'я контейнера для Docker HEALTHCHECK."""
import os
import urllib.request

if __name__=="__main__":
    port=os.getenv("PORT","8000")
    with urllib.request.urlopen("http://127.0.0.1:"+port+"/health", timeout=4) as response:
        assert response.status==200
