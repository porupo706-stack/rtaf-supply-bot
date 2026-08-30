import os
from notebooklm import NotebookLMClient


def setup_auth():

    auth_json = os.getenv(
        "NOTEBOOKLM_AUTH_JSON"
    )

    if not auth_json:
        return False

    return True


async def ask_notebook(
    notebook_id,
    prompt
):

    async with NotebookLMClient.from_storage() as client:

        result = await client.chat.ask(
            notebook_id,
            prompt
        )

        return result