"""
REF: https://qiita.com/iroiro_bot/items/ad0f3901a2336fe48e8f
"""
import os
from typing import List, Optional, Tuple

import requests
from pydantic import BaseModel

# 事前に取得したYouTube API key
YT_API_KEY = os.getenv("YOUTUBE_API_KEY")


def get_chat_id(yt_url: str) -> Optional[str]:
    '''
    https://developers.google.com/youtube/v3/docs/videos/list?hl=ja
    '''
    video_id = yt_url.replace('https://www.youtube.com/watch?v=', '')
    print('video_id : ', video_id)

    url = 'https://www.googleapis.com/youtube/v3/videos'
    params = {'key': YT_API_KEY, 'id': video_id, 'part': 'liveStreamingDetails'}
    data = requests.get(url, params=params).json()

    if data.get("status", "") == "PERMISSION_DENIED":
        raise RuntimeError("YouTube API failed due to permission denied.")

    live_streaming_details = data['items'][0]['liveStreamingDetails']
    if 'activeLiveChatId' in live_streaming_details.keys():
        chat_id = live_streaming_details['activeLiveChatId']
        print('get_chat_id done!')
    else:
        chat_id = None
        print('NOT live')

    return chat_id


class ChatLog(BaseModel):
    name: str
    message: str


def get_chat(chat_id: str, page_token: Optional[str]) -> Tuple[List[ChatLog], str]:
    '''
    https://developers.google.com/youtube/v3/live/docs/liveChatMessages/list
    '''
    url = 'https://www.googleapis.com/youtube/v3/liveChat/messages'
    params = {'key': YT_API_KEY, 'liveChatId': chat_id, 'part': 'id,snippet,authorDetails'}
    if type(page_token) == str:
        params['pageToken'] = page_token

    data = requests.get(url, params=params).json()

    chat_logs: List[ChatLog] = []
    try:
        chat_logs = [ChatLog(
            name=item['authorDetails']['displayName'],
            message=item['snippet']['displayMessage']
        ) for item in data['items']]
        # print("start : ", data['items'][0]['snippet']['publishedAt'])
        # print("end   : ", data['items'][-1]['snippet']['publishedAt'])
    except Exception:
        pass

    return chat_logs, data.get('nextPageToken', None)


class ChatMonitor:
    def __init__(self, youtube_url: str):
        self.youtube_url = youtube_url
        chat_id = get_chat_id(youtube_url)
        if chat_id is None:
            raise ValueError("Not Live")
        self.chat_id = chat_id
        self.next_page_token: Optional[str] = None

    def get_recent_chats(self) -> List[ChatLog]:
        """
        最新のチャットの一覧を取得する（前回実行時から差分のみ）
        """
        chat_logs, self.next_page_token = get_chat(
            self.chat_id,
            self.next_page_token
        )
        return chat_logs


class MockChatMonitor(ChatMonitor):
    def __init__(self):
        pass

    def get_recent_chats(self) -> List[ChatLog]:
        # return [ChatLog(name="test", message="わーい")]
        return []
