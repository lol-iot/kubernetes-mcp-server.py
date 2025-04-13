from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from kubernetes import client, config
from mcp.server.fastmcp import Context, FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount


@dataclass
class AppContext:
    k8s_contexts: list[dict]


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    # Initialize on startup
    contexts, _ = config.list_kube_config_contexts()

    yield AppContext(k8s_contexts=contexts)


mcp = FastMCP("kubernetes", lifespan=lifespan)


@mcp.tool()
def list_contexts(ctx: Context) -> list[str]:
    """
    List all available kubeconfig contexts.
    """
    k8s_contexts = ctx.request_context.lifespan_context.k8s_contexts

    return [context["name"] for context in k8s_contexts]


@mcp.tool()
def list_pods(ctx: Context, context: str = "", namespace: str = "default") -> list[str]:
    """
    List all pods in the specified context and namespace.
    """
    if context:
        api_client = config.new_client_from_config(context=context)
    else:
        api_client = config.new_client_from_config()

    v1 = client.CoreV1Api(api_client=api_client)

    pods = v1.list_namespaced_pod(namespace)

    return pods


app = Starlette(
    routes=[
        Mount("/", app=mcp.sse_app()),
    ]
)
