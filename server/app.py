import pathlib

import uvicorn
from starlette.applications import Starlette
from starlette.endpoints import WebSocketEndpoint
from starlette.responses import FileResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

layouts_dir = pathlib.Path(__file__).parent / "layouts"
latest_robot_metrics: dict[str, object] | None = None
metrics_connections: set[WebSocket] = set()


async def home(request):
    return FileResponse(layouts_dir / "robot.html")


class RobotMetricsWebSocket(WebSocketEndpoint):
    encoding = "json"

    async def on_connect(self, websocket) -> None:
        await websocket.accept()
        metrics_connections.add(websocket)

    async def on_receive(self, websocket, data: dict[str, object]) -> None:
        global latest_robot_metrics
        latest_robot_metrics = data

        disconnected_connections = []
        for connection in list(metrics_connections):
            if connection is websocket:
                continue

            try:
                await connection.send_json(data)
            except RuntimeError:
                disconnected_connections.append(connection)

        for connection in disconnected_connections:
            metrics_connections.discard(connection)

    async def on_disconnect(self, websocket, close_code: int) -> None:
        metrics_connections.discard(websocket)


app = Starlette(
    routes=[
        Route("/", home),
        WebSocketRoute("/metrics", RobotMetricsWebSocket),
    ]
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2399)
