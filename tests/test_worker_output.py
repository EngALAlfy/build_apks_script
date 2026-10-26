"""Regression coverage for frozen/redirected Windows console encodings."""
import io
import os
import unittest
from unittest.mock import patch
from server.worker import RedactingOutput


class WorkerOutputTests(unittest.TestCase):
    def test_windows_codepage_is_reconfigured_to_utf8(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding='cp1252', errors='strict')
        writer = RedactingOutput(stream)
        text = '\u221a Built app-debug.apk / \u2713 / العربية / \U0001f680\n'
        self.assertEqual(writer.write(text), len(text))
        writer.flush()
        self.assertEqual(buffer.getvalue().decode('utf-8').replace('\r\n', '\n'), text)
        self.assertEqual(stream.encoding, 'utf-8')
        stream.close()

    def test_redaction_and_ansi_cleanup_preserve_unicode(self):
        stream = io.StringIO()
        with patch.dict(os.environ, SLACK_WEBHOOK='private-webhook'):
            writer = RedactingOutput(stream)
            writer.write('\x1b[32m\u221a Built\x1b[0m private-webhook\n')
        self.assertEqual(stream.getvalue(), '\u221a Built [redacted]\n')

    def test_invalid_surrogate_cannot_crash_logging(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding='cp1252')
        writer = RedactingOutput(stream)
        writer.write('output: \ud800')
        self.assertIn(b'\\ud800', buffer.getvalue())
        stream.close()


if __name__ == '__main__':
    unittest.main()
