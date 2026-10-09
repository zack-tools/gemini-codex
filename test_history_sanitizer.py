#!/usr/bin/env python3
import base64
import json
import unittest
from history_sanitizer import sanitize_json, sanitize_compaction_item


class TestHistorySanitizer(unittest.TestCase):
    def test_ccswitch_compaction_conversion(self):
        original_summary = "## Context Checkpoint Handoff Summary\nTesting compaction restore."
        b64 = base64.b64encode(original_summary.encode("utf-8")).decode("utf-8")
        item = {
            "type": "compaction",
            "id": "cmp_12345",
            "encrypted_content": f"ccswitch-compaction-v1:{b64}",
            "internal_chat_message_metadata_passthrough": {"turn_id": "turn_abc"}
        }
        cleaned, changed = sanitize_compaction_item(item)
        self.assertTrue(changed)
        self.assertEqual(cleaned["type"], "message")
        self.assertEqual(cleaned["role"], "assistant")
        self.assertEqual(cleaned["content"][0]["text"], original_summary)
        self.assertNotIn("encrypted_content", cleaned)

    def test_gAAAAAB_compaction_conversion(self):
        item = {
            "type": "compaction",
            "id": "cmp_67890",
            "encrypted_content": "gAAAAABqyEt8sWqeN_dpMTiQHLbk7tQ13q7RT0zj",
            "internal_chat_message_metadata_passthrough": {"turn_id": "turn_xyz"}
        }
        cleaned, changed = sanitize_compaction_item(item)
        self.assertTrue(changed)
        self.assertEqual(cleaned["type"], "message")
        self.assertEqual(cleaned["role"], "assistant")
        self.assertIn("Prior conversation context compacted", cleaned["content"][0]["text"])

    def test_cpa_ag_compact_preserved(self):
        item = {
            "type": "compaction",
            "id": "cmp_native",
            "encrypted_content": "cpa-ag-compact-v1:resp_ag_compact_12345",
        }
        cleaned, changed = sanitize_compaction_item(item)
        self.assertFalse(changed)
        self.assertEqual(cleaned["type"], "compaction")

    def test_carrier_fields_stripped(self):
        item = {
            "type": "reasoning",
            "id": "rs_123",
            "encrypted_content": "cpa-gemini-responses-carrier-v1:next:text:abcd",
            "thought_signature": "rs_resp_req_vrtx_12345",
            "other_field": "keep_me"
        }
        cleaned, changed = sanitize_json(item)
        self.assertTrue(changed)
        self.assertNotIn("encrypted_content", cleaned)
        self.assertNotIn("thought_signature", cleaned)
        self.assertEqual(cleaned["other_field"], "keep_me")


    def test_heavy_image_stripped(self):
        item = {
            "type": "input_image",
            "image_url": "data:image/png;base64," + "X" * 2000
        }
        cleaned, changed = sanitize_json(item)
        self.assertTrue(changed)
        self.assertEqual(cleaned["type"], "input_text")
        self.assertIn("Historical image attachment omitted", cleaned["text"])

if __name__ == "__main__":
    unittest.main()
