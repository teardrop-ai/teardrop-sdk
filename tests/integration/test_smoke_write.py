"""Integration write+undo smoke tests.

Each test creates a resource, asserts the response shape, then deletes it in
a ``finally`` block to guarantee cleanup even when assertions fail.

Skipped automatically when integration env vars are not set.
"""

from __future__ import annotations

import uuid

import pytest

from teardrop.client import AsyncTeardropClient
from teardrop.exceptions import GatewayError, NotFoundError
from teardrop.models import (
    AddTrustedAgentRequest,
    AgentWalletResponse,
    CreateMcpServerRequest,
    CreateOrgToolRequest,
    DiscoverMcpToolsResponse,
    LlmConfigResponse,
    MemoryEntry,
    OrgMcpServer,
    OrgTool,
    StoreMemoryRequest,
    TrustedAgent,
    UpdateMcpServerRequest,
    UpdateOrgToolRequest,
)
from teardrop.models import (
    TestWebhookResponse as WebhookTestResponse,
)


class TestMemoryRoundTrip:
    async def test_create_and_delete_memory(self, async_client: AsyncTeardropClient) -> None:
        memory: MemoryEntry | None = None
        try:
            memory = await async_client.create_memory(
                StoreMemoryRequest(content="__smoke_test__ ok")
            )
            assert memory.id
            assert "__smoke_test__" in memory.content
        finally:
            if memory is not None:
                await async_client.delete_memory(memory.id)


class TestAgentWalletRoundTrip:
    async def test_provision_get_and_deactivate_agent_wallet(
        self, async_client: AsyncTeardropClient
    ) -> None:
        try:
            existing_wallet = await async_client.get_agent_wallet()
        except NotFoundError:
            existing_wallet = None

        if existing_wallet is not None:
            pytest.skip("Test account already has an agent wallet")

        wallet: AgentWalletResponse | None = None
        try:
            wallet = await async_client.provision_agent_wallet()
            assert wallet.id
            assert wallet.address
            assert wallet.is_active

            fetched = await async_client.get_agent_wallet(include_balance=True)
            assert fetched.id == wallet.id
            assert fetched.is_active
        finally:
            if wallet is not None:
                await async_client.deactivate_agent_wallet()


class TestTrustedAgentRoundTrip:
    async def test_add_list_and_remove_trusted_agent(
        self, async_client: AsyncTeardropClient
    ) -> None:
        trusted_agent: TrustedAgent | None = None
        agent_url = f"https://example.com/a2a-smoke-{uuid.uuid4().hex[:8]}"
        try:
            trusted_agent = await async_client.add_trusted_agent(
                AddTrustedAgentRequest(agent_url=agent_url, label="integration smoke test")
            )
            assert trusted_agent.id
            assert trusted_agent.agent_url == agent_url

            agents = await async_client.list_trusted_agents()
            assert any(agent.id == trusted_agent.id for agent in agents)
        finally:
            if trusted_agent is not None:
                await async_client.remove_trusted_agent(trusted_agent.id)


class TestLlmConfigRoundTrip:
    async def test_set_get_and_delete_llm_config(self, async_client: AsyncTeardropClient) -> None:
        try:
            existing_config = await async_client.get_llm_config()
        except NotFoundError:
            existing_config = None

        if existing_config is not None:
            pytest.skip("Test account already has an LLM config")

        config: LlmConfigResponse | None = None
        try:
            config = await async_client.set_llm_config(
                provider="anthropic",
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
            )
            assert config.provider == "anthropic"
            assert config.model == "claude-haiku-4-5-20251001"

            fetched = await async_client.get_llm_config()
            assert fetched.provider == config.provider
            assert fetched.model == config.model
        finally:
            if config is not None:
                await async_client.delete_llm_config()


class TestToolRoundTrip:
    async def test_create_and_delete_tool(self, async_client: AsyncTeardropClient) -> None:
        tool: OrgTool | None = None
        name = f"smoketool_{uuid.uuid4().hex[:8]}"
        try:
            tool = await async_client.create_tool(
                CreateOrgToolRequest(
                    name=name,
                    description="Smoke test tool — safe to delete",
                    input_schema={"type": "object", "properties": {}, "required": []},
                    webhook_url="https://example.com/smoke-tool",
                )
            )
            assert tool.id
            assert tool.name == name

            fetched = await async_client.get_tool(tool.id)
            assert fetched.id == tool.id
            assert fetched.name == name

            updated = await async_client.update_tool(
                tool.id,
                UpdateOrgToolRequest(description="Updated integration smoke tool"),
            )
            assert updated.description == "Updated integration smoke tool"

            webhook_result = await async_client.test_webhook(tool.id, {"source": "smoke"})
            assert isinstance(webhook_result, WebhookTestResponse)
        finally:
            if tool is not None:
                await async_client.delete_tool(tool.id)


class TestMcpServerRoundTrip:
    async def test_create_and_delete_mcp_server(self, async_client: AsyncTeardropClient) -> None:
        server: OrgMcpServer | None = None
        name = f"smokemcp_{uuid.uuid4().hex[:8]}"
        try:
            server = await async_client.create_mcp_server(
                CreateMcpServerRequest(
                    name=name,
                    url="https://example.com/smoke-mcp",
                )
            )
            assert server.id
            assert server.name == name

            fetched = await async_client.get_mcp_server(server.id)
            assert fetched.id == server.id
            assert fetched.name == name

            updated = await async_client.update_mcp_server(
                server.id,
                UpdateMcpServerRequest(timeout_seconds=20),
            )
            assert updated.timeout_seconds == 20

            try:
                discovery = await async_client.discover_mcp_server_tools(server.id)
            except GatewayError:
                pass
            else:
                assert isinstance(discovery, DiscoverMcpToolsResponse)
                assert discovery.server_id == server.id
        finally:
            if server is not None:
                await async_client.delete_mcp_server(server.id)
