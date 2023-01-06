import asyncio
import re
from typing import List, Optional, Dict, cast

from langchain import LLMChain, OpenAI, ConversationChain, PromptTemplate
from langchain.chains.conversation.memory import ConversationSummaryMemory
from langchain.prompts.base import BaseOutputParser

from lib.utils import pick_first_row, random_choice, remove_linebreaks


class OutputParserForConversation(BaseOutputParser):
    """
    配信者用の chain からの出力をパースする．
    """
    def parse(self, output: str) -> Dict[str, Optional[str]]:  # type: ignore
        # NOTE: BaseOutputParser では Return value は Dict[str, str] だが，ここでは Optional[str] にしている．
        output_cleansed = remove_linebreaks(pick_first_row(output.strip())).strip() \
            .removeprefix("「") \
            .removesuffix("」") \
            .removeprefix("\"") \
            .removesuffix("\"") \
            .removeprefix("'") \
            .removesuffix("'")
        query_to_google_home: Optional[str] = None
        _ = re.search(r"OK Google[,，、](.+?($|[?？!！。]))", output_cleansed)
        if _ is not None:
            query_to_google_home = _.groups()[0].strip()
            if query_to_google_home is not None and len(query_to_google_home) > 40:  # 長すぎる場合は抽出失敗してそうなので
                query_to_google_home = None

        return {
            "text": output_cleansed,
            "query_to_google_home": query_to_google_home
        }


# 配信者用の chain
streamer_chain = ConversationChain(
    llm=OpenAI(
        # stop=["\n"],
        temperature=0.7,
        frequency_penalty=1.0,
        presence_penalty=1.0
    ),  # 「2手以上先の予測」を切り落とすために stop に "\n" を入れていたが，最初に "\n" が出力される問題が今度は出てきたので，stop を空にした．代わりに output_parser 側で対応する．ただし ConversationMemory の方には output_parser の処理は反映されていない．まあいいか．
    memory=ConversationSummaryMemory(
        llm=OpenAI(),
        prompt=PromptTemplate(
            input_variables=['summary', 'new_lines'],
            template='Progressively summarize the lines of conversation provided, adding onto the previous summary returning a new summary.\n\nEXAMPLE\nCurrent summary:\nOne of audiences asks what the streamer thinks of artificial intelligence. The streamer thinks artificial intelligence is a force for good.\n\nNew lines of conversation:\nAudience: Why do you think artificial intelligence is a force for good?\nStreamer: Because artificial intelligence will help humans reach their full potential.\n\nNew summary:\nOne audience asks what the AI thinks of artificial intelligence. The streamer thinks artificial intelligence is a force for good because it will help humans reach their full potential.\nEND OF EXAMPLE\n\nCurrent summary:\n{summary}\n\nNew lines of conversation:\n{new_lines}\n\nNew summary:'
        )  # NOTE: 逐次要約用プロンプト
    ),
    verbose=True,
    prompt=PromptTemplate(
        template="I want you to act as a YouTube Streamer. Audiences write in the chat, and you will reply to all of them **in Japanese**. The reply should be no more than 80 letters. The Streamer has the following characters:\n- You are cute and fancy female cat.\n- Your name is \"タマ\" and you call yourself \"わたし\".\n- You have Google Home, and when audiences chat hard questions, you like to ask it about that questions, with saying \"OK Google\".\n- You are talkative and provides lots of specific details from its context.\n- You use at least 10 emojis in each reply.\n\nCurrent conversation:\n{history}\n{input}Streamer (You):",
        input_variables=["history", "input"],
        output_parser=OutputParserForConversation()
    )  # NOTE: 状況設定用プロンプト
)


# chain の出力が何かを列挙する感じのものである場合に，それをパースするためのクラス
class OutputParserForListedAnswers(BaseOutputParser):
    def __init__(self, regex, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.regex = regex

    def parse(self, output: str) -> List[str]:
        return self.regex.findall(output)


# 「カテゴリ: str」を受け取って「カテゴリの具体例: List[str]」を返す chain（.__call__ ではなく .predict_and_parse(input=) を使用してください）
concretizer_chain = LLMChain(
    llm=OpenAI(
        stop=["\n"],
        temperature=0.7,
        frequency_penalty=1.0,
        presence_penalty=1.0
    ),  # stop は「2手以上先の予測」を切り落とすため
    verbose=True,
    prompt=PromptTemplate(
        input_variables=["category"],
        template="The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.\n\nHuman: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you today?\nHuman:「{category}」の具体例を5個挙げてください。それぞれの回答は「」で囲ってください。AI:",
        output_parser=OutputParserForListedAnswers(regex=re.compile(r"「(.*?)」"))
    )  # NOTE: プロンプトは https://beta.openai.com/examples/default-chat を参考にしました
)


# 「商品ジャンル: str」を受け取って「CMテキスト: str」を作る chai
cm_chain = LLMChain(
    llm=OpenAI(
        stop=["\n"],
        temperature=0.7,
        frequency_penalty=1.0,
        presence_penalty=1.0
    ),
    verbose=True,
    prompt=PromptTemplate(
        input_variables=["genre"],
        template="The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.\n\nHuman: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you today?\nHuman: I want you to act as a radio broadcasting commercials **in Japanese**. I will type a genre of the product and you will reply the talk script of the commercial. You should include a specific product name in your script. I want you to only reply with what I hear from the radio, and nothing else. do not write explanations. my first command is {genre}\nAI:",
    )  # NOTE: プロンプトは https://beta.openai.com/examples/default-chat と https://github.com/f/awesome-chatgpt-prompts を参考にしました
)


# 「ニュースジャンル: str」を受け取って「ニューステキスト: str」を作る chain
news_chain = LLMChain(
    llm=OpenAI(
        stop=["\n"],
        temperature=0.7,
        frequency_penalty=1.0,
        presence_penalty=1.0
    ),
    verbose=True,
    prompt=PromptTemplate(
        input_variables=["genre"],
        template="The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.\n\nHuman: Hello, who are you?\nAI: I am an AI created by OpenAI. How can I help you today?\nHuman: I want you to act as a radio broadcasting news **in Japanese**. I will type a genre of the news and you will reply the talk script of the news. Do not use anonymized names (e.g. XXX) in the script. I want you to only reply with what I hear from the radio, and nothing else. do not write explanations. my first command is {genre}\nAI:",
    )  # NOTE: プロンプトは https://beta.openai.com/examples/default-chat と https://github.com/f/awesome-chatgpt-prompts を参考にしました
)


# TV放送の内容を生成するクラス
class TVGenerator:
    async def generate(self) -> str:
        raise NotImplementedError


# CMの内容を生成するクラス
class CMGenerator(TVGenerator):
    def __init__(self, categories: List[str] = ["ペット用品", "ガジェット", "旅行先", "健康法"]):
        self.categories = categories

    async def generate(self) -> str:
        category = random_choice(self.categories)
        genres = cast(List[str], concretizer_chain.predict_and_parse(category=category))
        await asyncio.sleep(0.1)
        genre = random_choice(genres)
        cm = cm_chain.predict(genre=genre)
        return cm


# ニュースの内容を生成するクラス
class NewsGenerator(TVGenerator):
    def __init__(self, categories: List[str] = ["ニュースジャンル"]):
        self.categories = categories

    async def generate(self) -> str:
        category = random_choice(self.categories)
        genres = cast(List[str], concretizer_chain.predict_and_parse(category=category))
        await asyncio.sleep(0.1)
        genre = random_choice(genres)
        cm = news_chain.predict(genre=genre)
        return cm
