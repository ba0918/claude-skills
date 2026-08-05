"""Smoke tests for ollama_executor.sh against a fake /api/chat server.

The wrapper is the only piece of the process path that talks to a live LLM
service, so these tests stand up an in-process HTTP server and script its
responses per call. What they pin down is the two-call contract from
skills/skill-regression/references/process-queue.md § Text-only backends:
call 1 produces the deliverable itself (saved as artifact.md, the re-judge
counterpart), call 2 continues the conversation and produces the report JSON.
"""
import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "ollama_executor.sh")


def ok_response(content, done_reason="stop"):
    return {"message": {"role": "assistant", "content": content},
            "done": True, "done_reason": done_reason}


REPORT_JSON = json.dumps({"requirements": [
    {"index": 1, "verdict": "yes", "evidence": "did the thing"}]})


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        server = self.server
        body = self.rfile.read(int(self.headers["Content-Length"]))
        server.requests.append(json.loads(body))
        if len(server.responses) > len(server.requests) - 1:
            scripted = server.responses[len(server.requests) - 1]
        else:
            scripted = b'{"error": "fake server ran out of scripted responses"}'
        if isinstance(scripted, dict):
            scripted = json.dumps(scripted).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(scripted)))
        self.end_headers()
        self.wfile.write(scripted)

    def log_message(self, *args):
        pass


class ExecutorHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.output_file = os.path.join(self.tmp, "unit", "report.json")
        os.makedirs(os.path.dirname(self.output_file))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.requests = []
        self.server.responses = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    @property
    def artifact_file(self):
        return os.path.join(os.path.dirname(self.output_file), "artifact.md")

    def run_script(self, prompt="## Situation\n\nExplain the failure.\n"):
        env = dict(os.environ)
        env.update({
            "OLLAMA_MODEL": "fake-model",
            "OUTPUT_FILE": self.output_file,
            "OLLAMA_HOST": "http://127.0.0.1:%d" % self.server.server_address[1],
            "OLLAMA_MAX_TIME": "5",
        })
        return subprocess.run(["bash", SCRIPT], input=prompt, env=env,
                              capture_output=True, text=True)

    def read(self, path):
        with open(path) as handle:
            return handle.read()


class TestTwoCallProtocol(ExecutorHarness):
    def test_saves_the_deliverable_then_writes_the_report(self):
        self.server.responses = [ok_response("THE DELIVERABLE BODY"),
                                 ok_response(REPORT_JSON)]
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.server.requests), 2)
        self.assertEqual(self.read(self.artifact_file), "THE DELIVERABLE BODY")
        self.assertEqual(self.read(self.output_file), REPORT_JSON)

    def test_call_one_asks_for_the_deliverable_not_the_report(self):
        self.server.responses = [ok_response("body"), ok_response(REPORT_JSON)]
        self.run_script(prompt="THE PROMPT\n")
        first = self.server.requests[0]["messages"]
        self.assertEqual([m["role"] for m in first], ["user"])
        self.assertTrue(first[0]["content"].startswith("THE PROMPT"))
        self.assertIn("call 1 of 2", first[0]["content"])
        self.assertIn("report JSON", first[0]["content"])

    def test_call_two_continues_the_conversation_with_the_saved_deliverable(self):
        """Self-assessment must be grounded in the artifact that was actually
        saved — the assistant turn carries the exact text artifact.md holds."""
        self.server.responses = [ok_response("body of the deliverable"),
                                 ok_response(REPORT_JSON)]
        self.run_script()
        first = self.server.requests[0]["messages"]
        second = self.server.requests[1]["messages"]
        self.assertEqual([m["role"] for m in second],
                         ["user", "assistant", "user"])
        self.assertEqual(second[0], first[0])
        self.assertEqual(second[1]["content"], "body of the deliverable")
        self.assertIn("call 2 of 2", second[2]["content"])
        self.assertIn("only", second[2]["content"])

    def test_strips_closed_think_blocks_in_both_calls(self):
        self.server.responses = [
            ok_response("<think>hm</think>clean body"),
            ok_response("<think>hm</think>" + REPORT_JSON)]
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read(self.artifact_file), "clean body")
        # The continued conversation carries the stripped text, matching the file.
        self.assertEqual(self.server.requests[1]["messages"][1]["content"],
                         "clean body")
        self.assertEqual(self.read(self.output_file), REPORT_JSON)


class TestFailureModes(ExecutorHarness):
    def assert_failed(self, result, fragment):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(fragment, result.stderr)
        self.assertFalse(os.path.exists(self.output_file),
                         "a failed run must not leave a report file")

    def test_a_failed_first_call_never_reaches_call_two(self):
        self.server.responses = [ok_response("<think>cut mid-thought")]
        result = self.run_script()
        self.assert_failed(result, "unclosed <think>")
        self.assertEqual(len(self.server.requests), 1)
        self.assertFalse(os.path.exists(self.artifact_file),
                         "a truncated deliverable must not be saved as the artifact")

    def test_truncation_in_call_two_fails_the_unit(self):
        self.server.responses = [ok_response("body"),
                                 ok_response(REPORT_JSON, done_reason="length")]
        result = self.run_script()
        self.assert_failed(result, "num_predict cap")
        self.assertEqual(len(self.server.requests), 2)

    def test_empty_completion_fails(self):
        self.server.responses = [ok_response("   ")]
        self.assert_failed(self.run_script(), "empty completion")

    def test_server_error_field_is_reported(self):
        self.server.responses = [{"error": "model 'fake-model' not found"}]
        self.assert_failed(self.run_script(), "model 'fake-model' not found")

    def test_non_json_response_is_reported(self):
        self.server.responses = [b"<html>proxy in the way</html>"]
        self.assert_failed(self.run_script(), "not JSON")

    def test_empty_prompt_fails_before_any_request(self):
        result = self.run_script(prompt="")
        self.assert_failed(result, "empty prompt")
        self.assertEqual(len(self.server.requests), 0)


if __name__ == "__main__":
    unittest.main()
