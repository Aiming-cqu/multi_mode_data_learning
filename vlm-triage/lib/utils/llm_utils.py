#!/usr/bin/env -S pixi run -- test -s

from __future__ import absolute_import, annotations

import logging, typing as tp

from openai import AsyncOpenAI


logger: logging.Logger = logging.getLogger(name=__name__)


def make_text_content(text_prompt: str) -> tp.Mapping[str, tp.Any]:
    r"""
    Create a text content mapping for LLM messages.

    Args:
        text_prompt: The text content to be included in the message.

    Returns:
        A mapping with 'type' set to 'text' and 'text' containing the prompt.
    """
    return {"type": "text", "text": text_prompt}


def make_image_content(image_url: str, **url_kwds: tp.Any) -> tp.Mapping[str, tp.Any]:
    r"""
    Create an image content mapping for LLM messages.

    Args:
        image_url: The URL of the image to be included.
        **url_kwds: Additional keyword arguments to include in the image_url mapping.

    Returns:
        A mapping with 'type' set to 'image_url' and 'image_url' containing
        the URL and any additional parameters.
    """
    return {"type": "image_url", "image_url": {"url": image_url, **url_kwds}}


def make_video_content(video_path: str, **url_kwds: tp.Any) -> tp.Mapping[str, tp.Any]:
    r"""
    Create a video content mapping for LLM messages.

    Args:
        video_path: The path or URL of the video to be included.
        **url_kwds: Additional keyword arguments to include in the video_url mapping.

    Returns:
        A mapping with 'type' set to 'video_url' and 'video_url' containing
        the path and any additional parameters.
    """
    return {"type": "video_url", "video_url": {"url": video_path, **url_kwds}}


def make_message(
    content: tp.Union[str, tp.Sequence[tp.Mapping[str, tp.Any]]],
    role: str = "user",
) -> tp.Mapping[str, tp.Any]:
    r"""
    Create a message mapping for LLM chat completion.

    Args:
        content: The content of the message, either a string or a sequence
            of content mappings (e.g., from make_text_content, make_image_content).
        role: The role of the message sender. Defaults to 'user'.

    Returns:
        A mapping with 'role' and 'content' keys suitable for LLM API calls.
    """
    return {"role": role, "content": content}


async def select_model(client: AsyncOpenAI) -> str:
    r"""
    Select first available model from the client.

    Iterates through available models from the OpenAI client and returns
    the ID of the first model found.

    Args:
        client: An AsyncOpenAI client instance.

    Returns:
        The ID of the first available model.

    Raises:
        RuntimeError: If no models are available from the client.
    """
    async for model in client.models.list():
        logger.info('selected base_url=%r model_id=%r', client.base_url, model.id)
        return model.id
    raise RuntimeError(f'No model found, {client=}')


async def test_select_model():
    r"""
    Test function for select_model.

    Creates a local OpenAI provider and tests the select_model function.
    """
    try:
        import os

        from pydantic_ai.providers.openai import OpenAIProvider

        base_url = os.environ["TRIAGE_MODEL_ROUTER_URL"]
        provider = OpenAIProvider(base_url=base_url, api_key='REDACTED')

        model_id = await select_model(provider.client)
        print(f'HIL: check model_id: {model_id!r}')
    finally:
        if __name__ == '__main__': globals().update(locals())  # fmt: skip


if __name__ == '__main__':
    import logfire

    from conflog import configure_logging, configure_auto_tracing

    configure_logging(env="test")
    configure_auto_tracing(env="test")

    logfire.instrument_openai()
    logfire.instrument_pydantic_ai()

    import asyncio

    with asyncio.Runner(debug=True) as runner:
        print(runner.run(test_select_model()))
