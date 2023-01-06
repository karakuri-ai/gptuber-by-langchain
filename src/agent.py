import argparse
import asyncio
import subprocess
import time
from typing import Awaitable, Callable, Optional
from typing_extensions import Protocol

from langchain.agents import load_tools
from langchain.agents import initialize_agent
from langchain.llms import OpenAI

from lib.utils import remove_control_characters


class FnSmartAgent(Protocol):
    def __call__(self, query: str, fn_report: Optional[Callable[[str], None]] = None) -> Awaitable[None]:
        ...


async def execute_agent_with_subprocess(query: str, fn_report: Optional[Callable[[str], None]] = None) -> None:
    proc = subprocess.Popen(
        ["python", "-u", "./agent.py", query],
        stdout=subprocess.PIPE,
        text=True
    )
    t0 = time.time()
    while True:
        if proc.stdout is None:
            break
        line = proc.stdout.readline()
        if line == "" and proc.poll() is not None:
            break
        if line:
            if fn_report is not None:
                fn_report(remove_control_characters(line))
        elapsed = time.time() - t0
        if elapsed > 80:
            # 80 秒以上かかっている場合は，強制終了する．
            proc.kill()
            break
        await asyncio.sleep(0.1)


async def execute_agent_mock(
    query: str,
    fn_report: Optional[Callable[[str], None]] = None
) -> None:
    await asyncio.sleep(3)
    if fn_report is not None:
        fn_report("> Final Answer: Sorry I don't understand.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("QUERY", type=str, help="Query to be answered.")
    args = parser.parse_args()

    llm = OpenAI(temperature=0)
    tools = load_tools(["serpapi", "llm-math"], llm=llm)
    agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)

    agent.run(args.QUERY)
