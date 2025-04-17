from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from kubernetes import client, config
from kubernetes.client.api_client import ApiClient
from mcp.server.fastmcp import Context, FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

from ..utils import remove_none


@dataclass
class AppContext:
    clients: dict[str, ApiClient]


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    clients = {}

    contexts, _ = config.list_kube_config_contexts()
    for context in contexts:
        api_client = config.new_client_from_config(context=context["name"])
        clients[context["name"]] = api_client

    yield AppContext(clients=clients)


mcp = FastMCP("kubernetes", lifespan=lifespan)


@mcp.tool()
def list_contexts(ctx: Context) -> list[str]:
    """
    List all available kubeconfig contexts.
    """
    return list(ctx.request_context.lifespan_context.clients.keys())


@mcp.tool()
def list_pods(ctx: Context, context: str = "", namespace: str = "") -> dict:
    """
    List all pods in the specified context and namespace.
    """
    if not context:
        context = list(ctx.request_context.lifespan_context.clients.keys())[0]

    if not namespace:
        namespace = "default"

    v1 = client.CoreV1Api(
        api_client=ctx.request_context.lifespan_context.clients[context]
    )

    if namespace == "all":
        pods = v1.list_pod_for_all_namespaces().to_dict()["items"]
    else:
        pods = v1.list_namespaced_pod(namespace).to_dict()["items"]

    ret = []
    for pod in pods:
        pod["metadata"].pop("managed_fields", None)
        ret.append(remove_none(pod))

    return {
        "context": context,
        "namespace": namespace,
        "items": ret,
    }


app = Starlette(
    routes=[
        Mount("/", app=mcp.sse_app()),
    ]
)
