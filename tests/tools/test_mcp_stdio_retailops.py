from __future__ import annotations

import unittest


class TestMcpStdioRetailops(unittest.TestCase):
    def test_registered_tool_names(self) -> None:
        from app.tools import mcp_stdio_retailops

        tools = mcp_stdio_retailops.mcp._tool_manager.list_tools()
        names = {t.name for t in tools}
        self.assertEqual(
            names,
            {
                "create_purchase_order",
                "submit_approval_request",
                "get_order_status",
                "check_tool_api_health",
            },
        )


if __name__ == "__main__":
    unittest.main()
