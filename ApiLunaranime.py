#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Coded by aqil.almara - t.me/prudentscitus

# Imports
import json
import requests
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
from requests.exceptions import HTTPError, ConnectionError, ReadTimeout
try: from json.decoder import JSONDecodeError
except ImportError: JSONDecodeError = ValueError

class Unexpected(Exception):
    def __init__(self, message="Terjadi sesuatu yang tidak terduga"):
        self.message = message
        super().__init__(self.message)

def create_session():
    session = requests.Session()
    session.headers.update({
        'Host': 'api.lunaranime.ru',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'dnt': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'referer': 'https://lunaranime.ru/',
        'sec-ch-ua-platform': '"Android"',
        'sec-ch-ua-mobile': '?1',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'accept-language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
    })

    # Set cookies
    # session.cookies.set('on-boarding', 'true')
    # session.cookies.set('Authorization', 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMzVmMWFjMS00ZmQyLTQ2ODktODhjZi1mZWI0YzMxNWVmYjUiLCJleHAiOjE3NzU4NjI2OTQsImlhdCI6MTc3MzI3MDY5NCwicm9sZSI6InVzZXIifQ.nhhA_urTLhVnQwjNPLJxK-B28vXREq5Li3D1uz2zHrI')
    # session.cookies.set('selectedProvider', 'hentai')
    return session

# Penggunaan session
session = create_session()

def fetch(endponit, params=None, post=None, timeout=(10, 10)):
    url = endponit if endponit.startswith('http') else f'https://api.lunaranime.ru/api{endponit}'

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if post: response = session.post(url, json=post, timeout=timeout)
            else: response = session.get(url, params=params, timeout=timeout)

            if response.status_code == 200:
                try: return response.json()
                except JSONDecodeError: return response.text
                return {"raw": response.text}
            else: return {"error": f"HTTP {response.status_code}", "status": response.status_code}

        except (ConnectionError, ReadTimeout) as e:
            if attempt < max_retries - 1: time.sleep(2)
            else: raise Unexpected(f"Connection failed after {max_retries} attempts: {e}")
        except Exception as e: raise Unexpected(f"An unexpected error occurred: {e}")

    return {"error": "Max retries reached"}


def search_manga(query="webcomic", page=1, limit=30, sort="relevance"):
    params = {
        "query": query,
        "page": page,
        "limit": limit,
        "sort": sort
    }
    return fetch('/manga/search', params=params)

def parse_genres(genres_str: str) -> List[str]:
    """Parse string genres JSON menjadi list"""
    try: return json.loads(genres_str.replace("'", '"'))
    except: return []

def save_to_json(data: Dict[str, Any], filename: str = "manga_search.json"):
    """Simpan hasil ke file JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 Data disimpan ke {filename}")

def search_profile(username):
    params = {'username': username}
    resp = fetch('/animes/profile', params=params)
    return resp
    if  data := resp.get('data'):
        user_id = data.get('user_id')
        return data

    return resp.get('message')

def get_chapters(slug: str):
    resp = fetch(f'/manga/{slug}')
    # Path('chapters_data.json').write_text(
    #     json.dumps(resp, indent=4)
    # )
    results = {}
    for chapter in resp.get('data', []):
        lang = chapter['language']
        if not results.get(lang): results.update({lang: []})
        results[lang].append({
            'view_count': chapter['view_count'],
            'chapter_number': chapter['chapter_number'],
            'chapter_title': chapter['chapter_title']
        })

    resp['data'] = results
    return resp

def get_user_projects(user_id: str):
    resp = fetch(f'/user/{user_id}/projects')
    if projects:= resp.get('projects'):
        return projects

    return resp

def function(slug: str):
    resp = fetch(f'/manga/title/{slug}')
    return resp.get('manga')
