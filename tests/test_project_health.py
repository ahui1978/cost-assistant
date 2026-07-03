import py_compile
import unittest

from fastapi.testclient import TestClient

import server


class ProjectHealthTests(unittest.TestCase):
    def test_root_serves_chat_page(self):
        client = TestClient(server.app)

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("造价智能助手", response.text)

    def test_pipeline_parser_script_compiles(self):
        py_compile.compile("assets/js/parse_pipeline.py", doraise=True)

    def test_custom_system_prompt_keeps_tool_instructions(self):
        messages = [{"role": "system", "content": "请用简洁中文回答。"}]

        prepared = server.prepare_messages(messages)

        self.assertEqual(prepared[0]["role"], "system")
        self.assertIn("请用简洁中文回答。", prepared[0]["content"])
        self.assertIn("query_pipeline_indicator", prepared[0]["content"])


if __name__ == "__main__":
    unittest.main()
