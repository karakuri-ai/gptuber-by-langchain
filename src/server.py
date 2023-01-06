"""
バックエンドサーバー
ブレインを動かしつつ，フロントエンドとソケット通信を行います．
"""
import asyncio
import json
from typing import Dict, List, Optional, cast
import argparse

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.typing import Data

from agent import execute_agent_mock, execute_agent_with_subprocess
from lib.gptuber import Action, GPTuber
from lib.chains import TVGenerator, streamer_chain
from lib.utils import random_choice
from lib.youtube import ChatLog, ChatMonitor, MockChatMonitor
from lib.chains import NewsGenerator, CMGenerator


class Server:
    def __init__(self):
        self.web_socket: Optional[WebSocketServerProtocol] = None
        self.chat_list: List[ChatLog] = []

    async def on_message(self, websocket: WebSocketServerProtocol, path: str):

        self.web_socket = websocket
        while True:
            # クライアントからのメッセージを受信
            message = await self.web_socket.recv()
            print(f"Received message: {message!r}") 
            obj = json.loads(message)
            if obj["type"] == "chat":
                self.chat_list.append(ChatLog(name="", message=obj["message"]))

    async def main(self):
        async with websockets.serve(self.on_message, "localhost", 8080):
            await asyncio.Future()  # run forever

    def send_message(self, message: Data):
        if self.web_socket is not None:
            asyncio.create_task(self.web_socket.send(message))

    def get_recent_chats(self) -> List[ChatLog]:
        """
        チャット（差分のみ）を返す．
        """
        chat_list = self.chat_list
        self.chat_list = []
        return chat_list


async def run(
    youtube_url: Optional[str] = None,
    no_llm: bool = False,
    no_neural_tts: bool = False,
    no_smart_agent: bool = False
):
    def _fn_streamer_llm(query: str) -> Action:
        pred_raw = cast(Dict[str, str], streamer_chain.predict_and_parse(input=query))
        return Action(**pred_raw)

    def _fn_streamer_llm_mock(query: str) -> Action:
        return Action(text="こんにちは。今日はいい天気ですね。")

    chat_monitor = ChatMonitor(youtube_url) if youtube_url is not None else MockChatMonitor()

    def _fn_get_recent_chats() -> List[ChatLog]:
        chats_from_youtube = chat_monitor.get_recent_chats()
        chats_from_local = server.get_recent_chats()
        return chats_from_youtube + chats_from_local

    async def _fn_distract() -> str:
        generators: List[TVGenerator] = [
            NewsGenerator(),
            CMGenerator()
        ]
        return await random_choice(generators).generate()

    async def _fn_distract_mock() -> str:
        return "テスト放送中"

    server = Server()
    gptuber = GPTuber(
        _fn_streamer_llm_mock if no_llm else _fn_streamer_llm,
        fn_get_recent_chats=_fn_get_recent_chats,
        fn_distract=_fn_distract_mock if no_llm else _fn_distract,
        fn_send_message=server.send_message,
        fn_smart_agent=execute_agent_mock if no_smart_agent else execute_agent_with_subprocess,
        no_neural_tts=no_neural_tts
    )
    await asyncio.gather(
        server.main(),
        gptuber.main_loop(),
        gptuber.main_loop2()
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--youtube-url", type=str, help="YouTube Live URL, where the chat is monitored.")
    parser.add_argument("--no-llm", action="store_true", help="Don't use LLM.")
    parser.add_argument("--no-neural-tts", action="store_true", help="Don't use Neural TTS.")
    parser.add_argument("--no-smart-agent", action="store_true", help="Don't use Smart Agent.")
    args = parser.parse_args()

    asyncio.run(run(
        youtube_url=args.youtube_url,
        no_llm=args.no_llm,
        no_neural_tts=args.no_neural_tts,
        no_smart_agent=args.no_smart_agent
    ))
