import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from probe_and_capture import parse_q_json


FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class QMetadataTests(unittest.TestCase):
    def test_a_answer(self):
        self.assertEqual(parse_q_json(load("q_a.json")), {
            "answer_count": "1", "cname_count": "0", "ttl_min": "300",
            "padding_present": "unknown",
        })

    def test_cname_chain(self):
        self.assertEqual(parse_q_json(load("q_cname_chain.json")), {
            "answer_count": "2", "cname_count": "1", "ttl_min": "120",
            "padding_present": "unknown",
        })

    def test_empty_answer(self):
        self.assertEqual(parse_q_json(load("q_empty.json")), {
            "answer_count": "0", "cname_count": "0", "ttl_min": "",
            "padding_present": "unknown",
        })

    def test_padding_is_detected_from_response(self):
        self.assertEqual(parse_q_json(load("q_opt_padding.json"))["padding_present"], "true")

    def test_numeric_type_and_duration_ttl(self):
        self.assertEqual(parse_q_json(load("q_numeric_duration.json")), {
            "answer_count": "1", "cname_count": "0", "ttl_min": "300",
            "padding_present": "unknown",
        })

    def test_q_minimum_ttl_fallback(self):
        self.assertEqual(parse_q_json(load("q_minttl.json"))["ttl_min"], "300")

    def test_q_entry_reply_header_schema(self):
        self.assertEqual(parse_q_json(load("q_entry_replies.json")), {
            "answer_count": "1", "cname_count": "0", "ttl_min": "300",
            "padding_present": "unknown",
        })
