"""The README's example handler runs as documented."""

import re
from pathlib import Path

import httpx

from tests.test_worker import Harness


def readme_example() -> dict:
    text = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    code = re.search(r"```python\n(.*?)```", text, re.S).group(1)
    namespace: dict = {"__name__": "readme"}
    exec(code, namespace)
    return namespace


async def test_readme_example_handler():
    invert = readme_example()["invert"]
    async with Harness() as h:
        h.mock.get("/api/files/abc").mock(return_value=httpx.Response(200, content=bytes([0, 1, 255])))
        worker = h.worker(invert)
        await worker.start()
        job_id = await h.dispatch({"file": "abc"})
        await h.wait_for(job_id, "succeeded")
        missing = await h.dispatch({})
        await h.wait_for(missing, "failed")
        await worker.close()
        assert h.types(job_id) == ["started", "progress", "succeeded"]
        upload = [c for c in h.mock.calls if c.request.url.path == "/worker/files"][0]
        assert bytes([255, 254, 0]) in upload.request.content
