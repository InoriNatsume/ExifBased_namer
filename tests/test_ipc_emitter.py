from tests import _bootstrap  # noqa: F401

import contextlib
import io
import json
import unittest

from sidecar.emitter import JsonEmitter


class IpcEmitterTests(unittest.TestCase):
    def test_emitter_injects_version(self) -> None:
        emitter = JsonEmitter(version=1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emitter.emit({"type": "log", "message": "hello"})
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload.get("version"), 1)

    def test_emitter_preserves_version(self) -> None:
        emitter = JsonEmitter(version=1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emitter.emit({"type": "log", "version": 9})
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload.get("version"), 9)


if __name__ == "__main__":
    unittest.main()
